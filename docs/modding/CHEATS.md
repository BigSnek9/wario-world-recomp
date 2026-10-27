# Cheats (engine side)

Game-module cheats for the in-game menu's Cheats tab (status 2026-10-27: done;
the menu's jump height slider covers 100-500 %). They are built into the game
module by `scripts/build_rel_bundle.py` (the `CHEAT_SITES` section: hook sites, C glue
`CHEAT_GLUE`). Engine findings behind them: `docs/engine/PHYSICS.md` G-0007, G-0010..G-0015.

Every cheat is an exported `volatile s32` in `gGWWE01_recomp.dll` (look it up with
`GetProcAddress`, like `wario_audio_*`). All of them are **inert at 0**: each hook returns
before touching guest state, so with every variable at 0 the module runs the original code.
The module reads the variables on the game's CPU thread at logic time (inside the player
update, collision and attack code), so the menu can write them at any moment.

| Export | Type / values | Effect |
|---|---|---|
| `wario_cheat_noclip` | s32, 0 off / 1 on | Walk through walls: wall hits of Wario's mover are ignored; floors and ceilings stay solid. |
| `wario_cheat_super_punch` | s32, 0 off / 1 on | The first and second combo punches hit with the third (big) combo punch's power and reach. |
| `wario_cheat_jump_percent` | s32, 0 or 100 = original; clamped to 10..1000 | Jump height in percent of the original full-hold jump. |
| `wario_cheat_unlock_stages` | s32 request: write 1; module sets 2 when applied | One shot: marks every stage and world boss of the four worlds as cleared, so every stage and world opens. |
| `wario_cheat_collect_all` | s32 request: write 1; module sets 2 when applied | One shot: marks every per-stage collectable as collected (treasures, red diamonds, Spritelings, statue parts, the stage's special items) plus the four world-boss pieces the final-boss chest needs; also unlocks every GBA game. |

One-shot requests are applied at the next player update, i.e. only while a save is
loaded and Wario exists (hub or stage); a request made on the title screen waits until
then, so loading a file cannot overwrite it. The menu may write 0 again afterwards (the
progress stays changed; the game saves it at its normal save points like any other
progress). There is no "undo": progress changes are permanent once the game saves.

## Mechanisms

**Walk through walls.** Wario's movement collision is the mover at player+0x160
(fn_80125488, r29 = mover). It runs eight queries against the collision mesh (vtable
+0x1C swept test, +0x24 sphere test; the result struct starts with the hit normal). With
noclip on, a hit whose normal is horizontal (|ny| < 0.5) is reported as no hit for
Wario's mover only. The floor is snapped by the separate ground probe (fn_801272A4), and
floor/ceiling-like normals still count, so Wario keeps walking on floors and slopes. The
generic sphere-collider pushout fn_8012A2A0 gets the same rule. Objects (doors, crates,
enemies) push Wario through their own code and stay solid. Walking out of the level over a
pit still falls (there is no floor). No separate fly mode (not trivial: gravity and the
ground probe would both need overrides).

**Super punch.** The punch state (state 13, fn_8011C8F0) runs phases 1 (first punch),
2 (second) and 3 (the third, big combo punch). Each sets Wario's attack object (player
+0x2E4) through fn_80112288 (r4 type, f1 radius, r6 power). Phases 1/2 use power 1 with
radius 1.0/1.5; phase 3 uses power 3, radius 2.0. With super punch on, the four phase 1/2
calls get power 3 and radius 2.0. Animations, timing and the combo itself are unchanged.

**Jump height.** fn_80113BCC (jump controller, mover at player+0x160) launches with 0.39
along the up normal (lbl_80200BC8), then adds 0.021 per frame (decaying x0.9995) while A is
held and Wario rises; gravity is 0.035 per frame and air drag x0.985. The cheat scales only
the launch speed. The factor for a target height is found by simulating a full-hold jump
with those constants (bisection), so the percent is a true height ratio for held jumps
(tap jumps scale a little less). Springs, enemy bounces and other launches are unchanged.

**Unlock stages.** Progress block 0x801CE3A4 (+8, u16): bit world*3+stage is set when that
stage (stage 2 = the world's boss) is cleared (fn_800308F0); the hub opens doors from
these bits. The cheat ORs in 0x0FFF: both stages and the boss of every world (bits 2, 5,
8 and 11 are the four world bosses). That is the value a finished save holds (the user's
post-ending state reads 0x0FFF). The hub's final-boss chest needs all 12 bits: when the
hub is built it sets its flag +0x16E only if (mask & 0xFFF) == 0xFFF (WWUSPF 0xE998).
The first version set 0x07FF and so left the last world boss's piece missing. The hub
shows newly set bits with its normal door-opening handling (it compares against the copy
at 0x801CE470); both checks run when the hub is loaded, so re-enter the hub after applying.

**Collect everything.** Per-stage records at 0x801CE3B0 + world*0x30 + stage*0x10 (stages
0 and 1). The cheat ORs in: +4 0x1F (five Spritelings), +6 0xFF (eight statue parts; the hub
unlocks the stage's GBA game when this byte is 0xFF), +8 0xFF (eight treasures), +A and +C
0xFF (eight red diamonds and the stage's special items). +0/+1 (the stage's own event
flags) are not touched. It also ORs in the four world-boss clear bits (0x0924), the pieces
the hub's final-boss chest counts, as the boss-clear code (fn_800308F0) does. With every
stage cleared as well (by playing or the unlock cheat) the chest opens. These are exactly
the values the game's own setters write. Nothing else collectable is stored elsewhere: the
pause book's eight treasures, three special items, five rings, statue (8/8), red diamonds
and five Spritelings all come from these records (checked in a capture of Pecan Sands
with the cheat; applying it in a stage also shows the special-item pickup effect once).
Progress +0 (coins) and +4 (a running counter, max 99,999) are not collectables.

## Verification (hidden, muted runs; private evidence under private/runs)

Test hooks: `WARIO_CHEAT_TEST="noclip,super_punch,jump_percent,unlock,collect[,delay_ms]"`
sets the variables after delay_ms; `WARIO_CHEAT_LOG=<file>` logs cheat events and, with
`WARIO_CHEAT_LOG_POS=1`, Wario's position/velocity every update.

- Jump (Greenhorn Ruins state, A held 60 frames): peak 4.406 (100%), 8.812 (200%),
  13.219 (300%) units above the floor.
- Super punch (same state, enemy swarm, B every 28 frames): on, the log shows power 1 -> 3
  on the punch calls and the captures show enemies knocked out (white KO burst, coins,
  red-diamond counter); off, the same punches only push the enemies back.
- Collect everything + unlock (early save, mask 0x0001): progress block after the request
  equals the documented values (mask 0x07FF in that first version, now 0x0FFF; records
  001F/00FF x4); the pause book of
  Greenhorn Ruins shows 8/8 statue parts, all treasures and items, red diamonds and five
  Spritelings (without the cheat: one treasure, one Spriteling, 0/8).
- Walk through walls (Greenhorn Ruins swarm room, stick held into the ivy back wall): off,
  Wario stops at z = 81.8 and slides along the wall; on, the log shows the suppressed hits
  (0x801258E8, 0x8012618C, 0x80126B20) and Wario passes the wall (z 81.8 -> 79.0 -> ...).
  Behind that wall there is no floor, so he then falls (the game's pit fall; it did not
  end within 10 s). In the hub the outer rim is a steep slope (|ny| about 0.46 is ignored,
  but the floor probe still holds him), so he stops there with or without the cheat.
- All cheats 0 vs the stock module (same state and walk probe, two runs each): every run
  stops at the wall (z 81.809..81.815), the progress block is byte-identical, the cheat log
  stays empty; the x position along the wall varies between runs of the stock module too.

## Limitations

- Noclip has no fly mode and no safety net: walking out of a level where there is no floor
  falls forever until the player reloads (or turns noclip off before reaching the edge).
  Steep slopes count as floor; object collisions (doors, crates, enemies) are unchanged.
- Super punch covers the grounded punch combo only (not other attacks).
- Jump height scales only the A-button jump; the percent is exact for full-hold jumps.
- Hub door animations, the GBA shelf and the opened final-boss chest were checked in
  memory only (late hub save: unlock gives 0x07FF -> 0x0FFF; Pecan Sands save: collect gives
  0x0BFF, the one missing bit being the uncleared stage itself), not watched in a capture; the exact meaning of record fields +0xA / +0xC is unverified.

## The retired "Moon jump"

The first cheat (a host-side `MoonJump()` in the menu, and before that the
`launcher/cheats.pyw` helper) pushed Wario's **position** y up while A was held:
a levitation nudge outside the game's physics, frame-rate dependent and not
synchronized with the CPU thread. It was replaced by Jump height
(`wario_cheat_jump_percent`), which scales the game's own launch. The menu drops
the old `moon_jump` / `moon_speed` keys on the next save; the helper script was
removed.
