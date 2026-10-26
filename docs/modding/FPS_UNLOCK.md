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
