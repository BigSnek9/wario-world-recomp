# Frame timing

The authoritative ledger is [../TIMING.md](../TIMING.md) (entries T001-T009,
including the intervention points used by frame generation). This file indexes
it for the required docs layout.

Summary: simulation is gated by a VI retrace wait in the main loop (T001);
input sampling via SISetSamplingRate(0) (T002); guest clock OSGetTime/OSGetTick
(T003); fixed-step module updates confirmed in title (T006) and opening (T007)
modules; a message-loop worker ticks once per frame (T008); the frame counter
and soft-reset hold count frames (T009). Original target is 59.94 Hz NTSC; the
simulation still runs at that rate with frame generation on, which only adds
presented frames (../modding/FPS_UNLOCK.md).
