# Controllers and keyboard

Status 2026-10-27: GameCube-layout defaults, in-game rebinding (Controls tab of the
Back / Tab menu) and rumble.

## Default layout: GameCube positions

The defaults copy where the buttons sit on a GameCube pad, not their printed labels.
The big A is the bottom face button, B is to its left, X to its right and Y on top:

| GameCube | Xbox | DualShock / DualSense | Wario World use |
|---|---|---|---|
| A | A (bottom) | Cross | jump |
| B | X (left) | Square | punch, grab, throw |
| X | B (right) | Circle | - |
| Y | Y (top) | Triangle | - |
| Z | RB | R1 | Hyper Suction (pull in loose coins) |
| L (analog, click near full) | LT (LB clicks L too) | L2 (L1) | Hyper Suction |
| R (analog, click near full) | RT | R2 | dash on the ground, ground pound in the air, piledriver |
| Control Stick | left stick | left stick | move |
| C Stick | right stick | right stick | camera |
| D-pad | D-pad | D-pad | - |
| Start | Menu | Options | pause book |

Wario World plays almost entirely with A, B and R (game uses from the StrategyWiki
controls page, checked 2026-10-27), so the two main buttons land where a GameCube
player expects them: jump at the bottom, punch to its left. The previous defaults
mapped by label (Xbox B = GameCube B), which put punch on the right.

Keyboard (alongside any pad): arrows = Control Stick, Enter = Start, X / Z = A / B,
C / S / D = X / Y / Z, Q / W = L / R, I / J / K / L = C Stick, T / F / G / H = D-pad.
The game's Yes / No prompts read the analog stick, not the D-pad.

## Devices

- Player 1 accepts XInput slots 0..3 (Xbox pads, and anything presented as XInput by
  Steam Input or DS4Windows), so Windows assigning another slot needs no remapping.
- DualShock / DualSense / Switch Pro and other SDL gamepads: the in-game menu adds
  every connected SDL gamepad to the bindings with the same positional layout (SDL
  names face buttons by position: South / West / East / North), checked about once a
  second, so a pad plugged in mid-game works. Xbox pads, which SDL also lists, are left
  to XInput.
- Stick dead zones are 12 %; circular calibration is explicit.

## Rumble

`Rumble/Motor` drives both motors (`Motor L | Motor R`) on every XInput slot and on SDL
gamepads; an output expression sets every control it names. The Controls tab has
Rumble on / off and Rumble strength (0-100 %, the motor reference's range, saved in
WarioWorld.ini as `rumble` / `rumble_strength`). Wario World sends rumble through the
GameCube pad's motor command. The mapping resolves in hidden runs; actual vibration
cannot be felt by a hidden test and still needs a player's confirmation.

## Rebinding (Controls tab)

Select a GameCube control (A, B, X, Y, Z, Start, L, R, D-pad), then press the new
button or key within 6 s. Dolphin's `InputDetector` watches every device; a pad press
replaces that control's pad binding (on every XInput slot and SDL gamepad, translated
by position), a key press replaces its keyboard key. Back, Guide and Tab stay reserved
for the menu and are ignored, as is the mouse. "Reset controls to defaults" restores
the table above. Bindings are saved to Dolphin's `Config/GCPadNew.ini`, so they apply
immediately and next launch. Sticks and the analog trigger values keep their defaults.

The menu only rewrites simple expressions (backtick terms joined by `|`, with the
`(...) > 0.9` trigger click); anything hand-written in GCPadNew.ini is left alone.

## Installation and migration

Profile: `<user>/Config/GCPadNew.ini` (GCPad1). GameCube port 1: `Config/Dolphin.ini`
Core SIDevice0=6.

- `python scripts/configure_controls.py` restores the defaults explicitly (backs up a
  changed profile; other players, other settings and saves are kept). The launcher
  runs it only when the profile is missing.
- `python scripts/configure_controls.py --migrate` moves an existing profile to the
  GameCube layout: bindings still equal to the old by-label defaults are replaced,
  custom bindings are kept, rumble is added, and the old file is backed up first
  (`GCPadNew.before-gamecube-layout-*.ini`). It is idempotent. The playtest profile was
  migrated on 2026-10-27 (B, X, rumble updated; L only re-ordered).
- `scripts/tool_fix_wario_menu.py` (kPadControls) and `configure_controls.py`
  (CONTROLS) hold the same table and build the same expressions.

## What was verified (2026-10-27)

- `python -m unittest test_configure_controls` (7 tests, including the GameCube layout,
  rumble mapping and migration that keeps a custom binding) and
  `test_configure_baseline.py` pass.
- `scripts/verify_controls.py`: 85 cases through the production expression parser and
  GCPad conversion (four XInput slots with the positional face buttons, sticks, dead
  zone, partial / full triggers, keyboard, unplug and hot-plug), failed=0.
- Hidden menu run (`MODERNGEKKO_WARIO_MENU_TEST_PAD=1`, legacy profile seeded): "Reset
  controls to defaults" wrote all 23 GCPad1 bindings identical to `profile()`.
- Not verified by a test: an actual rebind (needs a physical press), vibration, and a
  physical DualShock.
