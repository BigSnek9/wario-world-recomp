"""Build a separate diagnostic DLL that counts attempted guest instructions.

This instruments private generated C, never the original executable. It lets the
shadow interpreter stop after the exact native instruction count, avoiding a
cycle-estimate guess when a chunk returns inside an unrolled/counted loop.
"""
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
upstream = ROOT / "third_party/ModernGekko/vendor/dolphin"
sources = sorted((ROOT / "build/modules/GWWE01").glob("*/dolrecomp-output/generated"))
if len(sources) != 1:
    raise SystemExit("Expected one pinned main-module source tree")
source = sources[0]
generated = ROOT / "generated/main-instrumented"
generated.mkdir(parents=True, exist_ok=True)
for name in ("generated.h", "generated_smc.txt", "main.dol"):
    shutil.copy2(source / name, generated / name)
(generated / "chunks").mkdir(exist_ok=True)
sites = 0
for chunk in sorted((source / "chunks").glob("*.c")):
    text = chunk.read_text()
    text, count = re.subn(r"(^    // [0-9A-Fa-f]{8}: [^\n]*\n)(?!    // embedded data)",
                          r"\1    if (wario_count_enabled) ++wario_instruction_count;\n", text, flags=re.M)
    sites += count
    text = text.replace('#include "../generated.h"', '#include "../generated.h"\n#include "../wario_instruction_counter.h"')
    (generated / "chunks" / chunk.name).write_text(text)
(generated / "wario_instruction_counter.h").write_text("extern u64 wario_instruction_count;\nextern int wario_count_enabled;\n")
template = ROOT / "build/instrumented-template"
shutil.copytree(upstream / "module-template", template, dirs_exist_ok=True)
export = template / "module_export.c"
export.write_text(export.read_text() + '''
u64 wario_instruction_count = 0;
int wario_count_enabled = 0;
RECOMP_MODULE_EXPORT u64 wario_instruction_journal(int enabled) {
    const u64 result = wario_instruction_count;
    wario_count_enabled = enabled;
    if (enabled) wario_instruction_count = 0;
    return result;
}
''')
build = ROOT / "build/module-instrumented"
args = ["cmake", "-S", str(template), "-B", str(build), "-G", "Visual Studio 17 2022", "-A", "x64",
        "-DGAME_ID=GWWE01", "-DGENERATED_DIR=" + str(generated),
        "-DGXRUNTIME_DIR=" + str(upstream / "GXRuntime"),
        "-DCHASSIS_ABI_DIR=" + str(upstream / "Source/Core/Core/PowerPC/StaticRecomp")]
print("Diagnostic instruction sites:", sites, flush=True)
with (ROOT / "reports/build-instrumented.log").open("w") as log:
    subprocess.run(args, check=True, stdout=log, stderr=subprocess.STDOUT)
    subprocess.run(["cmake", "--build", str(build), "--config", "Release", "--parallel", "8"],
                   check=True, stdout=log, stderr=subprocess.STDOUT)
print(build / "Release/gGWWE01_recomp.dll")
