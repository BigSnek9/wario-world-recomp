# Engine architecture map

- Main loop: main.dol 0x8002FC00 (F-0001) updates through six virtual calls (0x8002FCBC..0x8002FD28) then waits on VI retrace 0x801A87C4 (F-0002). See FRAME_TIMING.md.
- Scene/module manager: desired/current state globals 0x801FD914/0x801FD924; transition 0x800302CC links a REL (OSLink 0x801A0B40) and calls its prolog; teardown 0x800304AC (F-0007/F-0008). Built-in states 0..2 construct objects directly; state 3 = title REL WWUSTT (ID 8).
- Modules: 1=WWUSS1, 2=WWUSS2, 3=WWUSS4, 4=WWUSS5, 5=WWUSOP (opening), 6=WWUSED, 7=WWUSPF (hub), 8=WWUSTT (title). Greenhorn Forest's stage update is in main (0x8015BF2C); the module queue is empty at stage entry, but WWUSS1 is linked a few seconds into the stage (below).
- Camera singleton candidate: 0x801FDB20 (CAMERA.md CAM-001).
- Detailed evidence: ../PROGRESS.md (2026-10-25 notes), ../REL_RUNTIME.md.

Mapped since: player, progress block, collision of the player (PHYSICS.md). Still unmapped: the general actor/entity system, scripting, save system internals.

## Module lifetime observation (2026-10-26)

At the Greenhorn Forest entry checkpoint the OS module list (0x800030C8) is
empty; after a few seconds of walking it holds WWUSS1 (module ID 1) at header
0x809E74C0 with 23 sections (code section 3 at 0x809E75C0, 303,636 bytes;
small data sections 4-7). So REL1 is linked and executed during Greenhorn
Forest gameplay, correcting the earlier note that stage one does not exercise
REL1. Evidence: private/runs/20261026T165304735180Z-f5082ae1 snapshots 1-3.
What triggers the link (area streaming? enemy set?) is not yet known.

## Main loop per frame (main, 0x8002FC98..0x8002FD58) - confirmed static, runtime-checked

Scene object pointer: `[0x801FD910]` (Greenhorn: 0x804AF4E0; its vtable 0x80A33C54
lies in WWUSS1's data section, so the stage scene class is defined in REL1 and
overrides slot +0x50 with REL1 code at 0x809F5A8C; other slots are base-class
methods in main). Flags `[0x801FD930]` (0x3 in gameplay): bit 0 keeps the outer
scene loop alive, bit 1 keeps the per-frame loop alive, bit 2 selects the
alternate update.

1. `fn_800302CC` scene/module transition (F-0007), `fn_80041B00`, `fn_80041B30`
   framebuffer toggle (T005).
2. `fn_8004ABA0([0x801FDA90])` - pad/input manager update (probable; the same
   object's +0xE0 holds button bits, see T009).
3. If flag bit 2: scene vtbl+0x44 (base fn_80031244 -> [0x801FD9D4] vtbl+0x0C,
   fn_80037498). Else: vtbl+0x48 (fn_80031294 -> [0x801FD9D4] vtbl+0x10,
   fn_800374F0), vtbl+0x4C (fn_800312E4, large update: fn_8003432C, fn_80034374,
   fn_800353B0, fn_80035710 ...), vtbl+0x50 (stage-specific; REL1 in Greenhorn).
4. vtbl+0x58 (fn_80031708: frame counter + reset handling, T009).
5. `fn_800589A8` worker tick (T008).
6. vtbl+0x54 (fn_80031688 -> [0x801FD9D4] vtbl+0x18; probably draw/flush).
7. `fn_801A87C4` wait for VI retrace (T001).

Roles of +0x48/+0x4C/+0x50/+0x54 as update vs draw are probable, not confirmed.
`[0x801FD9D4]` is a second manager object called in each phase (unknown role).
