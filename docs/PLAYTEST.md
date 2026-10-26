# Your later playtest

Current review: ACCURACY_REVIEW.md. Launcher now pins native 1x and 4:3, with
backups of prior settings. Scaling is the internal EFB scale, not window size;
resizing keeps the game presentation at 4:3 with borders as required. Focus gate
repaired in the host; background-input behavior still needs human confirmation.
Water animation and slowdown reports in Greenhorn Forest remain unresolved.


Double-click Play-WarioWorld.cmd in the project folder when you want to test.
It has been prepared but has not been launched automatically. Unlike automated
tests, your manual launcher opens the game window and enables normal sound.
It uses the uninstrumented full-vectors module at original speed with no mods.
Your saves/settings go under private/playtest-user, separate from automated test
folders and your normal Dolphin installation. Nothing is uploaded.

Xbox/XInput mapping is now installed; see [controller controls](CONTROLS.md).
Close and reopen the game to load it. Xbox Menu/Start starts the game; left stick
selects menu choices; A confirms. Both sticks, triggers and D-pad are mapped.

Keyboard fallback:
- Arrow keys: main analog stick (including Yes/No selection).
- Enter: Start.
- X: GameCube A; Z: GameCube B.
- C/S/D: GameCube X/Y/Z; Q/W: L/R triggers.
- I/K/J/L: C-stick up/down/left/right.
- T/G/F/H: D-pad up/down/left/right.

The file-creation prompt responds to the analog stick: use arrow Up to choose
Yes, then X to confirm. D-pad Up was insufficient in our automation probes.
The mapping passes 85 production input-conversion cases and a live device-binding
check. Actual physical button presses, physical audio output and haptics still
need playtesting. The agent has not opened the visible manual launcher.

The title, save creation, opening cutscene, hub and first Greenhorn Forest area
have bounded native tests. The first-stage transition passes 12785 CPU checks
without mismatches and without JIT use on that route. Interpreted special-register
instructions remain explicitly counted. Full gameplay, bosses, audio/pixel parity
and bit accuracy remain unverified. Frame rate/refresh behavior has not been changed.

Useful feedback: where an issue happened; what you pressed; whether it repeats;
whether it affects graphics, sound, input, saving or progression. Keep any saves
or screenshots private. The agent can continue technical work without this test.

The last manual launch log is private/playtest-last.log. Your playtest saves are
retained in private/playtest-user and are never replaced by automated runs.
Actual saved-progression reload still needs a real save-point or stage-clear
cycle; the automated outer-card-file test is not proof of this.

## Launcher (2026-10-26)

Double-click `Launch Wario World.cmd` in the Wario World folder (or
`Recomp/Launch-WarioWorld.cmd`). It opens a small window: pick the build
(fast Clang build by default, MSVC fallback), optionally tick Fullscreen, press
PLAY. It does the same setup as Play-WarioWorld.cmd (controls if missing, 4:3 /
native baseline) and uses private/playtest-user, so saves are kept. "Open last
log" shows private/playtest-last.log after a crash. Choices are remembered in
private/launcher.json.
