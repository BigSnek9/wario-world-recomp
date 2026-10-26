# Xbox controller and keyboard

Close the current game and reopen Play-WarioWorld.cmd to load the installed
profile. Your existing game saves are retained. Press the Xbox Menu/Start button
at the title screen. Use the LEFT STICK to select Yes/No, then A to confirm.

| Xbox input | GameCube input |
|---|---|
| A / B / X / Y | A / B / X / Y, by label |
| Left stick | Control Stick |
| Right stick | C Stick |
| D-pad | D-pad |
| Menu / Start | Start / Pause |
| RB | Z |
| LT / RT | Analog L / R; near-full press also clicks L / R |
| LB | Digital L click |

Keyboard also works alongside the controller: arrow keys = Control Stick,
Enter = Start, X/Z = A/B, C/S/D = X/Y/Z, Q/W = L/R, I/K/J/L = C Stick,
T/G/F/H = D-pad. The game's Yes/No menu expects the analog stick, not D-pad Up.

Player 1 accepts XInput controller slots 0..3, so Windows assigning a different
slot does not require remapping. Stick dead zones are 12%; circular input
calibration is explicit. Rumble settings are unchanged and have not been tested.

## Installation and preservation

Profile: private/playtest-user/Config/GCPadNew.ini (GCPad1).
GameCube port 1: Config/Dolphin.ini Core SIDevice0=6.
To explicitly restore these defaults, run python scripts/configure_controls.py.
It backs up a changed pre-existing profile before replacing Player 1 mappings,
preserves other controller sections and other Dolphin settings, and never edits
saves. The launcher installs defaults only if the profile is missing; it does
not overwrite an existing custom profile every launch. No controller driver or
additional software was installed.

## What was verified

85 cases run through the production controller expression parser and actual
GCPad conversion: four Xbox slots, buttons, both sticks, dead zone, partial/full
triggers, keyboard fallback, release and simulated reconnect. Five configuration
preservation/idempotence tests pass. A hidden, muted Runtime::Create using a
copy of the installed configuration detects the actual XInput/0/Gamepad plus
keyboard; every face/Start/Z binding resolves to both devices, Player 1 connected.
See reports/controller-mapping-test.json and controller-runtime-bindings.log.
No physical button press has been verified by the agent. A user verification
question is pending; actual in-game response after restart still needs their
feedback. Silent automated pad injection alone is not physical-controller proof.
