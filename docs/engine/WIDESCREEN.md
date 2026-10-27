# Widescreen, aspect and screen-space findings

All addresses are main.dol (GWWE01 rev 0) virtual addresses. Original values
come from the private dtk disassembly (`generated/analysis/asm`) and can be
re-derived with `python scripts/asm_lookup.py <addr>`. Nothing here is patched
in the baseline build.

## Source of these leads

Dolphin ships a "16:9 Widescreen" Gecko code for GWWE01
(`third_party/ModernGekko/vendor/dolphin/Data/Sys/GameSettings/GWWE01.ini`).
It is not enabled by the recomp. Each write was compared with the original
instruction/data at that address (2026-10-26). The Gecko code is evidence of
*where* a community author found 4:3 assumptions; it is not proof that the list
is complete or that every site is understood.

## WS-001 Perspective aspect constant (confirmed data, probable role)

- `lbl_801FE5B0` (.sdata2) = 1.3333334 (4:3). Gecko writes 1.7777778 (16:9).
- Loaded once, in `fn_80068250` at 0x800682E0 and stored to camera-parameter
  block `[obj+0x14]+0x44`. Callers: `fn_8006B29C`, `fn_8006C118`.
- Neighbouring constants stored into the same block by `fn_80068250`:
  `+0x38` 0.125, `+0x3C` 1024.0, `+0x40` 1008.0, `+0x44` 1.3333 (aspect),
  `+0x48` 45.0, `+0x4C` 0.025, `+0x34` -1.0. 45.0 next to the aspect is very
  vertical FOV in degrees. **Confirmed 2026-10-26** by reading the live camera
  block: its +0x54 perspective matrix matches cot(45/2)/aspect exactly
  (CAMERA.md CAM-002).
- Mod approach: replace aspect with the host aspect, keep the 45 degree vertical
  FOV (Hor+). Because this is a default copied into a per-camera block, cutscene
  or special cameras that write `+0x44` themselves must also be found.

## WS-002 2D layer half-width (confirmed data, probable role)

- `lbl_801FE6CC` = 320.0 (half of 640). Gecko writes 426.6667 (= 320 * 4/3).
- Loaded in `fn_8006F7CC` at 0x8006F7E8; caller `fn_8007DF18`.
- Probable role: half-width of an orthographic 2D/HUD projection. Widening it
  stretches the 2D coordinate space so 4:3-authored HUD elements keep their
  shape.

## WS-003 HUD/screen-space integer layout sites (confirmed original code)

| Address | Function | Original | Gecko replacement | Note |
|---|---|---|---|---|
| 0x80031AC4 | fn_800319A8 | li r5,-0x118 (-280) | li r5,-386 | left HUD x offset |
| 0x800809D0 | fn_80080954 | subfic r6,r7,-0x140 (-320) | subfic r6,r7,-426 | screen-left edge |
| 0x8007F7D8 | fn_8007F7A4 | li r5,0x140 (320) | li r5,427 | caller fn_8007BEAC |
| 0x8007EC24 | fn_8007EBF0 | li r7,0x140 (320) | li r7,427 | caller fn_8007BEAC |
| 0x80081528/38/5C | fn_800814E0 | mr r4,r31 | addi r4,r31,-106 | shift left by 106 px |
| 0x80080BE8 | fn_80080BA4 | li r7,0x110 (272) | li r7,378 | caller fn_800319A8 |
| 0x80082EE0 | fn_80082E4C | li r5,0x118 (280) | li r5,386 | caller fn_80082D84 |
| 0x800637A8 | fn_8006370C | extrwi r31,r3,15,16 (value/2) | li r31,191 | computed half-width replaced by constant |
| 0x80063198 | fn_80063154 | extrwi r30,r3,15,16 | li r30,135 | caller fn_80062F3C |
| 0x800631AC | fn_80063154 | extrwi r7,r3,15,16 | li r7,9 | caller fn_80062F3C |
| 0x80063318 | fn_800632DC | extrwi r30,r3,15,16 | li r30,18 | caller fn_80062F3C |
| 0x800634C4 | fn_8006348C | clrlwi r0,r3,16 | li r0,450 | caller fn_80062F3C |
| 0x8006F14C/F1F0 | fn_8006EF1C | li r7,0xC (12) | li r7,9 | |
| 0x8006F3C0 | fn_8006F3A8 | slwi r29,r7,1 | li r29,24 | caller fn_8006EF1C |
| 0x8006F530 | fn_8006F510 | mr r27,r7 | li r27,9 | caller fn_8006EF1C |

The pattern 320 -> 427 and 280 -> 386 is a multiply by 4/3 (16:9 / 4:3).
The fn_80062F3C / fn_8006EF1C groups replace *computed* values with constants;
those look like text/glyph layout and are the riskiest to reuse for arbitrary
aspect ratios (the replacement is only right for 16:9). Roles are **speculative**
until each function is traced.

Pause-menu signal (confirmed code and memory): lbl_801FD930 bit 0x8 is set
from book open (state fn_8006CB04) until the close state finishes
(fn_8006DC4C), through the counter lbl_801FD940 (fn_8003195C, no other
callers); bit 0x4 (counter lbl_801FD93C, fn_80031910) is the general
update freeze, also set by other screens (fn_80059E14, fn_80098C50, ...).
The recomp's draw-time HUD edge shift uses DX 0 while bit 0x8 is set,
keeping the HUD inside the 4:3 book.

## Host side (runtime, not game code)

- Presentation is forced to 4:3 (`AspectRatio=2` ForceStandard, widescreen
  hack off) by `scripts/configure_baseline.py`. Dolphin's Auto mode switches
  aspect heuristically; the Dolphin wiki reports this game flipping between
  4:3 and 16:9 at the World 1 boss under Auto. That matches the human report of
  "transient stretching" before the baseline fix (see KNOWN_ISSUES.md).
- A real widescreen mod therefore needs BOTH guest changes (WS-001..003) and
  host presentation set to the matching aspect.

## WS-004 Render target is 512x448 (confirmed runtime value)

Viewport globals 0x801FDA20/0x801FDA24 hold 512.0 x 448.0 in Greenhorn Forest
(CAMERA.md CAM-003). The game renders 3D into a 512-wide EFB area and the video
interface scales it to the 640-wide display, so pixels are not square and the
"4:3" aspect constant describes the displayed picture, not the EFB grid. A
widescreen mod must keep aspect (+0x44) = displayed width/height; a higher host
internal resolution scales this 512x448 target. 2D layout uses a separate
640-based space (WS-002).

## WS-007 Fixed screen cameras (confirmed code, probable role)

fn_8007DF18 (which also builds the two 2D cameras via fn_8006F7CC) creates:
- fn_80067AA8(f1, f2): C_MTXOrtho, top 224, left -320, near 1, far 256
  (lbl_801FE580/584/57C/588); called twice with depth ranges (0.75, 1.0) and
  (0, 0.25) stored at +0x50/+0x54. Vtable lbl_801BEB28; apply fn_80067C34
  (GXSetViewport from the viewport globals, then GXSetProjection(obj+0x10) at
  0x80067D1C).
- fn_80067D50: C_MTXPerspective(fovy 30, aspect = lbl_801FDA20 / lbl_801FDA24
  = 512/448, near 1, far 256). Vtable lbl_801BEAF8; apply fn_80067F44
  (GXSetProjection at 0x8006801C).
Neither reads HC-0007, so in a wide aspect anything drawn through them
stretches horizontally. The hint/message boards (parchment, text and the 3D
figure in them) are drawn this way (human screenshot, 2026-10-27).
C_MTXPerspective (fn_8019C618) stores m11 = cot(fovy/2) and m00 = m11 / aspect.

A third C_MTXPerspective call (fn_8015C8C8, caller fn_800302CC) uses fixed
fovy 50 and aspect 4/3 (lbl_80201928..34); its role is unknown.

## Open questions

- Which code writes camera `+0x44` besides fn_80068250 (cutscenes, bosses)?
- Where the camera block's +0x54 matrix is rebuilt from +0x44/+0x48 (needed so
  aspect/FOV edits take effect).
- Whether fn_8007BEAC is the main HUD draw.
