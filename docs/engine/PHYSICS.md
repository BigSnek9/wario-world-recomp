# Physics and gameplay

No confirmed findings yet. Observed: Greenhorn Forest stage update in main.dol at 0x8015BF2C. Movement/jump/attack inputs respond in hidden tests; no trajectory measurements yet.

## G-0001 Player object pointer (probable)

- Global `0x801FDA00` holds the player (Wario) actor pointer (0x804AF400 in the
  Greenhorn Forest checkpoint). World position f32 vec3 at `+0x14` (x, y-up, z).
- Evidence and caveats: research/FUNCTION_DATABASE.json `globals` G-0001.
- Use: automated navigation/test assertions can read this instead of relying on
  screenshots. Do not write it in tests that claim gameplay parity.

## G-0007 Live player actor pointer - CONFIRMED (2026-10-26)

`0x801C5820` -> player actor; position f32 x/y/z at +0x14/+0x18/+0x1C.
Writing y moves Wario (camera follows). 0x801FDA00 (G-0001) only mirrors the
position. Used by launcher/cheats.pyw (moon jump).

## G-0010 Progress block (save data) - CONFIRMED (2026-10-27)

`0x801CE3A4` (lbl_801CE3A4, 0xCC bytes): +0 coins (s32, max 999,999,999, fn_8003081C),
+4 s32 (max 99,999, fn_800308A4), +8 u16 stage-cleared mask (G-0011), +0xA u16 (zero),
+0xC.. twelve 0x10-byte stage records (G-0012). Current world/stage at 0x801CE398 / +4
(-1 in the hub). 0x801CE470 is a copy taken at hub/stage transitions (fn_80030158,
fn_8015D204, WWUSPF); the hub XORs the two masks to animate newly opened doors and reads
the copy's records for the GBA-game shelf. Cleared by fn_800306D4 (new file). Evidence:
accessors fn_800308F0..fn_80030CB0 and memory dumps of hub states from three play sessions
(early save 0x0001, mid 0x00FF, late 0x07FF). PAL equivalent: 0x801D8BF0 records /
0x801D8BEC mask (GWWP01 Action Replay codes; NTSC offset -0xA840).

## G-0011 Stage-cleared mask - probable semantics, confirmed layout

Progress+8 (0x801CE3AC) u16, bit world*3 + stage (stage 2 = world boss), set by
fn_800308F0 for the current world/stage (called from the stage RELs' clear code), tested by
fn_80030924. A finished game showed 0x07FF before the final boss; bit 11 is the last
world's boss. Used by the unlock-stages cheat (docs/modding/CHEATS.md).

## G-0012 Per-stage collectable record - CONFIRMED layout

Record (w, s) at 0x801CE3B0 + w*0x30 + s*0x10 (s 0..1 used; s 2 never written):
+0 u16 stage event flags (stage RELs, via fn_80030CB0), +4 Spritelings (5 bits, 40 total;
setter fn_80030A20), +6 statue parts (8 bits, fn_80030AA0; 0xFF unlocks the stage's GBA
game in the hub), +8 treasures (8 bits, global id w<<4|s<<3|bit via fn_80030960),
+0xA (fn_80030B50) and +0xC (fn_80030BD0) 8-bit sets (red diamonds and the stage's
special items; exact assignment unverified). Pause-book capture with every bit set shows
8/8 parts, all treasures/items, eight red diamonds and five Spritelings.

## G-0013 Player physics and jump - CONFIRMED (2026-10-27)

Player actor (G-0007) velocity f32 x/y/z at +0x204/+0x208/+0x20C; mover sub-object at
+0x160 (its +0xA4 is the same velocity). Per update: gravity -0.035 (fn_80124428), jump
controller fn_80113BCC (state at player+0x104), integration pos += vel and drag x0.985
(fn_8010E444). Jump: launch 0.39 (lbl_80200BC8) along the up normal, +0.021 per frame while
A is held and rising (lbl_80200BC4, x0.9995 per frame). Measured full-hold jump: 4.41 units.
Evidence: function-entry trace of a hidden run (position/velocity attribution per call).

## G-0014 Player state machine and punch combo - CONFIRMED

State machine at player+0x378 (+0 current state, +4 previous); 20 state objects with
vtables 0x801C579C (state 0) .. 0x801C55D4 (enter, exit, update at +8/+0xC/+0x10).
States seen: 1 idle/walk (fn_80116A34), 4 airborne, 13 punch (fn_8011C6F0 / fn_8011C8F0),
17 hurt. Punch phases at state+4: 1 first punch, 2 second, 3 third (big). Attack object
player+0x2E4 set through fn_80112288 (r4 type, r5 position, f1 radius, r6 power): punches
1/2 power 1 (radius 1.0/1.5), punch 3 power 3 (radius 2.0) plus camera shake and a
bigger hit effect. Health at player+0xD8.

## G-0015 Map collision of the player - CONFIRMED

fn_80125488 (mover vs collision mesh; r29 mover, +0x18 position pointer, +0x20 velocity
pointer) runs swept (+0x1C) and sphere (+0x24) queries through the mesh vtable; the wall
pushout of a walk into the Greenhorn Ruins back wall happens at 0x80126240..0x80126270
(normal at r1+0x54, distance r1+0x60). Floor snapping is fn_801272A4. fn_8012A2A0 is a
generic sphere-collider pushout. Used by the noclip cheat.
