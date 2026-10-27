# FPS unlock (frame interpolation)

Status 2026-10-26: **implemented (camera + objects), optional, off by default** (launcher checkbox
"Smooth 120 FPS", runtime env `MODERNGEKKO_WARIO_FPS=1`). The accurate baseline
is the original 59.94 Hz loop; with the option off, nothing below runs.
Runtime change: `scripts/tool_fix_wario_fps.py` (applied by
`scripts/apply_tool_fixes.py`).

## Why simply running faster is wrong

Everything mapped so far advances once per main-loop frame with no delta time.
Running the loop at 120 Hz would make the game 2x faster: physics, enemy AI,
animations, timers, the worker tick (T008), the soft-reset hold (T009), the
title damping (T006) and opening countdowns (T007). Rescaling each of those is
a rewrite of the game, not a recompilation enhancement.

| ID | System | Coupling |
|---|---|---|
| T001 | main loop | waits for each VI retrace (0x801FE00C) |
| T002 | controller sampling | SI sampling rate tied to video |
| T006/T007 | title/opening modules | fixed-step per update, no delta time |
| T008 | message-loop worker | one tick message per main-loop frame (0x801FDAE4/E8) |
| T009 | soft reset / frame counter | B+X+Start needs >10 frames + 30-frame countdown; 0x801FD934 +1/frame |
| CAM-004 | camera | projection/view rebuilt per camera update |

## What was built: simulation at 59.94 Hz, presentation at ~120 Hz

The guest runs exactly as before. The video thread renders one extra frame
between each pair of real frames with the camera halfway between them.

1. **Record.** Every GPU command of a frame is appended to a buffer from
   `OpcodeDecoder::RunCallback::OnCommand` (display-list contents inline,
   `CALL_DL` skipped, as Dolphin's FIFO recorder does). At each XFB copy, the
   BP/CP/XF registers and TMEM are snapshotted as the next frame's start state
   (as a register-load command list, same register set as FifoPlayer).
2. **Camera.** When the frame uploads a perspective projection equal to the
   active camera's (`[0x801FDA50]+0x54`, CAM-002), the camera's eye (+0x14),
   up (+0x20) and target (+0x2C) are read from guest RAM. This happens while the
   CPU is still building that frame, so the values match what was drawn.
3. **Replay.** At the XFB copy of frame N, if N-1 and N both had the main
   camera and no cut happened (eye or target moved >150 units, or the view
   direction turned >~25 degrees), the EFB is cleared like the copy does,
   the start state is restored and frame N's commands are run again. Draws
   using the main projection get `P * C`, where
   `C = LookAt(lerp(N-1, N, 0.5)) * LookAt(N)^-1` (the same place Dolphin's
   free-look camera applies its view). Orthographic draws (HUD, fades) and other
   projections are untouched. During the replay, PE finish/token interrupts are
   not raised, XFB copies are skipped and no cycles are charged, so the guest
   cannot see it.
4. **Copy.** The replayed EFB is copied into a private texture-cache entry
   (no guest RAM write, not registered by address), then presented.
5. **Objects (game-level identities).** The engine draws every model through one
   matrix stack (object at `[0x801FDA38]`; methods fn_80047990 push, fn_800479E4 pop,
   fn_800479F4 set, fn_80047A5C multiply, fn_80047A90/B44/C18/CEC load into a GX
   slot via GXLoadPosMtxImm fn_8019B270). The recompiled module hooks those
   methods (scripts/build_rel_bundle.py `MATRIX_STACK_HOOKS`, helper
   `wario_mtx_hook` in module_export.c) and keeps a shadow identity per stack
   level:
   - push copies the identity;
   - set and multiply mix in the source matrix's address (persistent per object
     or bone) and the call site;
   - the model node renderer fn_80047F2C builds every node in one global scratch
     buffer, so there the current model `[0x801FDA7C]` and node counter
     `[0x801FDA74]` are mixed in;
   - sources on the guest stack use the caller's non-volatile pointer registers.
   On each load the identity is written into the GX stream as a 2-word XF write
   to unused XF memory (0x0FFE) right before the matrix. The video side pairs
   matrices between frames by that identity (plus its repeat count within the
   frame) instead of guessing. Untagged matrices keep frame N (camera only).
   Tagging is off unless the runtime sets the module export
   `wario_fps_tagging`, so the default GX stream is the original.
   Each matched main-camera matrix is interpolated in the frame of reference it
   moves less in. World space (static and world-moving objects) loads
   `lerp_t(D * MV_N-1, MV_N)`. Camera space (heat haze and other effects that
   follow the camera) loads `C^-1 * lerp_t(MV_N-1, MV_N)`, so the camera
   correction does not drag it along. Matrices identical in N-1 and N while the
   camera moved, tagged or not, are screen-locked and stay in place.
   For world space, matched main-camera matrices load `lerp_t(D * MV_N-1, MV_N)`
   (D = V_N * V_N-1^-1), so a static object gets exactly MV_N. Texture
   matrices are never blended.
   Measured: all position-matrix loads tagged in the hub, boss and Greenhorn.
   Identities repeating within a frame with different matrices: 0 in the boss
   and Greenhorn, 1.8% in the hub (one effect drawing the same object several
   times per frame in a fixed loop, where repeat order pairs correctly).
   Diagnostics: `WARIO_MTX_DEBUG=<file>` (module call-site histogram and
   collision sites), scripts/fps_flicker_check.py (blob outliers vs
   camera-only), scripts/fps_matrix.py.
6. **Pacing.** Wario World issues its XFB copy late in each 16.7 ms frame
   (measured: about 15 ms after the previous VI), so the in-between frame can
   only be built just before the next VI. The real frame from that VI is held
   back to half a frame after the in-between one (about 8 ms of extra latency,
   the same trade as Ship of Harkinian). Neither frame is ever slept for on the
   emulation thread. Both are queued and shown when due, either from the GPU
   command loop or, in this runtime's single-thread mode, from inside Dolphin's
   speed-limiter sleep (a hook in `CoreTimingManager::Throttle`), which is idle
   time anyway.
   Each in-between frame is queued as soon as its replay finishes, and frames
   already due are shown between replay steps. Every in-between frame is at
   least one interval after the previous one, whether that one is still queued
   or already shown (2026-10-27).
   - Underground levels (the trapdoor rooms, archive UGR) finish their frame
     about 11 ms after the previous real frame. Before this fix, the overdue
     in-between frames went out back to back. At 4x, 26% of presents were on
     pace and 825 were bunched; after it, 79% were on pace and 49 bunched. The
     human described the effect as motion blur.
   - Real frame source (2026-10-27, the main afterimage bug):
     - The game double-buffers its XFB, so the VI that follows frame N's XFB
       copy still shows frame N-1.
     - The held "real" frame used to be that VI image, so after the
       in-between frames leading up to N the screen stepped back to N-1 once
       per game frame. The human saw doubled edges on everything moving
       (photo); static dumps of the in-between frames could not show it.
     - Frame N is now copied privately at its own XFB copy (before the
       replays) and shown in the VI's place (Presenter::WarioSetRealCopy).
       Frames that are not interpolated keep the VI image.
     - Found with MODERNGEKKO_WARIO_FPS_PRESENT_DUMP=<dir>, which saves the
       frames actually presented, in order. The real frame matched the
       in-between t=3/4 of the previous group: difference 0.13, against 0.55
       for the group just before it.
     - After the fix, the in-between -> real steps are even (about 0.15).
     - The step from a real frame into the next group stays larger: content
       the game updates only at 60 Hz (untagged draws, particles, texture
       animation) moves forward there, never backward.
   - VSync (2026-10-27): turned on while interpolating, if multiplier x
     59.94 <= refresh + 1 Hz (re-read every 2 s), and restored after.
     - Reason: frames paced by the clock without VSync drift against the
       refresh, so some refreshes get two new frames and others none. The
       human reported afterimages on moving geometry at 4x on a 239 Hz screen.
     - Speed: full in hidden runs (hub 0.99, UGR 0.997, 3x Vulkan).
     - Present-call gaps get less even, because presents now block on the
       display; the display itself is the real pacer.
     - Not yet verified by eye.
     - Settings: menu `VideoCommon::g_wario_vsync_mode` (1 = off); debug bit
       8 skips it.
   - Adaptive budget (2026-10-27):
     - Behaviour: when the game frame period (smoothed) goes above 17.4 ms,
       the multiplier cap drops by one, down to 1 (= no in-between frames).
       It rises again after 60 game frames on time. Heavy moments then trade
       smoothness for speed instead of slowing the game (human report: hub
       charge dash).
     - Why: every in-between frame is a full re-render on the emulation
       thread, and VSync presents wait for the display.
     - Stats: budget, budget_reduced, skipped_budget.
     - Hidden 4K runs: 4x with VSync stays at full speed. A hidden window
       blocks on VSync more than a real screen does, so the cuts there
       overstate what a player sees.
     - The player's display is 239.991 Hz (QueryDisplayConfig), above
       4 x 59.94.
   - Diagnostics: MODERNGEKKO_WARIO_FPS_TRACE=<file> logs every pacing event
     with a timestamp: C copy, Q queued, M/R in-between/real shown, V VI swap,
     H real held, r real shown at the VI.

## Measurements (hidden runs, prof runner, OpenGL, PGO module)

| Scene | In-between frames | Gaps 6-10 ms | Speed min (off -> on) |
|---|---|---|---|
| Greenhorn Forest walk/punch (40 s) | 1790 / 1800 frames | - | 0.999 -> 0.985-0.999 |
| World 4 boss CB41 (45 s) | 2094 / 2100 | 3833 / 4079 (94%) | 1.000 -> 0.992 |
| World 2 boss CB21 (45 s) | 2094 / 2100 | - | 0.999 -> 0.999 |

- Replay fidelity: with `MODERNGEKKO_WARIO_FPS_IDENTITY=1` (replay with no
  camera change) the replayed image equals the real frame pixel-for-pixel in
  15 of 17 samples. The two that differ are the stage-entry white afterimage
  effect, which feeds the previous frame back in as a texture.
- Earlier versions slept to pace frames. Sleeping to hold the real frame cost
  7-9% in boss arenas; sleeping before the in-between frame cost up to 30% in
  the hub (0.70-0.76; this runtime runs CPU and GPU on one thread). Queuing
  both frames removed it: hub 1.000 (99% of gaps 6-10 ms), boss CB41 0.999,
  Greenhorn 0.992, with camera + object interpolation on.
- `MODERNGEKKO_WARIO_FPS_DEBUG` bits isolate pacing (1 = no wait, 2 = don't
  show in-between frames, 4 = don't hold real frames).

## Diagnostics

- `MODERNGEKKO_WARIO_FPS_STATS=<absolute file>`: counters every 300 frames
  (interpolated, skipped cut/no camera/late, mid offset, held-frame lateness,
  present-gap histogram).
- `MODERNGEKKO_WARIO_FPS_DUMP=<absolute dir>`: saves every 120th real and
  in-between frame pair as PNG.
- `MODERNGEKKO_WARIO_FPS_IDENTITY=1`: replay without the camera change.

## Known limits

- Objects are interpolated through their tagged matrices. Geometry the CPU writes
  directly into vertex buffers (if any particles do this), and anything drawn
  without the matrix stack, stays at 60 Hz.
- Normal matrices (lighting) use frame N.
- Screen-copy effects (afterimage, blur) are isolated: the replay sees the
  start-of-frame copies and the real copies are restored afterwards.
- If the game changes a buffer that frame N used (indexed matrices, vertex
  arrays) before the video thread reaches the copy, the replay uses the newer
  data. Not seen in testing.
- Needs VSync off (the launcher sets it) and is best on a 120 Hz+ display.
- Camera cuts and loading screens show only the real 60 Hz frames.

## Next steps

1. Higher multiples (180/240 Hz) by replaying at t = 1/3, 2/3, ... when the
   video thread has the headroom.
2. Pacing on a separate present thread (Vulkan), to drop the 8 ms delay.

## HD texture streaming (2026-10-27, scripts/tool_fix_hd_texture_streaming.py)

The hub / charge-dash slowdowns also happened at 60 fps. The cause was the
player's HD pack, not frame generation:
- the pack is 239 PNGs, 150 of them 4096x4096 (9.7 GB decoded);
- Dolphin decodes them on its asset loader threads, but creates and uploads
  each texture on the emulation thread the first time it is drawn.

Each frame now uploads at most 32 MB of HD texture data (always at least one
texture; MODERNGEKKO_HD_UPLOAD_MB overrides the limit). Past that, the
original texture is shown for a frame or two and the HD version replaces it
through the existing DidLinkedAssetsChange reload.

Hidden hub run at 4K with the pack, frame gen off:

| Version | Min speed | Slow samples |
|---|---|---|
| Before the fix | 0.838 | 14 |
| After the fix | 0.998 | 0 |
| After the fix, 4x frame gen | 0.996 | 0 |

Dual core (Core.CPUThread=True) is not an option yet: it desyncs the GPU FIFO
at once ("Unknown Opcode") with the static recomp.
