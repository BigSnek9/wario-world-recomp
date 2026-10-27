"""Build main-plus-eight-REL DLLs: an uninstrumented candidate (--clean) or the
instrumented diagnostic bundle used for lockstep verification."""
from pathlib import Path
import argparse
import json
import os
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
parser.add_argument("--pgo-generate", action="store_true",
                    help="With --clang: build an instrumented module (-fprofile-instr-generate) into module-<variant>-clang-pgogen")
parser.add_argument("--pgo-use", help="With --clang: merged .profdata path relative to the Recomp folder (no spaces); "
                                      "builds module-<variant>-clang-pgo")
parser.add_argument("--jobs", type=int, default=8, help="Parallel compile jobs for --clang builds")
parser.add_argument("--build-dir", help="Build folder name under build/ (default: module-<variant>[-clang suffix]); "
                                        "use to test a module without touching the standard output")
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
# Optional widescreen support (docs/modding/WIDESCREEN_SUPPORT.md WS-005/WS-006):
# the x coordinates (+-320) of the full-screen quad draws (fades/overlays)
# read the exported module variable wario_fullscreen_half_width instead of a
# constant. It is 320 unless the runtime's aspect adapter widens it, so the
# default build computes exactly the original values.
# The screen-overlay constructors fn_8007EBF0 (textured EFB-copy feedback quad,
# drawn by fn_8007EE8C; the loading-coin afterimage) and fn_8007F7A4 (solid
# colour quad, drawn by fn_8007FA2C) store the constant 320 in object +0x30
# (s16; nothing else writes it), which the draw routines use as +-x. Those
# stores stay original; the draw-time reads (HUD_EDGE_SITES below, 0x8007EEBC
# and 0x8007FA6C/7C/8C/A4) map 320 to the live half width, so overlays built
# before an aspect change (or restored from a savestate) still cover the screen.
FULLSCREEN_QUAD_X = (0x80062C3C, 0x80062C50, 0x800708C8, 0x800708DC, 0x800728B0, 0x800728C4)
quad_sites = 0


# FPS object tagging (docs/modding/FPS_UNLOCK.md, "game-level interpolation"). The engine
# draws every model through one matrix stack (object at [0x801FDA38]: +4 base of 0x30-byte
# matrices, +8 top index). Its methods get an entry hook that keeps a shadow identity per stack
# level (wario_mtx_hook in module_export.c):
#   fn_80047990 push (copy top up), fn_800479F4 set top from r4, fn_80047A5C top *= r4,
#   fn_80047A90/B44/C18/CEC load stack[top - r4] into GX matrix slot r5 (GXLoadPosMtxImm).
# A load writes the identity into the GX stream as a 2-word XF write to the unused XF memory at
# 0x0FFE just before the matrix, so the video side pairs matrices between frames exactly. Inert
# (no extra GX commands) unless the runtime sets wario_fps_tagging.
MATRIX_STACK_HOOKS = {0x80047990: 1, 0x800479F4: 2, 0x80047A5C: 3,
                      0x80047A90: 4, 0x80047B44: 4, 0x80047C18: 4, 0x80047CEC: 4}
mtx_sites = 0


def hook_matrix_stack(text):
    global mtx_sites
    for address, kind in MATRIX_STACK_HOOKS.items():
        old = "label_%08X:\n    ctx->pc = 0x%08Xu;\n" % (address, address)
        if old in text:
            if text.count(old) != 1:
                raise SystemExit(f"matrix stack hook {address:08X}: unexpected generated code")
            text = text.replace(old, old + "    wario_mtx_hook(ctx, %d);\n" % kind)
            mtx_sites += 1
    if "wario_mtx_hook(ctx," in text:
        text = text.replace('#include "../generated.h"',
                            '#include "../generated.h"\nvoid wario_mtx_hook(CPUState* ctx, int kind);', 1)
    return text


def widen_fullscreen_quads(text):
    global quad_sites
    for address in FULLSCREEN_QUAD_X:
        pattern = re.compile(r"(    // %08X: li\s+r(\d+), (-?)320\n    ctx->gpr\[\2\] = )\(u32\)\(s32\)\(-?320\);" % address)
        text, count = pattern.subn(r"\1(u32)(s32)(\3wario_fullscreen_half_width);", text)
        quad_sites += count
    text = anchor_hud_edges(text)
    text = hook_matrix_stack(text)
    if any(name in text for name in ("wario_fullscreen_half_width", "WARIO_HUD_DX", "wario_hud_edge", "wario_quad_half", "wario_sync_2d_ortho", "wario_sync_screen_perspective", "wario_book_row")):
        text = text.replace('#include "../generated.h"',
                            '#include "../generated.h"\nextern volatile s32 wario_fullscreen_half_width;' +
                            HUD_EDGE_HELPERS, 1)
    return text


# WS-003 (docs/engine/WIDESCREEN.md): edge-anchored HUD x positions. The extra
# half width of the widened 2D ortho (WARIO_HUD_DX = wario_fullscreen_half_width
# - 320; 0 in 4:3, so the default build computes exactly the original values)
# moves left-anchored elements left and right-anchored ones right. Applied where
# the x is read for drawing (not where the objects are built), so a live aspect
# change moves HUD objects that already exist. Covers the community 16:9 Gecko
# code's HUD sites (it hard-codes DX = 106/107 at the constructors instead).
#   fn_80080954 (left slide-in coin panel, fn_80080658): screen-left edge -320.
#   fn_800814E0 (top-left slide-in counters, children of fn_80082044): x passed
#     to the three draw virtuals.
#   fn_80082344 sprite rows: hearts (fn_800829C4, x -280, bottom-left) and the
#     stage counter row (fn_80082E4C via fn_80082D84, x +280, bottom-right); the
#     stored x (+0x1C) is read by fn_80082594 (item n x), fn_800825C8 and
#     fn_8008284C (draw) and fn_800824A0 (position getter, s16 -> float via
#     GQR5). Pushed away from the centre by sign: x<0 left, x>0 right.
#   fn_80080BA4 indicator (x +272 at +0x36, bottom-right): fn_80080E54 and
#     fn_80080FF0 (draw, including the s16 -> float matrix x at 0x80081148).
_EDGE_I = "(u32)wario_hud_edge_x(ctx, (s32)(s16)mem_read16(ctx, ea));"
_QUAD_I = "(u32)wario_quad_half((s32)(s16)mem_read16(ctx, ea));"
HUD_EDGE_SITES = {
    0x800809D0: ("u64 res = (u64)(u32)(s32)(-320) +", "u64 res = (u64)(u32)(s32)(-320 - WARIO_HUD_DX) +"),
    0x80081528: ("ctx->gpr[4] = ctx->gpr[31] | ctx->gpr[31];", "ctx->gpr[4] = ctx->gpr[31] - (u32)WARIO_HUD_DX;"),
    0x80081538: ("ctx->gpr[4] = ctx->gpr[31] | ctx->gpr[31];", "ctx->gpr[4] = ctx->gpr[31] - (u32)WARIO_HUD_DX;"),
    0x8008155C: ("ctx->gpr[4] = ctx->gpr[31] | ctx->gpr[31];", "ctx->gpr[4] = ctx->gpr[31] - (u32)WARIO_HUD_DX;"),
    0x800825B0: ("(u32)(s32)(s16)mem_read16(ctx, ea);", _EDGE_I),
    0x800825BC: ("(u32)(s32)(s16)mem_read16(ctx, ea);", _EDGE_I),
    0x80082600: ("(u32)(s32)(s16)mem_read16(ctx, ea);", _EDGE_I),
    0x800828C4: ("(u32)(s32)(s16)mem_read16(ctx, ea);", _EDGE_I),
    0x800824A0: ("ppc_psq_load_inline(ctx, 1u, ea, true, 5u, false, 0x800824A0u);",
                 "ppc_psq_load_inline(ctx, 1u, ea, true, 5u, false, 0x800824A0u);\n"
                 "        ctx->fpr[1] = wario_hud_edge_f(ctx, ctx->fpr[1]);"),
    0x80080E78: ("(u32)(s32)(s16)mem_read16(ctx, ea);", _EDGE_I),
    0x8008101C: ("(u32)(s32)(s16)mem_read16(ctx, ea);", _EDGE_I),
    0x80081148: ("ppc_psq_load_inline(ctx, 1u, ea, true, 5u, false, 0x80081148u);",
                 "ppc_psq_load_inline(ctx, 1u, ea, true, 5u, false, 0x80081148u);\n"
                 "        ctx->fpr[1] = wario_hud_edge_f(ctx, ctx->fpr[1]);"),
    # fn_8006F954 (2D camera apply, GXSetProjection(obj+0x14, ortho)): the 2D
    # camera bakes HC-0007 into m[0][0] = 2/(r-l) only when it is constructed
    # (fn_8006F7CC -> C_MTXOrtho fn_8019C6E8), so a camera built before an aspect
    # change (or restored from a savestate) kept the old width while the HUD
    # offsets above follow the live value. Recompute m[0][0] from the live
    # HC-0007 with C_MTXOrtho's arithmetic (l = -r, so m[0][3] stays -0). Inert
    # until the adapter first widens the half width, so a 4:3-only session never
    # writes; switching back to 4:3 restores exactly 2*(1/640).
    0x8007EEBC: ("(u32)(s32)(s16)mem_read16(ctx, ea);", _QUAD_I),
    0x8007FA6C: ("(u32)(s32)(s16)mem_read16(ctx, ea);", _QUAD_I),
    0x8007FA7C: ("(u32)(s32)(s16)mem_read16(ctx, ea);", _QUAD_I),
    0x8007FA8C: ("(u32)(s32)(s16)mem_read16(ctx, ea);", _QUAD_I),
    0x8007FAA4: ("(u32)(s32)(s16)mem_read16(ctx, ea);", _QUAD_I),
    0x8006F978: ("ctx->gpr[3] = ctx->gpr[31] + (u32)(s32)(20);",
                 "ctx->gpr[3] = ctx->gpr[31] + (u32)(s32)(20);\n    wario_sync_2d_ortho(ctx, ctx->gpr[3]);"),
    # WS-007 fixed-size screen cameras built by fn_8007DF18 next to the 2D layer:
    # fn_80067AA8 (C_MTXOrtho +-320 x +-224, applied by fn_80067C34) and
    # fn_80067D50 (C_MTXPerspective 30 deg, aspect = viewport 512/448, applied
    # by fn_80067F44). They draw the hint/message boards and the 3D figures in
    # them, which a wide screen stretched. At their GXSetProjection(obj+0x10)
    # m[0][0] follows the live half width: ortho as the 2D layer above,
    # perspective m00 = m11 / (aspect * half/320) (C_MTXPerspective computes
    # m00 = cot / aspect with m11 = cot, so 4:3 restores the exact value).
    0x80067D14: ("ctx->gpr[3] = ctx->gpr[31] + (u32)(s32)(16);",
                 "ctx->gpr[3] = ctx->gpr[31] + (u32)(s32)(16);\n    wario_sync_2d_ortho(ctx, ctx->gpr[3]);"),
    0x80068014: ("ctx->gpr[3] = ctx->gpr[31] + (u32)(s32)(16);",
                 "ctx->gpr[3] = ctx->gpr[31] + (u32)(s32)(16);\n    wario_sync_screen_perspective(ctx, ctx->gpr[3]);"),
    # WS-008 pause book Sprite/jail row: fn_8006051C (draw method of the page
    # component vtable lbl_801BC2E4, built by fn_8006073C for the pause page
    # lbl_801BC2C0) draws each of the 5 slots (rescued Sprite model or jail) in
    # its own 215x215 EFB-pixel viewport: GXSetViewport (fn_8019B500 at
    # 0x8006062C) x = 181 + 43*i (f29 from lbl_801FE460, step lbl_801FE468),
    # inside GXSetScissor(264, 310, 215, 124) (0x800605C0). Pixel positions do
    # not follow the widened 2D layer, so on a wide screen the row spread out
    # by half/320 while the book (and the shadow markers printed on its page)
    # stayed 4:3: the last jail hung past the page edge. Wide screens map the
    # slot centres and the scissor edges about the EFB centre by 320/half,
    # which puts the row back on the markers exactly as at 4:3; the viewport
    # size stays (the synced WS-007 perspective already keeps the figures'
    # shape and size). 4:3 (half width 320) computes exactly the original values.
    0x800605B0: ("ctx->gpr[3] = (u32)(s32)(264);",
                 "ctx->gpr[3] = (u32)wario_book_row_scissor(ctx, 264, 215, 0);"),
    0x800605B8: ("ctx->gpr[5] = (u32)(s32)(215);",
                 "ctx->gpr[5] = (u32)wario_book_row_scissor(ctx, 264, 215, 1);"),
    0x80060618: ("ctx->fpr[1] = ctx->fpr[29];",
                 "ctx->fpr[1] = wario_book_row_x(ctx, ctx->fpr[29], ctx->fpr[3]);"),
}
# The pause book is drawn at 4:3 in the centre, and the HUD rows drawn with it
# (hearts, coin panel, stage counter row) belong inside it, so DX is 0 while the
# game's own pause-menu freeze bit is set: bit 0x8 of lbl_801FD930 (main-loop
# state word), kept by the push/pop counter lbl_801FD940 in fn_8003195C, whose
# only callers are the pause-menu states fn_8006CB04 (open, +1) and fn_8006DC4C
# (close finished, -1); the HUD itself reads it through fn_8003199C
# (fn_80082B4C). Only read when the screen is wide, so 4:3 never touches it.
HUD_EDGE_HELPERS = """
static inline s32 wario_hud_dx(CPUState* ctx) {
    const s32 dx = (s32)wario_fullscreen_half_width - 320;
    return dx == 0 || (mem_read32(ctx, 0x801FD930u) & 0x8u) ? 0 : dx;
}
#define WARIO_HUD_DX wario_hud_dx(ctx)
static inline s32 wario_hud_edge_x(CPUState* ctx, s32 x) {
    const s32 dx = WARIO_HUD_DX;
    return dx == 0 ? x : x < 0 ? x - dx : x > 0 ? x + dx : x;
}
static inline f64 wario_hud_edge_f(CPUState* ctx, f64 x) {
    const s32 dx = WARIO_HUD_DX;
    return dx == 0 ? x : x < 0.0 ? x - (f64)dx : x > 0.0 ? x + (f64)dx : x;
}
static inline s32 wario_quad_half(s32 x) {
    return x == 320 ? (s32)wario_fullscreen_half_width : x;
}
static int wario_wide_seen;
static inline void wario_sync_2d_ortho(CPUState* ctx, u32 m00_address) {
    union { u32 u; float f; } half, m00;
    if (wario_fullscreen_half_width != 320)
        wario_wide_seen = 1;
    if (!wario_wide_seen)
        return;
    half.u = mem_read32(ctx, 0x801FE6CCu);
    m00.f = 2.0f * (1.0f / (half.f - -half.f));
    if (mem_read32(ctx, m00_address) != m00.u)
        mem_write32(ctx, m00_address, m00.u);
}
static inline void wario_sync_screen_perspective(CPUState* ctx, u32 m00_address) {
    union { u32 u; float f; } half, m11, width, height, m00;
    if (wario_fullscreen_half_width != 320)
        wario_wide_seen = 1;
    if (!wario_wide_seen)
        return;
    half.u = mem_read32(ctx, 0x801FE6CCu);
    m11.u = mem_read32(ctx, m00_address + 0x14u);
    width.u = mem_read32(ctx, 0x801FDA20u);
    height.u = mem_read32(ctx, 0x801FDA24u);
    m00.f = m11.f / ((width.f / height.f) * (half.f / 320.0f));
    if (mem_read32(ctx, m00_address) != m00.u)
        mem_write32(ctx, m00_address, m00.u);
}
static inline f64 wario_book_row_scale(CPUState* ctx) {
    union { u32 u; float f; } half;
    if (wario_fullscreen_half_width == 320)
        return 1.0;
    half.u = mem_read32(ctx, 0x801FE6CCu);
    return half.f > 0.0f ? 320.0 / (f64)half.f : 1.0;
}
static inline f64 wario_book_center(CPUState* ctx) {
    union { u32 u; float f; } width;
    width.u = mem_read32(ctx, 0x801FDA20u);
    return (f64)width.f * 0.5;
}
static inline f64 wario_book_row_x(CPUState* ctx, f64 x, f64 w) {
    const f64 s = wario_book_row_scale(ctx);
    if (s == 1.0)
        return x;
    const f64 c = wario_book_center(ctx);
    return (f64)(float)(c + (x + w * 0.5 - c) * s - w * 0.5);
}
static inline s32 wario_book_row_scissor(CPUState* ctx, s32 x, s32 w, int want_width) {
    const f64 s = wario_book_row_scale(ctx);
    if (s == 1.0)
        return want_width ? w : x;
    const f64 c = wario_book_center(ctx);
    const s32 left = (s32)(c + ((f64)x - c) * s + 0.5);
    const s32 right = (s32)(c + ((f64)(x + w) - c) * s + 0.5);
    return want_width ? right - left : left;
}"""
hud_sites = 0


def anchor_hud_edges(text):
    global hud_sites
    for address, (old, new) in HUD_EDGE_SITES.items():
        marker = "    // %08X: " % address
        start = text.find(marker)
        if start < 0:
            continue
        end = text.find("\n    // ", start + len(marker))  # next instruction comment
        end = len(text) if end < 0 else end
        block = text[start:end]
        if block.count(old) != 1:
            raise SystemExit(f"HUD edge site {address:08X}: unexpected generated code")
        text = text[:start] + block.replace(old, new) + text[end:]
        hud_sites += 1
    return text


for source, chunk in chunk_sources:
    text = widen_fullscreen_quads(source.read_text())
    if args.clean:
        count = 0
    else:
        text, count = re.subn(r"(^    // [0-9A-Fa-f]{8}: [^\n]*\n)(?!    // embedded data)",
                              r"\1    if (wario_count_enabled) ++wario_instruction_count;\n", text, flags=re.M)
        text = text.replace('#include "../generated.h"', '#include "../generated.h"\nextern u64 wario_instruction_count;\nextern int wario_count_enabled;')
    chunk.parent.mkdir(parents=True, exist_ok=True)
    write_changed(chunk, text)
    sites += count
if quad_sites != len(FULLSCREEN_QUAD_X):
    raise SystemExit(f"expected {len(FULLSCREEN_QUAD_X)} full-screen quad sites, patched {quad_sites}")
if hud_sites != len(HUD_EDGE_SITES):
    raise SystemExit(f"expected {len(HUD_EDGE_SITES)} HUD edge sites, patched {hud_sites}")
if mtx_sites != len(MATRIX_STACK_HOOKS):
    raise SystemExit(f"expected {len(MATRIX_STACK_HOOKS)} matrix stack hooks, patched {mtx_sites}")
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
WARIO_REL_EXPORT volatile s32 wario_fullscreen_half_width = 320; /* WS-005; 320 = original */
/* FPS object tagging (scripts/build_rel_bundle.py MATRIX_STACK_HOOKS). Shadow identity per
   matrix-stack level: set/multiply mix in the source matrix address (persistent per object or
   bone) and the call site; when the source is a temporary on the guest stack, the caller's
   non-volatile registers r14-r31 holding heap pointers (`this`, node) or small integers (loop
   counters / item offsets) are used. */
WARIO_REL_EXPORT volatile s32 wario_fps_tagging = 0; /* set by the runtime; 0 = original stream */
#define WARIO_MTX_LEVELS 64
static u32 wario_mtx_stack_object;
static u64 wario_mtx_ids[WARIO_MTX_LEVELS];
static u32 wario_mtx_site[WARIO_MTX_LEVELS]; /* last set/multiply call site per level (debug) */
static u64 wario_mtx_mix(u64 h, u64 v) {
    h ^= v + 0x9E3779B97F4A7C15ull + (h << 6) + (h >> 2);
    return h * 0xBF58476D1CE4E5B9ull;
}
static u64 wario_mtx_source(CPUState* ctx, u32 source) {
    u64 h = wario_mtx_mix(0, ctx->lr);
    const u32 sp = ctx->gpr[1];
    if (source - sp < 0x4000u || sp - source < 0x100u) {
        for (int r = 14; r <= 31; ++r) {
            const u32 v = ctx->gpr[r];
            /* heap pointers (owner, node) and small loop counters/offsets (item index) */
            if ((v >= 0x80000000u && v < 0x81800000u && (v - sp >= 0x4000u)) || v < 0x10000u)
                h = wario_mtx_mix(h, ((u64)r << 32) | v);
        }
        return h;
    }
    return wario_mtx_mix(h, source);
}
/* Diagnostics: WARIO_MTX_DEBUG=<file> writes a histogram of hook call sites
   (kind, return address, source on the stack, r29-r31) every 100000 calls. */
#include <stdio.h>
#include <stdlib.h>
typedef struct { u32 lr, kind, temp, r29, r30, r31, count; } WarioMtxSite;
static WarioMtxSite wario_mtx_sites[4096];
static int wario_mtx_debug_on;
static u64 wario_mtx_seen_id[8192];
static u32 wario_mtx_seen_hash[8192], wario_mtx_seen_frame;
static void wario_mtx_count(u32 lr, u32 kind, u32 temp) {
    u32 h = (lr * 2654435761u ^ kind * 97u ^ temp) & 4095u;
    for (int probe = 0; probe < 4096; ++probe, h = (h + 1u) & 4095u) {
        WarioMtxSite* s = &wario_mtx_sites[h];
        if (s->count == 0) { s->lr = lr; s->kind = kind; s->temp = temp; }
        if (s->lr == lr && s->kind == kind && s->temp == temp) { s->count++; return; }
    }
}
static void wario_mtx_collision(CPUState* ctx, u32 level, u64 id, u32 matrix) {
    const u32 frame = mem_read32(ctx, 0x801FD934u); /* T009 frame counter */
    if (frame != wario_mtx_seen_frame) {
        wario_mtx_seen_frame = frame;
        for (int i = 0; i < 8192; ++i) wario_mtx_seen_id[i] = 0;
    }
    u32 hash = 2166136261u;
    for (u32 i = 0; i < 12; ++i) hash = (hash ^ mem_read32(ctx, matrix + 4u * i)) * 16777619u;
    u32 slot = (u32)(id ^ (id >> 29)) & 8191u;
    for (int probe = 0; probe < 64; ++probe, slot = (slot + 1u) & 8191u) {
        if (wario_mtx_seen_id[slot] == 0) { wario_mtx_seen_id[slot] = id; wario_mtx_seen_hash[slot] = hash; return; }
        if (wario_mtx_seen_id[slot] == id) {
            if (wario_mtx_seen_hash[slot] != hash) wario_mtx_count(wario_mtx_site[level], 9u, 0u);
            return;
        }
    }
}
static void wario_mtx_debug(CPUState* ctx, int kind) {
    static int mode = -1;
    static const char* path;
    static u32 calls;
    if (mode < 0) { path = getenv("WARIO_MTX_DEBUG"); mode = path && *path ? 1 : 0; wario_mtx_debug_on = mode; }
    if (!mode) return;
    const u32 sp = ctx->gpr[1], src = ctx->gpr[4];
    const u32 temp = (kind == 2 || kind == 3) && (src - sp < 0x4000u || sp - src < 0x100u);
    u32 h = (ctx->lr * 2654435761u ^ (u32)kind * 97u ^ temp) & 4095u;
    for (int probe = 0; probe < 4096; ++probe, h = (h + 1u) & 4095u) {
        WarioMtxSite* s = &wario_mtx_sites[h];
        if (s->count == 0) { s->lr = ctx->lr; s->kind = (u32)kind; s->temp = temp;
            s->r29 = ctx->gpr[29]; s->r30 = ctx->gpr[30]; s->r31 = ctx->gpr[31]; }
        if (s->lr == ctx->lr && s->kind == (u32)kind && s->temp == temp) { s->count++; break; }
    }
    if (++calls % 100000u == 0) {
        FILE* f = fopen(path, "w");
        if (!f) return;
        for (int i = 0; i < 4096; ++i)
            if (wario_mtx_sites[i].count)
                fprintf(f, "%u %08X %u %u %08X %08X %08X\\n", wario_mtx_sites[i].kind, wario_mtx_sites[i].lr,
                        wario_mtx_sites[i].temp, wario_mtx_sites[i].count, wario_mtx_sites[i].r29,
                        wario_mtx_sites[i].r30, wario_mtx_sites[i].r31);
        fclose(f);
    }
}
void wario_mtx_hook(CPUState* ctx, int kind) {
    if (!wario_fps_tagging)
        return;
    wario_mtx_debug(ctx, kind);
    const u32 stack = ctx->gpr[3];
    if (stack != wario_mtx_stack_object) {
        wario_mtx_stack_object = stack;
        for (int i = 0; i < WARIO_MTX_LEVELS; ++i)
            wario_mtx_ids[i] = 0;
    }
    const u32 top = mem_read32(ctx, stack + 8u);
    if (top >= WARIO_MTX_LEVELS)
        return;
    switch (kind) {
    case 1: /* push */
        if (top + 1u < WARIO_MTX_LEVELS) {
            wario_mtx_ids[top + 1u] = wario_mtx_ids[top];
            wario_mtx_site[top + 1u] = wario_mtx_site[top];
        }
        break;
    case 2: /* set top */
        wario_mtx_ids[top] = wario_mtx_source(ctx, ctx->gpr[4]);
        wario_mtx_site[top] = ctx->lr;
        break;
    case 3: { /* top *= m */
        u64 source = wario_mtx_source(ctx, ctx->gpr[4]);
        /* fn_80047F2C (model node renderer) builds every node's matrix in one global scratch
           buffer (0x801CF2C8): the node is identified by the current model [0x801FDA7C] and
           the node counter [0x801FDA74] instead. */
        if (ctx->lr == 0x80047F7Cu)
            source = wario_mtx_mix(wario_mtx_mix(source, mem_read32(ctx, 0x801FDA7Cu)),
                                   mem_read32(ctx, 0x801FDA74u));
        wario_mtx_ids[top] = wario_mtx_mix(wario_mtx_ids[top], source);
        wario_mtx_site[top] = ctx->lr;
        break;
    }
    case 4: { /* load stack[top - depth] */
        const u32 level = top - ctx->gpr[4];
        if (level >= WARIO_MTX_LEVELS)
            return;
        const u64 id = wario_mtx_ids[level] | 1ull; /* never 0 */
        if (wario_mtx_debug_on)
            wario_mtx_collision(ctx, level, id, mem_read32(ctx, stack + 4u) + level * 0x30u);
        mem_write8(ctx, 0xCC008000u, 0x10u);
        mem_write32(ctx, 0xCC008000u, (1u << 16) | 0x0FFEu);
        mem_write32(ctx, 0xCC008000u, (u32)(id >> 32));
        mem_write32(ctx, 0xCC008000u, (u32)id);
        break;
    }
    }
}
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


def pgo_flags(clang, build):
    """CMake cache flags for clang PGO. Paths must be space-free (CMake splits flag strings),
    so the profile is referenced relative to the build folder."""
    # Release-only flags: CMake's compiler self-test builds in Debug from a nested
    # scratch folder, where the build-relative profile path would not resolve.
    base = "/O2 /Ob2 /DNDEBUG"
    if args.pgo_generate:
        runtime = next((clang.parent.parent / "lib/clang").glob("*/lib/windows/clang_rt.profile-x86_64.lib"), None)
        if runtime is None:
            raise SystemExit("clang_rt.profile-x86_64.lib not found next to clang-cl")
        # Linked by name from the build folder (the LLVM path contains spaces).
        build.mkdir(parents=True, exist_ok=True)
        shutil.copy2(runtime, build / runtime.name)
        return ["-DCMAKE_C_FLAGS_RELEASE=" + base + " -fprofile-instr-generate",
                "-DCMAKE_SHARED_LINKER_FLAGS_RELEASE=" + runtime.name]
    if args.pgo_use:
        profile = Path(os.path.relpath(ROOT / args.pgo_use, build)).as_posix()
        if " " in profile:
            raise SystemExit("profile path must not contain spaces relative to the build folder")
        return ["-DCMAKE_C_FLAGS_RELEASE=" + base + " -fprofile-instr-use=" + profile
                + " -Wno-profile-instr-unprofiled -Wno-profile-instr-out-of-date -Wno-backend-plugin"]
    return []


common = ["-DGAME_ID=GWWE01", "-DGENERATED_DIR=" + str(destination), "-DGXRUNTIME_DIR=" + str(upstream / "GXRuntime"),
          "-DCHASSIS_ABI_DIR=" + str(upstream / "Source/Core/Core/PowerPC/StaticRecomp")]
print("Bundle instruction sites:", sites, "REL chunks:", len(new_chunks), flush=True)
if args.clang:
    suffix = "-clang-pgogen" if args.pgo_generate else "-clang-pgo" if args.pgo_use else "-clang"
    build = ROOT / "build" / (args.build_dir or ("module-" + variant + suffix))
    clang = Path(args.clang_cl)
    if not clang.is_file():
        raise SystemExit(f"clang-cl not found at {clang}")
    linker = clang.with_name("lld-link.exe")
    configure = subprocess.list2cmdline(["cmake", "-S", str(template), "-B", str(build), "-G", "Ninja",
        "-DCMAKE_BUILD_TYPE=Release", "-DCMAKE_C_COMPILER=" + clang.as_posix(), "-DCMAKE_CXX_COMPILER=" + clang.as_posix(),
        "-DCMAKE_LINKER=" + linker.as_posix(), "-DRECOMPCORE_MODULE_ENABLE_IPO=OFF", *pgo_flags(clang, build), *common])
    compile_ = subprocess.list2cmdline(["cmake", "--build", str(build), "--parallel", str(args.jobs)])
    script = build.parent / (build.name + "-build.cmd")
    script.write_text(f'@echo off\r\ncall "{vcvars64()}" >nul 2>nul || exit /b 1\r\n'
                      f'{configure} || exit /b 1\r\n{compile_}\r\n')
    with (ROOT / f"reports/build-rel-bundle-{args.build_dir or variant + '-clang'}.log").open("w") as log:
        subprocess.run(["cmd", "/c", str(script)], check=True, stdout=log, stderr=subprocess.STDOUT)
    print(build / "gGWWE01_recomp.dll")
    raise SystemExit(0)
build = ROOT / "build" / (args.build_dir or ("module-" + variant))
command = ["cmake", "-S", template, "-B", build, "-G", "Visual Studio 17 2022", "-A", "x64", *common]
with (ROOT / f"reports/build-rel-bundle-{variant}.log").open("w") as log:
    subprocess.run(command, check=True, stdout=log, stderr=subprocess.STDOUT)
    subprocess.run(["cmake", "--build", build, "--config", "Release", "--parallel", "1", "--", "/nr:false"], check=True, stdout=log, stderr=subprocess.STDOUT)
print(build / "Release/gGWWE01_recomp.dll")
