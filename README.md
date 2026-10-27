# Wario World Recomp

A native Windows PC version of **Wario World** (Nintendo GameCube, 2003), made by
*static recompilation*: the game's own code is translated into C and compiled for
your PC, then run on a GameCube-compatible runtime based on Dolphin. The whole
game is playable from start to finish.

**Everything in this project was made by Claude (Anthropic's AI)**, working
autonomously at the owner's direction: the recompilation, the runtime fixes, the
enhancements, the tests and these docs.

**Windows only.** It runs on Windows 10/11 (x64), the only system it has been built
and tested on. Linux, macOS and Steam Deck are not supported.

## You need your own copy of the game

No game files are included or ever will be. You need your own dump of the
**USA disc, GWWE01 (revision 0)** as a plain `.iso`. The starter and the installer
check that it is the right version.

## Enhancements

All optional, all in an in-game menu (press **Back** on the controller or **Tab**),
applied instantly. With everything off, the game behaves like the original.

- **Smooth frame rate:** 60, 120, 180 or 240 FPS (or match your monitor). Extra
  frames are generated from the game's own camera and objects, not by guessing
  from the picture.
- **Widescreen:** any aspect ratio (16:9, 16:10, 21:9, 32:9). The view widens
  instead of stretching, the HUD sits at the screen edges, and menus, speech boxes
  and the pause book keep their original shape.
- **Resolution:** up to 8x, or match your window/monitor (4K and above).
- **HDR** (Vulkan), with brightness, paper white and colour controls.
- **HD texture packs**, loaded smoothly in the background, plus a tool to
  extract all of the game's textures for upscaling.
- **Audio mixer:** master, music and sound effect volume, and an option to mute
  the pause-menu music.
- **Performance mode:** runs the graphics on their own thread.
- **Cheats:** higher jumps (more coming).
- Controller and keyboard support, fullscreen, OpenGL or Vulkan.

## Install

**Release zip (recommended).** Download `WarioWorldRecomp-vX.Y.zip` from the
releases page (about 46 MB), unzip it anywhere you own (not Program Files) and
double-click **`WarioWorldRecomp.exe`**. The first time, pick your `.iso`: it is
checked (GWWE01 revision 0, by its SHA-256), its files are copied into `game\` next
to the exe and the game starts. Setup takes seconds on an SSD and only happens once;
nothing else needs installing.

The zip holds the compiled runtime and game module, the starter, licences and a
README; no game files. Your saves and settings are in `user\`, logs and F12
bug-report snapshots in `data\`. To update, unzip the new version over the old
folder (your `user\` folder is kept). Starter options for tests and tools:
`WarioWorldRecomp.exe --iso <your.iso> --setup-only` sets up without a dialog
(`--quiet` writes errors only to `data\launcher.log`).

**Build it yourself from the ISO (alternative).** Double-click
**`Install-WarioWorld.cmd`**. The installer asks for your `.iso` (it checks that it is
GWWE01 revision 0) and for an install folder (any folder), then builds the game on
your PC and installs it there. Building takes 20-60 minutes; you can stop it and
resume it later.

It needs Windows 10/11 and these free tools; the installer checks for each one and
links to it (or installs it with `winget`, only if you click that button):
Python 3.11+, Git, CMake, Ninja, Visual Studio 2022 C++ build tools
("Desktop development with C++") and LLVM/clang. Allow about 5 GB of free space while
it builds; the finished install is about 0.5 GB.

What it does: downloads the pinned DolRecomp and ModernGekko sources, applies this
project's fixes, builds the tools and the runtime, extracts your disc, translates the
game's code to C and compiles it into a game module, then copies the runtime, module,
game files and starter into the install folder, makes a game icon from the coin
texture on your disc and adds desktop / Start-menu shortcuts. The build files are
deleted when it finishes. Everything runs from the install folder: your saves and
settings are in `user\`, logs in `data\`. Start the game with the shortcut or
`Play Wario World.cmd`. Running the installer again on the same folder with your disc
rebuilds it and keeps your saves; without the disc, **Update** just remakes the icon
and shortcuts.

Without the window: `python installer\wario_installer.pyw --no-gui --iso <your.iso>
--install-dir <folder> [--desktop-shortcut] [--start-menu-shortcut]` (`--check` only
checks the prerequisites; `--refresh` only remakes the icon and shortcuts). Manual build
steps: [docs/START_HERE.md](docs/START_HERE.md). Making a release zip:
[docs/PUBLISHING.md](docs/PUBLISHING.md).

## Status

- Complete playthrough done on this build.
- Being polished: frame pacing on high-refresh monitors, a few widescreen screens,
  more cheats and controller options.
- Details and test evidence: [docs/progress/CURRENT_STATUS.md](docs/progress/CURRENT_STATUS.md).

## Credits and licences

- Built on [DolRecomp](https://github.com/ExpansionPak/DolRecomp) and
  [ModernGekko](https://github.com/ExpansionPak/ModernGekko), which includes the
  [Dolphin](https://dolphin-emu.org/) emulator code (GPLv2 or later).
- This project's own scripts and patches are GPLv3; upstream components keep their
  own licences.
- Wario World is © Nintendo. This is an unofficial fan project, not affiliated with
  or endorsed by Nintendo. It contains no Nintendo code or assets.
