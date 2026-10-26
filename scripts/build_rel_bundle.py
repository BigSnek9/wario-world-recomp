"""Build main-plus-eight-REL DLLs: an uninstrumented candidate (--clean) or the
instrumented diagnostic bundle used for lockstep verification."""
from pathlib import Path
import argparse
import json
import re
import shutil
import subprocess
import sys
from relocation_model import parse
from emit_rel_metadata import emit

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--vectors", action="store_true", help="Include verified physical SDK exception/vector paths")
parser.add_argument("--clean", action="store_true", help="Emit the uninstrumented main-plus-REL port DLL without instruction-count instrumentation")
parser.add_argument("--clang", action="store_true",
                    help="Compile with LLVM clang-cl + Ninja into build/module-<variant>-clang/ (same /O2 /fp:strict flags; "
                         "~1.75x faster generated code than MSVC in measured gameplay)")
parser.add_argument("--clang-cl", default="C:/Program Files/LLVM/bin/clang-cl.exe")
args = parser.parse_args()
if args.vectors and args.clean:
    variant = "full-vectors"
elif args.vectors:
    variant = "rel-bundle-vectors"
elif args.clean:
    variant = "full"
else:
    variant = "rel-bundle"


def write_changed(path, text):
    if not path.is_file() or path.read_text() != text:
        path.write_text(text)


def copy_changed(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.is_file() or target.read_bytes() != source.read_bytes():
        shutil.copy2(source, target)


upstream = ROOT / "third_party/ModernGekko/vendor/dolphin"
destination = ROOT / "generated" / variant
destination.mkdir(parents=True, exist_ok=True)
subprocess.run([sys.executable, ROOT / "scripts/prepare_rel_sources.py"], check=True)
if args.vectors:
    subprocess.run([sys.executable, ROOT / "scripts/prepare_vector_sources.py"], check=True)
main_sources = list((ROOT / "build/modules/GWWE01").glob("*/dolrecomp-output/generated"))
if len(main_sources) != 1:
    raise SystemExit("Expected one main source tree")
main = main_sources[0]
for name in ("generated.h", "generated_smc.txt", "main.dol"):
    copy_changed(main / name, destination / name)
chunk_sources = [(p, destination / "chunks" / p.name) for p in (main / "chunks").glob("*.c")]
prepared = ROOT / "generated/rel-position-independent/rels"
for path in prepared.rglob("generated.h"):
    copy_changed(path, destination / "rels" / path.relative_to(prepared))
chunk_sources += [(p, destination / "rels" / p.relative_to(prepared)) for p in prepared.rglob("chunks/*.c")]
vector_root = ROOT / "generated/vector-sources"
vectors = json.loads((vector_root / "manifest.json").read_text()) if args.vectors else []
for vector in vectors:
    name = vector["name"]
    source, target = vector_root / name / "generated", destination / "vectors" / name
    copy_changed(source / "generated.h", target / "generated.h")
    chunk_sources += [(p, target / "chunks" / p.name) for p in (source / "chunks").glob("*.c")]
for name in ("rel_support.h", "rel_support.c"):
    copy_changed(ROOT / "runtime" / name, destination / name)
base, models = 0x80500000, []
for path in sorted((ROOT / "original/GWWE01/files/dll").glob("*.rel")):
    raw = path.read_bytes()
    model = parse(raw)
    model["linked_base"], model["name"] = base, path.stem + "_" + str(model["module_id"])
    models.append(model)
    base = (base + len(raw) + int.from_bytes(raw[0x20:0x24], "big") + 0xffff) & ~0xffff
write_changed(destination / "rel_metadata.c", emit(models))
# The diagnostic bundle instruments every actual instruction comment, including
# counted-loop copies. The clean bundle copies chunks unchanged.
sites = 0
for source, chunk in chunk_sources:
    text = source.read_text()
    if args.clean:
        count = 0
    else:
        text, count = re.subn(r"(^    // [0-9A-Fa-f]{8}: [^\n]*\n)(?!    // embedded data)",
                              r"\1    if (wario_count_enabled) ++wario_instruction_count;\n", text, flags=re.M)
        text = text.replace('#include "../generated.h"', '#include "../generated.h"\nextern u64 wario_instruction_count;\nextern int wario_count_enabled;')
    chunk.parent.mkdir(parents=True, exist_ok=True)
    write_changed(chunk, text)
    sites += count
for model in models:
    mid, name = model["module_id"], model["name"]
    write_changed(destination / f"rel_bridge_{mid}.c",
        f'#include "rels/{name}/generated.h"\nint wario_rel_dispatch_{mid}(CPUState* ctx, u32 actual_pc) {{ return dolrecomp_call(ctx, actual_pc); }}\n')
for vector in vectors:
    name = vector["name"]
    write_changed(destination / f"vector_bridge_{name}.c",
        f'#include "vectors/{name}/generated.h"\nint wario_{name}_dispatch(CPUState* ctx,u32 pc) {{ return dolrecomp_call(ctx,pc); }}\n')

template = ROOT / "build" / (variant + "-template")
shutil.copytree(upstream / "module-template", template, dirs_exist_ok=True)
# Retain the pinned table generator for the DOL; append REL coverage explicitly.
subprocess.run([sys.executable, upstream / "module-template/gen_module_tables.py", destination / "generated.h",
                destination / "generated_smc.txt", destination / "main.dol", destination / "main_tables.inc"], check=True)
tables = (destination / "main_tables.inc").read_text()
new_ranges, new_chunks, rel_metadata = [], [], []
for model in models:
    mid = model["module_id"]
    code_sections = []
    header = (destination / "rels" / model["name"] / "generated.h").read_text()
    functions = sorted(int(x, 16) for x in re.findall(r"void func_([0-9A-Fa-f]{8})\(CPUState\* ctx\);", header))
    for section in model["sections"]:
        if not section["executable"] or not section["size"]:
            continue
        start, end = model["linked_base"] + section["offset"], model["linked_base"] + section["offset"] + section["size"]
        new_ranges.append((start, end))
        code_sections.append((section["index"], start, section["size"]))
        entries = [a for a in functions if start <= a < end]
        if not entries or entries[0] != start:
            raise ValueError("REL chunks do not tile section")
        for index, address in enumerate(entries):
            new_chunks.append((address, entries[index + 1] if index + 1 < len(entries) else end))
    rel_metadata.append((model, code_sections))

def array_body(text, name):
    return re.search(rf"static const [^\n]+ {name}\[\] = \{{\n(.*?)\n\}};", text, re.S)[1]

def ranges(text, name):
    return [(int(a,16),int(b,16)) for a,b in re.findall(r"\{\s*0x([0-9A-Fa-f]+)u,\s*0x([0-9A-Fa-f]+)u", array_body(text,name))]

all_ranges = ranges(tables,"s_code_ranges") + new_ranges
all_smc = ranges(tables,"s_smc_ranges")
main_chunks = ranges(tables,"s_chunk_ranges")
main_hashes = [int(x,16) for x in re.findall(r"0x([0-9A-Fa-f]+)u",array_body(tables,"s_chunk_hashes"))]
chunk_hashes = list(zip(main_chunks,main_hashes)) + [(r,0) for r in new_chunks]
for vector in vectors:
    folder = vector_root / vector["name"]
    source = folder / "generated"
    output = folder / "vector_tables.inc"
    subprocess.run([sys.executable,upstream / "module-template/gen_module_tables.py",source / "generated.h",
                    source / "generated_smc.txt",folder / "derived.dol",output],check=True,stdout=subprocess.DEVNULL)
    text = output.read_text()
    all_ranges += ranges(text,"s_code_ranges")
    all_smc += ranges(text,"s_smc_ranges")
    chunks = ranges(text,"s_chunk_ranges")
    hashes = [int(x,16) for x in re.findall(r"0x([0-9A-Fa-f]+)u",array_body(text,"s_chunk_hashes"))]
    chunk_hashes += list(zip(chunks,hashes))
tables = "// Private generated bundle tables.\n"
for name, entries, macro in (("s_code_ranges",sorted(all_ranges),"MODULE_CODE_RANGE_COUNT"),
                             ("s_smc_ranges",sorted(all_smc),"MODULE_SMC_RANGE_COUNT"),
                             ("s_chunk_ranges",[r for r,h in sorted(chunk_hashes)],"MODULE_CHUNK_RANGE_COUNT")):
    tables += f"static const StaticRecompRange {name}[] = {{\n"
    tables += "\n".join(f"{{0x{a:08X}u,0x{b:08X}u}}," for a,b in entries) or "{0u,0u},"
    tables += f"\n}};\n#define {macro} {len(entries)}u\n"
tables += "static const u64 s_chunk_hashes[] = {\n" + "\n".join(f"0x{h:016X}ull," for r,h in sorted(chunk_hashes)) + "\n};\n"
for model, sections in rel_metadata:
    mid = model["module_id"]
    tables += f"\nstatic const StaticRecompRelSection rel_sections_{mid}[] = {{\n"
    tables += "\n".join(f"{{{mid}u,{index}u,0x{address:08X}u,{size}u}}," for index,address,size in sections) + "\n};\n"
tables += "\nstatic const StaticRecompRelModule s_rel_modules[] = {\n"
for model, sections in rel_metadata:
    mid = model["module_id"]
    tables += f"{{{mid}u,{model['version']}u,{len(model['sections'])}u,{model['table_offset']}u,{model['file_size']}u,rel_sections_{mid},{len(sections)}u}},\n"
tables += "};\n"
write_changed(destination / "bundle_tables.inc", tables)
glue = '''#include "generated.h"
#include "rel_support.h"
#include "StaticRecompABI.h"
BRIDGE_DECLARATIONS
VECTOR_DECLARATIONS
static int chassis_dispatch(CPUState* ctx, u32 linked) {
    (void)linked;
    u32 actual = ctx->pc;
    if (dolrecomp_find_original(actual)) return dolrecomp_call(ctx, actual);
VECTOR_DISPATCH
BRIDGE_DISPATCH
    return 0;
}
void dolrecomp_indirect_dispatch(CPUState* ctx, u32 address) { ctx->pc=address; (void)chassis_dispatch(ctx,address); }
static void loaded(CPUState* ctx) { ppc_fpscr_updated(ctx); }
#include "bundle_tables.inc"
static const StaticRecompModuleDesc s_desc = {
    STATICRECOMP_ABI_VERSION,GXRUNTIME_CPU_ABI_VERSION,(u32)sizeof(CPUState),"GWWE01",DOLRECOMP_ENTRY_POINT,
    chassis_dispatch,loaded,s_code_ranges,MODULE_CODE_RANGE_COUNT,s_smc_ranges,MODULE_SMC_RANGE_COUNT,
    s_chunk_ranges,MODULE_CHUNK_RANGE_COUNT,s_chunk_hashes,s_rel_modules,8u
};
WARIO_REL_EXPORT const StaticRecompModuleDesc* staticrecomp_get_module(void) { return &s_desc; }
WARIO_REL_EXPORT int wario_runtime_pc_module(void) { return 1; }
JOURNAL_GLOBALS
'''
journal_globals = ("u64 wario_instruction_count=0;\n"
                   "int wario_count_enabled=0;\n"
                   "WARIO_REL_EXPORT u64 wario_instruction_journal(int enabled) {\n"
                   "    u64 previous=wario_instruction_count;wario_count_enabled=enabled;\n"
                   "    if(enabled) wario_instruction_count=0;return previous;\n"
                   "}\n") if not args.clean else ""
glue = glue.replace("JOURNAL_GLOBALS", journal_globals)
glue = glue.replace("BRIDGE_DECLARATIONS", "\n".join(f"int wario_rel_dispatch_{m['module_id']}(CPUState*,u32);" for m in models))
glue = glue.replace("BRIDGE_DISPATCH", "\n".join(f"    if(wario_rel_to_linked(ctx,{m['module_id']}u,actual)) return wario_rel_dispatch_{m['module_id']}(ctx,actual);" for m in models))
glue = glue.replace("VECTOR_DECLARATIONS", "\n".join(f"int wario_{v['name']}_dispatch(CPUState*,u32);" for v in vectors))
glue = glue.replace("VECTOR_DISPATCH", "\n".join(f"    if(actual>=0x{v['address']:08X}u && actual<0x{v['address']+v['size']:08X}u) return wario_{v['name']}_dispatch(ctx,actual);" for v in vectors))
(template / "module_export.c").write_text(glue)
cmake = (template / "CMakeLists.txt").read_text()
cmake = cmake.replace('file(GLOB CHUNK_INPUTS CONFIGURE_DEPENDS "${GENERATED_DIR}/chunks/*.c")',
    'file(GLOB_RECURSE CHUNK_INPUTS CONFIGURE_DEPENDS "${GENERATED_DIR}/chunks/*.c" "${GENERATED_DIR}/rels/*/chunks/*.c" "${GENERATED_DIR}/vectors/*/chunks/*.c")')
cmake += '\nfile(GLOB REL_BRIDGES "${GENERATED_DIR}/rel_bridge_*.c" "${GENERATED_DIR}/vector_bridge_*.c")\ntarget_sources(${MODULE_NAME} PRIVATE ${REL_BRIDGES} "${GENERATED_DIR}/rel_metadata.c" "${GENERATED_DIR}/rel_support.c")\ntarget_compile_options(${MODULE_NAME} PRIVATE $<$<C_COMPILER_ID:MSVC>:/MP8>)\n'
if not vectors:
    cmake = cmake.replace(' "${GENERATED_DIR}/vectors/*/chunks/*.c"', '')
    cmake = cmake.replace(' "${GENERATED_DIR}/vector_bridge_*.c"', '')
(template / "CMakeLists.txt").write_text(cmake)
def vcvars64():
    for edition in (sorted(Path("C:/Program Files (x86)/Microsoft Visual Studio/2022").glob("*")) +
                    sorted(Path("C:/Program Files/Microsoft Visual Studio/2022").glob("*"))):
        candidate = edition / "VC/Auxiliary/Build/vcvars64.bat"
        if candidate.is_file():
            return candidate
    raise SystemExit("vcvars64.bat not found; --clang needs the MSVC x64 environment for headers/libs")


common = ["-DGAME_ID=GWWE01", "-DGENERATED_DIR=" + str(destination), "-DGXRUNTIME_DIR=" + str(upstream / "GXRuntime"),
          "-DCHASSIS_ABI_DIR=" + str(upstream / "Source/Core/Core/PowerPC/StaticRecomp")]
print("Bundle instruction sites:", sites, "REL chunks:", len(new_chunks), flush=True)
if args.clang:
    build = ROOT / "build" / ("module-" + variant + "-clang")
    clang = Path(args.clang_cl)
    if not clang.is_file():
        raise SystemExit(f"clang-cl not found at {clang}")
    linker = clang.with_name("lld-link.exe")
    configure = subprocess.list2cmdline(["cmake", "-S", str(template), "-B", str(build), "-G", "Ninja",
        "-DCMAKE_BUILD_TYPE=Release", "-DCMAKE_C_COMPILER=" + clang.as_posix(), "-DCMAKE_CXX_COMPILER=" + clang.as_posix(),
        "-DCMAKE_LINKER=" + linker.as_posix(), "-DRECOMPCORE_MODULE_ENABLE_IPO=OFF", *common])
    compile_ = subprocess.list2cmdline(["cmake", "--build", str(build), "--parallel", "8"])
    script = build.parent / (build.name + "-build.cmd")
    script.write_text(f'@echo off\r\ncall "{vcvars64()}" >nul 2>nul || exit /b 1\r\n'
                      f'{configure} || exit /b 1\r\n{compile_}\r\n')
    with (ROOT / f"reports/build-rel-bundle-{variant}-clang.log").open("w") as log:
        subprocess.run(["cmd", "/c", str(script)], check=True, stdout=log, stderr=subprocess.STDOUT)
    print(build / "gGWWE01_recomp.dll")
    raise SystemExit(0)
build = ROOT / "build" / ("module-" + variant)
command = ["cmake", "-S", template, "-B", build, "-G", "Visual Studio 17 2022", "-A", "x64", *common]
with (ROOT / f"reports/build-rel-bundle-{variant}.log").open("w") as log:
    subprocess.run(command, check=True, stdout=log, stderr=subprocess.STDOUT)
    subprocess.run(["cmake", "--build", build, "--config", "Release", "--parallel", "1", "--", "/nr:false"], check=True, stdout=log, stderr=subprocess.STDOUT)
print(build / "Release/gGWWE01_recomp.dll")
