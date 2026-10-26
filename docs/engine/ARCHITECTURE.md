# Engine architecture map

- Main loop: main.dol 0x8002FC00 (F-0001) updates through six virtual calls (0x8002FCBC..0x8002FD28) then waits on VI retrace 0x801A87C4 (F-0002). See FRAME_TIMING.md.
- Scene/module manager: desired/current state globals 0x801FD914/0x801FD924; transition 0x800302CC links a REL (OSLink 0x801A0B40) and calls its prolog; teardown 0x800304AC (F-0007/F-0008). Built-in states 0..2 construct objects directly; state 3 = title REL WWUSTT (ID 8).
- Modules: 1=WWUSS1, 2=WWUSS2, 3=WWUSS4, 4=WWUSS5, 5=WWUSOP (opening), 6=WWUSED, 7=WWUSPF (hub), 8=WWUSTT (title). Greenhorn Forest gameplay runs in main (update 0x8015BF2C) with an empty module queue.
- Camera singleton candidate: 0x801FDB20 (CAMERA.md CAM-001).
- Detailed evidence: ../HANDOFF.md, ../REL_RUNTIME.md.

Unmapped: actor/entity system, collision, scripting, save system internals.

## Module lifetime observation (2026-10-26)

At the Greenhorn Forest entry checkpoint the OS module list (0x800030C8) is
empty; after a few seconds of walking it holds WWUSS1 (module ID 1) at header
0x809E74C0 with 23 sections (code section 3 at 0x809E75C0, 303,636 bytes;
small data sections 4-7). So REL1 is linked and executed during Greenhorn
Forest gameplay, correcting the earlier note that stage one does not exercise
REL1. Evidence: private/runs/20261026T165304735180Z-f5082ae1 snapshots 1-3.
What triggers the link (area streaming? enemy set?) is not yet known.
