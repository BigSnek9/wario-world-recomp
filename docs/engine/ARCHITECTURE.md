# Engine architecture map

- Main loop: main.dol 0x8002FC00 (F-0001) updates through six virtual calls (0x8002FCBC..0x8002FD28) then waits on VI retrace 0x801A87C4 (F-0002). See FRAME_TIMING.md.
- Scene/module manager: desired/current state globals 0x801FD914/0x801FD924; transition 0x800302CC links a REL (OSLink 0x801A0B40) and calls its prolog; teardown 0x800304AC (F-0007/F-0008). Built-in states 0..2 construct objects directly; state 3 = title REL WWUSTT (ID 8).
- Modules: 1=WWUSS1, 2=WWUSS2, 3=WWUSS4, 4=WWUSS5, 5=WWUSOP (opening), 6=WWUSED, 7=WWUSPF (hub), 8=WWUSTT (title). Greenhorn Forest gameplay runs in main (update 0x8015BF2C) with an empty module queue.
- Camera singleton candidate: 0x801FDB20 (CAMERA.md CAM-001).
- Detailed evidence: ../HANDOFF.md, ../REL_RUNTIME.md.

Unmapped: actor/entity system, collision, scripting, save system internals.
