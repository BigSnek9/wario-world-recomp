# FPS unlock plan

Ledger: ../TIMING.md (T001-T007). Summary of what must hold:

- Gameplay update count is tied to the VI retrace wait in main (T001,
  0x8002FD2C -> 0x801A87C4). Updates are fixed-step: title damping (T006) and
  opening countdowns (T007) have no elapsed-time argument.
- Therefore simply running the loop faster speeds the game up. The safe route
  is: keep simulation at 59.94 Hz on the guest clock and render extra frames by
  interpolating object/camera transforms between the last two simulation
  states (presentation-only).
- Inputs must still latch at original SI poll times (T002).

Open work: identify where actor transforms and the camera matrix are produced
per update (needed for interpolation); audit particle/animation updates and
any per-frame counters. No code changed.

## Update 2026-10-26: camera interpolation hook

The camera's per-update inputs are block +0x14 (eye), +0x20 (up), +0x2C
(target), turned into the view matrix +0x98 by C_MTXLookAt inside
fn_80042714 (CAM-004). A presentation-only interpolation layer can lerp
eye/target between the last two simulation updates and rebuild +0x98 for extra
rendered frames without touching game logic. Actor transforms still need the
same treatment (not yet located).

## Frame-coupled systems found so far

| ID | System | Coupling |
|---|---|---|
| T001 | main loop | waits for each VI retrace (0x801FE00C) |
| T002 | controller sampling | SI sampling rate tied to video |
| T006/T007 | title/opening modules | fixed-step per update, no delta time |
| T008 | message-loop worker | one tick message per main-loop frame (0x801FDAE4/E8) |
| CAM-004 | camera | projection/view rebuilt per camera update (interpolation hook) |
