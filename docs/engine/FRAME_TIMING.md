# Frame timing

The authoritative ledger is [../TIMING.md](../TIMING.md) (entries T001-T007, including uncap intervention points). This file indexes it for the required docs layout.

Summary: simulation is gated by a VI retrace wait in the main loop (T001); input sampling via SISetSamplingRate(0) (T002); guest clock OSGetTime/OSGetTick (T003); fixed-step module updates confirmed in title (T006) and opening (T007) modules. Original target is 59.94 Hz NTSC; measured host runs hold ~59.94 FPS at speed 1.0 in idle scenes.
