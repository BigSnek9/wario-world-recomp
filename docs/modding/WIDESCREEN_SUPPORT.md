# Widescreen support

Status 2026-10-27: done, optional (in-game menu Aspect: Auto, Original 4:3,
16:9, 16:10, 21:9, 32:9). Hor+ view, edge HUD, and the pause book, message
boards and results paper keep their 4:3 shape. WS-009 and WS-010 are not yet
confirmed in a capture (../progress/KNOWN_ISSUES.md KI-008). The plan and
implementation notes follow in the order they were written.

Findings: ../engine/WIDESCREEN.md (WS-001..010).

## Strategy (Hor+)

1. Camera: set the aspect default HC-0001 (0x801FE5B0) to `w/h` of the output;
   keep vertical FOV HC-0002 unchanged so 4:3 framing is preserved vertically.
   Find any other writers of camera block `+0x44` (cutscenes/bosses) first.
2. 2D space: set HC-0007 (0x801FE6CC) to `320 * (w/h) / (4/3)` so the
   orthographic 2D space widens instead of stretching.
3. HUD anchors: the WS-003 immediates move left/right HUD elements out to the
   new edges. For arbitrary aspects compute `x * (w/h) / (4/3)` instead of the
   16:9 constants. The fn_80062F3C / fn_8006EF1C group replaces computed
   values with constants that are only right for 16:9 - understand them first.
4. Host: set presentation aspect to match (custom aspect or Stretch to window
   with the guest doing the correction). Must not use Dolphin's Auto heuristic.

## Implementation route in the recomp

Prefer a host-side hook at the generated function level (func_8006xxxx) or a
data write at boot from a mod config, not edits to generated C. Keep the
original bytes for the baseline and record every changed address.

## Tests required

- Screenshot sweep: title, hub, Greenhorn Forest, pause menu, HUD at 4:3/16:9/21:9.
- Check sprites/fades that cover the screen (full-screen quads may assume 640).
- Verify culling at screen edges (wider view may expose popped objects).

## Update 2026-10-26: where the camera values are consumed

fn_80042714 (CAM-004) rebuilds the projection every camera update from block
+0x44 (aspect) and +0x48 (FOV), and also builds the culling side planes from
the same aspect. So a Hor+ mod can write aspect into the active camera block
([0x801FDA50]+0x44) or the default HC-0001 and both projection and culling
follow; no separate culling patch is needed for the side planes. HUD (WS-003)
and the 2D half-width (WS-002) still need their own changes.

## Implemented (2026-10-26; the launcher pickers are now the in-game menu)

- Runtime: MODERNGEKKO_WARIO_ASPECT=auto|w:h (scripts/tool_fix_wario_aspect.py)
  rewrites HC-0001, HC-0007 and the live camera +0x44 after every presented
  frame; "auto" follows the window/backbuffer aspect (GFX AspectRatio=Stretch),
  fixed ratios use AspectRatio=Custom. Resolution "auto" leaves the EFB scale
  to Dolphin's window-size mode (InternalResolution=0).
- Choice: originally launcher pickers, now the in-game menu's Resolution and
  Aspect (IN_GAME_MENU.md); "Original" choices restore the accurate native
  1x / 4:3 values. Hidden tests use the baseline unless they set
  `MODERNGEKKO_WARIO_ASPECT`.
- Verified hidden at 16:9: Greenhorn Forest Hor+ (same vertical framing, more
  scenery at the sides, no missing geometry at the new edges, live camera from
  a savestate adapts), title/file select/hub 2D art keeps its proportions, HUD
  stays undistorted in the centre 4:3 area.
- WS-005/WS-006 (2026-10-26): the screen-overlay constructors fn_8007F7A4
  (solid fade quad, drawn by fn_8007FA2C; the file select -> hub white fade
  that left side strips unfaded) and fn_8007EBF0 (textured EFB-copy feedback
  quad, drawn by fn_8007EE8C; drawn at +-320 inside the widened ortho it shrank
  each frame's copy by 0.75 toward the centre, giving the loading-coin trails)
  store the half width (always the constant 320) at object +0x30. Since
  2026-10-27 the constructors are original again and the draw-time reads
  (0x8007EEBC, 0x8007FA6C/7C/8C/A4) map 320 to `wario_fullscreen_half_width`
  (scripts/build_rel_bundle.py HUD_EDGE_SITES), so overlays built before an
  aspect change or restored from a savestate still cover the screen.
- WS-003 HUD anchoring (2026-10-27, scripts/build_rel_bundle.py
  HUD_EDGE_SITES): edge HUD x positions get DX = wario_fullscreen_half_width
  - 320 (0 in 4:3) at draw time, no new runtime variable. Left: hearts and the
  bottom-right stage counter row (fn_80082344 sprite rows, x read at
  0x800825B0/BC, 0x80082600, 0x800828C4, float getter 0x800824A0; pushed out
  by the sign of x), the coin panel (fn_80080954 edge -320 at 0x800809D0) and
  the top-left counters (fn_800814E0, 0x80081528/38/5C). Right: the
  fn_80080BA4 indicator (+0x36 read at 0x80080E78, 0x8008101C, float at
  0x80081148). The Gecko constants at 0x80031AC4/0x80080BE8/0x80082EE0 are
  constructor-time and were not used. The 2D camera bakes HC-0007 into its
  ortho only when built (fn_8006F7CC), so the apply routine fn_8006F954
  (0x8006F978) now recomputes m[0][0] = 2*(1/(2*HC-0007)) from the live value
  once the adapter has widened anything (never in a 4:3-only session).
  The fn_80062F3C / fn_8006EF1C Gecko groups (texture half-widths and glyph
  widths replaced by 16:9 constants) compensate an anamorphic stretch and are
  not needed with the widened ortho. Verified hidden at 16:9 and 32:9 with the
  conditional elements forced visible; 4:3 HUD positions unchanged.
  Pause book (2026-10-27): the book is drawn at 4:3 in the centre, and the
  hearts and coin panel shown with it were pushed outside it. (The Sprite /
  jail row in the book did not move with or without this; it is drawn in
  EFB-pixel viewports, see WS-008.) DX is now 0 while the game's own pause-menu bit is set: bit 0x8 of
  lbl_801FD930 (main-loop state word; paused 0xF, playing 0x3), driven by the
  counter lbl_801FD940 in fn_8003195C. Its only callers are the pause-menu
  states fn_8006CB04 (open, +1) and fn_8006DC4C (close finished, -1), and
  the HUD reads the same bit through fn_8003199C (fn_80082B4C). Evidence:
  hidden MEM1 diff paused/playing/paused on a Greenhorn Forest state. The
  bit is read only when the screen is wide, so 4:3 is unchanged. Other
  freezes (the other fn_80031910 callers set bit 0x4 only) keep edge anchoring.
- WS-007 message boards (2026-10-27): fn_8007DF18 builds two more screen
  cameras next to the 2D layer, and they ignored the widened half width:
  - fn_80067AA8: C_MTXOrtho, +-320 x +-224; applied by fn_80067C34.
  - fn_80067D50: C_MTXPerspective, 30 degrees, aspect = viewport 512/448;
    applied by fn_80067F44.
  They draw the hint/message boards (parchment, text and the 3D figure), which
  a wide screen stretched across the whole width. At their
  GXSetProjection(obj+0x10) calls (0x80067D14 and 0x80068014, HUD_EDGE_SITES):
  - the ortho gets the 2D layer's m[0][0];
  - the perspective gets m00 = m11 / (aspect * half/320).
  Boards keep their 4:3 shape, centred. The fix is inert until the adapter
  widens anything, and 4:3 restores the exact original values. Not yet seen
  in a hidden run (no state with a board open); full-screen draws through
  these cameras, if any, would now cover only the centre 4:3.
- WS-008 pause book pages (2026-10-27): the bottom-right row of 5
  slots on the pause book's right page (rescued Sprite model or jail) is drawn
  by fn_8006051C, one 215x215 EFB-pixel GXSetViewport per slot at
  x = 181 + 43*i (0x8006062C) inside GXSetScissor(264, 310, 215, 124)
  (0x800605C0); see ../engine/WIDESCREEN.md WS-008. Pixel positions ignore the
  widened 2D layer, so at 16:9 the row spread to 4/3 of its width while the
  book and the shadow markers printed on its page stayed 4:3, and the last
  jail hung past the page edge. The other page components do the same
  (statue/gem scene, boss key, treasure and stamp details, the Sprite page
  with the cage scene), so scripts/build_rel_bundle.py (BOOK_SCISSOR_CALLS /
  BOOK_VIEWPORT_CALLS, added to HUD_EDGE_SITES) hooks every
  GXSetScissor/GXSetViewport call of the book's page components:
  scissor 0x8005AAB0, 0x8005C4F4, 0x8005DE1C, 0x8005EBA0, 0x800605C0,
  0x80061084; viewport 0x8005AAD8, 0x8005C51C, 0x8005DE40, 0x8005EBFC,
  0x8005EC74, 0x8006062C, 0x800611F8, 0x800612BC, 0x80061384, 0x80061490
  (draw methods fn_8005AA20, fn_8005C4A0, fn_8005DDEC, fn_8005EB6C,
  fn_8006051C, fn_80061044). Before each call the viewport centre (f1 + f3/2)
  and the scissor edges (r3, r3 + r5) are mapped about the EFB centre by
  320/half, which restores the 4:3 layout in the centred book: every Sprite
  sits on its marker again, as in the original at 4:3. Viewport size is kept;
  the content's projection is the synced WS-007 perspective, so size and
  shape already match 4:3. Half width 320 computes exactly the original
  values. All six components are constructed only from the pause object
  constructor fn_8006DE28 (via fn_8005B334, fn_8005CB74, fn_8005E0B4,
  fn_8006073C, fn_800615E8), so the hooks are unconditional (no pause-bit
  gate). fn_8006259C / fn_80062970 set a full-screen viewport (0, 0, 512, 448)
  and are left alone.
  Verified hidden (savestate 112331_CF11, D-pad page tour, 2 s captures,
  module-ws008-pages): Greenhorn Forest and Greenhorn Ruins level pages
  (statue, gems, Sprite row), DinoMighty's Showdown key page, the treasure
  details (Ruby, "?"), the stamp details (boss, heart, treasure) and the
  Sprite page (cage scene with tutorial text) all match the 1.34-aspect
  (4:3 layout) run inside the book at 16:9; nothing crosses the page edge.
  Gameplay HUD capture (112627_AR11) unchanged (differences only in the
  animated scene).
  An earlier report that the original also overhangs at 4:3 came from running
  a 16:9 savestate at 4:3: the savestate's 2D camera stays 16:9 there, which
  squeezes the book (WS-008 caution in the engine doc).
- WS-009 message board figure (2026-10-27): with WS-007 the board is 4:3 and
  centred, but its 3D figure (playtest report: the small figure sat over the
  board's right edge at 16:9) is drawn by fn_8009E52C, the draw method of the
  figure part fn_8009E304 of the board fn_8009E5BC, in a fixed EFB-pixel
  viewport (336, 160, 128, 128) with a matching scissor. Hooked like WS-008:
  scissor 0x8009E55C and viewport 0x8009E578 (BOARD_SCISSOR_CALLS /
  BOARD_VIEWPORT_CALLS in scripts/build_rel_bundle.py). Board-only: the
  figure vtable lbl_801C0CD0 is used only by fn_8009E304 / fn_8009E3F0, and
  fn_8009E304 is called only by fn_8009E5BC. The board text is drawn in the
  board's own matrix (offset -48, 0, scale 0.75) through the synced WS-007
  ortho, so it is board-relative and needs no change. At 16:9 the figure
  centre maps from EFB x 400 to 256 + 144 * 320/half = 364, i.e. 180 ortho
  units right of centre, the same place as at 4:3 (board half width 256).
  Not yet seen in a hidden capture: no savestate with a board open was found
  (CF/AR/AP/CB/COP states and probe walks through the hub into Greenhorn
  Forest showed none). Pause book and gameplay HUD captures are unchanged
  against the WS-008 behaviour (states 112331_CF11, 112627_AR11).
- WS-010 stage results paper (2026-10-27): the results screen's icon layer
  (fn_80076B60, draw fn_80076EDC) draws its icons in EFB-pixel viewports,
  like the pause book, through three helpers: fn_800770FC (64x64 grid,
  0x800771D0), fn_80077400 (256x256, 0x80077438) and fn_800778C4 (128x128,
  0x80077974). Playtest report: icons misaligned the same way as the pause book.
  The three viewport calls get the WS-008 mapping (RESULTS_VIEWPORT_CALLS);
  the helpers are called only from fn_80076EDC, whose object is built only by
  the results screen fn_80077A88. The full-screen scissor at 0x80076F18 is
  left alone. Not yet seen in a hidden capture: no savestate near a stage
  clear exists in private/play-sessions (states are taken 25 s after an
  area's first load; none follows a boss defeat).
