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
5. **Objects.** Every XF matrix-memory load of the real frame (immediate
   writes and indexed loads to 0x000-0x0FF: GX position and texture matrices)
   is recorded with its values. Loads are matched with frame N-1 by
   (address, length, occurrence). A matched load is replaced in the replay by
   an immediate write of the halfway matrix (element-wise lerp). A pair is
   rejected, so frame N's value is kept, when the rotation part changes by
   >35% or the translation by >25% + 0.5 units. That catches different objects
   and wrapped texture scrolls. Position matrices (PNMTX slots, XF 0x00-0x77)
   loaded under the main camera are pre-multiplied by C^-1, so the projection's
   camera correction cancels and the result is exactly the halfway modelview.
   Greenhorn: 96.5% of loads matched; boss CB41: 99.6% (~300 loads per frame).
   `MODERNGEKKO_WARIO_FPS_OBJECTS=0` interpolates the camera only.
6. **Pacing.** Wario World issues its XFB copy late in each 16.7 ms frame
   (measured: about 15 ms after the previous VI), so the in-between frame can
   only be built just before the next VI. The real frame from that VI is held
   back to half a frame after the in-between one (about 8 ms of extra latency,
   the same trade as Ship of Harkinian). Neither frame is ever slept for on the
   emulation thread. Both are queued and shown when due, either from the GPU
   command loop or, in this runtime's single-thread mode, from inside Dolphin's
   speed-limiter sleep (a hook in `CoreTimingManager::Throttle`), which is idle
   time anyway.

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

- Objects are interpolated through their matrices. Geometry the CPU writes
  directly into vertex buffers (if any particles do this) stays at 60 Hz.
- Normal matrices (lighting) use frame N.
- Objects drawn with the main projection but not in world space (for example a
  3D HUD model, if any) move with the camera correction in the in-between
  frame.
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
