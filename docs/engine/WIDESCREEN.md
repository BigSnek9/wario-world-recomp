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

## WS-008 Pause book items drawn in EFB-pixel viewports (confirmed code)

The pause book page lbl_801BC2C0 (built by fn_8006073C from the pause object
constructor fn_8006DE28) has page components that each set their own
GXSetViewport (fn_8019B500) / GXSetScissor (fn_8019B524) in EFB pixels
(WS-004, 512x448) instead of drawing in the 2D layer:
- fn_8006051C (vtable lbl_801BC2E4, draw slot): the bottom-right row of 5
  slots. Scissor (264, 310, 215, 124) at 0x800605C0; per slot i a 215x215
  viewport at x = 181 + 43*i (lbl_801FE460 = 181, step lbl_801FE468 = 43,
  0x8006062C), y = 512 - 215*obj[+0x20]. Bit i of the rescue mask
  (lbl_801CE3A4 table) picks the Sprite model (obj+0x28) or the jail
  (obj+0x24); both are drawn through the same viewport.
- fn_8005EB6C (lbl_801BC314): the statue/gem scene, viewport 320x320 at
  x 203 or 210 (lbl_801FE3C4/3E4), scissor (274, 25, 194, 276).
- fn_8005AA20 (lbl_801BC1AC), fn_8005C4A0 (lbl_801BC204), fn_8005DDEC
  (lbl_801BC274): 320x320 (or 276x276) viewports at x 210/231 inside the
  same right-page scissor (274, 25, 194, 276); fn_80061044 (lbl_801BC36C):
  scissor (274, 25, 194, 276) and four 276x276 viewports at x 235 and
  lbl_801FE4A8/4B0 (textured quads plus a model; probably the Sprite page with the
  cage scene). Pages seen in a D-pad tour: level page, boss key page,
  treasure and stamp details, Sprite page.
- All six are vtable slot 3 (draw) of components whose constructors are
  reached only from the pause object constructor fn_8006DE28 (created by
  fn_800319A8 with the in-game HUD).
- fn_8006259C / fn_80062970 (lbl_801BE948 and a neighbour) set a full-screen
  viewport (0, 0, 512, 448) with the full scissor; not page-local.
The book art, including the shadow markers printed under the row, is in the
2D layer, so it stays 4:3 in a widened ortho while the viewports keep their
full-screen pixel positions: the row spreads by half/320. Measured on hidden
3x captures of one savestate, in 2D units: row centres = (32.5 + 43*i) EFB px
from the centre * half/256, i.e. 40.6 + 53.75*i at 4:3 and 54.2 + 71.7*i at
16:9 (5th slot past the page edge). The printed markers (slanted shadow
rectangles) are identical in both runs and sit under the 4:3 positions, about
42 + 52.5*i at their middle height, so the original 4:3 row is on its markers.
The figures keep their shape and size in a wide aspect because the projection
they use is the WS-007 perspective, which is synced.
Caution: a savestate made at 16:9 carries the 16:9 2D camera; running it with
the adapter at exactly 4:3 never resyncs it (sync is inert until something is
widened), so the book is squeezed to 3/4 and the row looks too wide even with
original code (also with --reference). Use a 4:3 savestate, or an aspect
just above 4:3 (e.g. MODERNGEKKO_WARIO_ASPECT=1.34) to see the 4:3 layout.

## WS-009 Message board figure drawn in an EFB-pixel viewport (confirmed code)

The hint/message board is fn_8009E5BC (vtable lbl_801C0CB8; constructed by
fn_800A85B0, fn_800AC250 and fn_800EABAC). It builds two parts:
- fn_8009DC84 (vtable lbl_801C0CE8; draw fn_8009DF4C): the parchment and text,
  drawn through the WS-007 ortho (screen manager lbl_801FDB28 +0x2c[0xC]).
  Arguments (0, 0, -48, 0), size 512x160 (r5/r6). fn_8009DF4C translates
  to the board position (+0x24/+0x28), scales by +0x20 (pop-in), draws the
  parchment (fn_8009E090 / fn_8009E104), then translates by the text offset
  (+0x2c/+0x30 = -48, 0) inside the board's matrix and draws the text at
  scale 0.75 (fn_8009E234). The text is therefore board-relative and follows
  the synced WS-007 ortho.
- fn_8009E304 (vtable lbl_801C0CD0; draw fn_8009E52C): the 3D figure, drawn
  through the WS-007 perspective (+0x2c[0x10]). It stores an EFB-pixel
  viewport (336, 160, 128, 128) (lbl_801FEEA0/A4/A8) at +0x24..+0x30 and
  its rounded copy at +0x34..+0x3A, and sets GXSetScissor (0x8009E55C) and
  GXSetViewport (0x8009E578) from them. Centre x 400 of 512 lands near the
  board's right end at 4:3.
With a widened 2D half width the board shrinks to its 4:3 size in the centre
(WS-007), but the pixel viewport stays at 400/512 of the screen width, so at
16:9 the figure moved right onto and past the board's right edge. Fixed like
WS-008 (viewport centre and scissor edges mapped about the EFB centre by
320/half). lbl_801C0CD0 is referenced only by fn_8009E304 (constructor) and
fn_8009E3F0 (destructor), and fn_8009E304 has the single caller fn_8009E5BC,
so the two calls are board-only.
A similar unhooked pattern exists in fn_8009878C (vtable draw of the object
built by fn_80098550, only from fn_80099684 via fn_80090930): viewport
(280, 88, 240, 240), centre x 400. Its screen is not identified; it is left
alone until it is seen.

## WS-010 Stage results paper icons in EFB-pixel viewports (confirmed code)

The results screen fn_80077A88 (called from fn_80078D44) builds the paper
fn_8007669C (vtable lbl_801BF748, draw fn_80076940, WS-007 ortho) and its
icon layer fn_80076B60 (vtable lbl_801BF730, WS-007 perspective; only
caller fn_80077A88). The icon layer's draw fn_80076EDC sets a full-screen
GXSetScissor (0x80076F18) and calls three row helpers, each twice (left and
right column, r5 = 0/1), with EFB-pixel bases from lbl_801FE77C..7A4:
- fn_800770FC: a grid of 64x64 viewports at x = 148.06 + 46.82*(col - 2),
  y = 159.67 / 340.57 + 51.77*(row - 1) (GXSetViewport 0x800771D0); bits of
  the lbl_801CE3A4 rescue table pick the model, as in the pause book row.
- fn_80077400: one 256x256 viewport at x 221.03, y 15.14 / 195.59
  (0x80077438).
- fn_800778C4: 128x128 viewports at x 290.8 + step, y 130.4 / 311.5
  (0x80077974).
The three helpers have no other caller. As with the pause book (WS-008) the
paper art follows the widened 2D layer and stays 4:3 in the centre while
the pixel viewports keep their full-screen positions, so at 16:9 the icons
spread by half/320 (user report, 2026-10-27). Fixed with the WS-008 mapping
at the three viewport calls; the full-screen scissor is left alone.

## Open questions

- Which code writes camera `+0x44` besides fn_80068250 (cutscenes, bosses)?
- Where the camera block's +0x54 matrix is rebuilt from +0x44/+0x48 (needed so
  aspect/FOV edits take effect).
- Whether fn_8007BEAC is the main HUD draw.
