# Playing from the repository

For the release zip see [release/v1.0.md](release/v1.0.md). This page is for the owner's copy in this
repository.

## Starting the game

Double-click `Play-WarioWorld.cmd` (or `Launch Wario World.cmd` one folder up).
There is no launcher window; the game starts straight away with the profile in
`private/playtest-user` (saves and settings, never touched by automated tests).

The starter (`launcher/wario_launcher.pyw`) installs the controls if they are
missing, reapplies the baseline Dolphin settings
(`scripts/configure_baseline.py`), runs the play tracker and writes
`private/playtest-last.log`. Errors appear in a message box.

Every option is in the in-game menu (Back on the controller, or Tab), saved in
`private/playtest-user/Config/WarioWorld.ini`; see
[modding/IN_GAME_MENU.md](modding/IN_GAME_MENU.md). Graphics backend and
performance mode take effect with the menu's "Restart now". Controls:
[CONTROLS.md](CONTROLS.md). The game's Yes / No prompts use the stick, not the
D-pad.

## Reporting a problem

Press **F12** at the spot (menu open or closed): it saves a savestate and a
screenshot as a bug-report snapshot (here in
`private/play-sessions/<UTC>/reports/`), so the problem can be reproduced in a
hidden test. Also useful: where it happened, what you pressed, whether it
repeats, and the frame rate / aspect / backend in use. Snapshots, saves and
screenshots stay private.

## Textures

- **Extract all textures** (System tab) reads every texture straight from the
  extracted disc archives into `Wario World/Extracted Textures/<area>/`
  (Title, Opening, Hub, Shared, World1-4 Stage/Boss/Area folders, Ending, Main
  program), with `manifest.csv` and `README.txt`, names compatible with the HD
  loader (`scripts/extract_textures.py`, 1,701 textures in about 5 s). Text
  drawn from the font at run time is not a disc texture; the font sheets are
  extracted.
- Upscale with names unchanged and put the results anywhere under
  `private/playtest-user/Load/Textures/GWWE01/` ("Open HD texture folder"),
  then turn on **HD textures**. Large packs stream in over a few frames
  (modding/FPS_UNLOCK.md, HD texture streaming).

## Play telemetry (private)

`launcher/play_tracker.py` runs while the game is open:
`private/play-sessions/<UTC>/stages.csv` (archive loads), `perf.csv` (speed /
fps per second with the current area), `states/<time>_<archive>.sav` (one
automatic savestate about 25 s after each new area per session; used as
hidden-test checkpoints), and `private/save-history/<time>_*.gci` (a copy of
the memory-card save when it changed).
