# FPS unlock plan

Status 2026-10-26: research complete enough to choose a design; nothing
implemented. Must stay optional and off by default (the accurate baseline is
the original 59.94 Hz loop).

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

## Chosen design: keep the simulation at 59.94 Hz, interpolate presentation

Same idea as Ship of Harkinian's frame interpolation, adapted to GX:

1. The guest runs exactly as today (one update + one draw per VI retrace).
   Simulation, input latching and audio are untouched.
2. Record each guest frame's GX command stream on the host. ModernGekko
   already contains Dolphin's FifoRecorder/FifoPlayer (Core/FifoPlayer), which
   capture per-frame FIFO data plus referenced memory; the video backend sees
   every XF register/matrix load (OpcodeDecoding, LoadIndexedXF).
3. Between real guest frames N-1 and N, render extra host frames by replaying
   frame N's stream with transforms replaced by lerp/slerp(N-1, N, t):
   - projection (GXSetProjection fn_8019B0FC uploads from camera +0x54),
   - view (camera +0x98, built by C_MTXLookAt in fn_80042714 from eye +0x14,
     up +0x20, target +0x2C - interpolate those inputs, then rebuild),
   - per-draw position/normal/texture matrices, matched between the two frames
     by draw order + matrix slot, falling back to frame N when the structure
     differs (spawns, despawns, cuts).
4. Present at the display rate; one frame of display latency is added (frame
   N is shown only once N+1 exists), as in Ship of Harkinian.

## Work items (in order)

1. Measure with a host-side FIFO tap: XF matrix loads per frame (immediate vs
   indexed), draw calls, EFB copies and display-list calls in Greenhorn Forest,
   a boss and the hub (the static search for GXLoadPosMtxImm-style writes found
   no simple pattern; the game may use indexed loads or display lists).
2. Camera-only prototype: render each guest frame twice with the camera
   interpolated and everything else from frame N.
3. Per-object matrix matching for actors (Wario, enemies).
4. Edge cases: EFB copies used as textures (shadows, water, bloom/god rays)
   re-executed in replayed frames; 2D HUD/fades drawn from frame N; no
   interpolation across camera cuts and scene changes (large eye/target jumps,
   module loads T004).
5. Pacing: present thread driven by the host display; guest frames stay on
   the emulated VI clock.

## Risks

- Host CPU for matching; the emulation thread has ~45% headroom after PGO.
- CPU-written particle vertices cannot be interpolated by matrix lerp and stay
  at 60 Hz motion (acceptable first step).
- Game code reading the EFB only happens on real frames.
