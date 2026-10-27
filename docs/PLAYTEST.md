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

## Starting the game (2026-10-27)

Double-click `Launch Wario World.cmd` in the Wario World folder (or
`Recomp/Launch-WarioWorld.cmd` / `Play-WarioWorld.cmd`). There is no launcher
window any more; the game starts straight away. Every option is in the in-game
menu (Back on the controller, or Tab), saved in
private/playtest-user/Config/WarioWorld.ini.
- **Graphics backend:** a menu option. It takes effect with the menu's
  "Restart now".
- **Builds:** the fast Clang PGO build is always used; the MSVC fallback
  choice is gone.
- **Setup:** the starter (launcher/wario_launcher.pyw) still installs the
  controls if they are missing, reapplies the 4:3 / native baseline, runs the
  play tracker and writes private/playtest-last.log. Errors appear in a
  message box.

(The texture-dump notes below describe the retired launcher; texture
extraction and the HD folder are now menu items.)

## Texture dump and HD textures (2026-10-26)

- Tick **Texture dump mode** and play normally. Every texture the game uses is
  saved once. When you close the game the launcher sorts the new ones into
  `Wario World/Texture Dump/<area>/` (area = the stage archive loaded just before
  the texture first appeared: Title, Hub, Shared, World/Stage folders, ...).
  `manifest.csv` and `README.txt` in that folder list every file. Repeat sessions
  only add new textures. Dumping writes PNGs during play, so expect small hitches.
- Upscale with names unchanged, put the results anywhere under
  `Recomp/private/playtest-user/Load/Textures/GWWE01/` ("Open HD texture folder"),
  and tick **Use HD textures**.
- Coverage = what you have seen; there is no static extractor yet (the disc's
  .RSC archives are a proprietary format).
- Verified headlessly: boot to hub dumped 204 textures sorted into Title (125),
  Hub (75), Shared/UNIV (4); a red/blue-swapped 2x title logo placed in a
  subfolder of the HD folder replaced the original on the title screen.
- Runtime detail: Dolphin forces DumpTextures off at every start, so the
  launcher sets MODERNGEKKO_DUMP_TEXTURES=1 (scripts/tool_fix_texture_dump.py).

## Launcher update (2026-10-26 evening)

- Play-time texture dump mode removed at the user's request; replaced by
  **Extract all textures** (reads every texture straight from the extracted disc
  archives into `Wario World/Extracted Textures/<area>/`, names compatible with
  the HD loader; scripts/extract_textures.py).
- **Volume slider** changes volume live: the runner gets
  `--automation-dir private/launcher-control` and the slider writes
  `command=set_volume volume=N` files (scripts/tool_fix_volume_command.py).
  Verified headless: valid values applied and persisted, 250 rejected.
- **Display**: OpenGL SDR / Vulkan SDR / Vulkan HDR output (KI-005).

Extractor result (2026-10-26): 1,701 textures in ~5 s, folders per area
(Title, Opening, Hub, Shared, World1-4 Stage/Boss/Area folders, Ending, Main
program), manifest.csv + README.txt. Text drawn from the font at run time
(e.g. "Please choose a file") is not a disc texture; the font sheets themselves
are extracted (I4 format).

## Playthrough telemetry (2026-10-26)

launcher/play_tracker.py runs while the game is open (all private):
private/play-sessions/<UTC>/stages.csv (archive loads), perf.csv (speed/fps per
second with current area), states/<time>_<archive>.sav (one automatic savestate
~25 s after each new area per session; hidden-test checkpoints), and
private/save-history/<time>_*.gci (copy of the memory card save when it
changed). Verified headless: title/hub archives logged, 78 perf rows, two
checkpoints (~26 MB each), checkpoint reloads in smoke_boot.
