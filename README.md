# Wario World Recomp

A native Windows PC version of **Wario World** (Nintendo GameCube, 2003), made by
*static recompilation*: the game's own code is translated into C and compiled for
your PC, then run on a GameCube-compatible runtime based on Dolphin. The whole
game is playable from start to finish.

**Everything in this project was made by Claude (Anthropic's AI)**, working
autonomously at the owner's direction: the recompilation, the runtime fixes, the
enhancements, the tests and these docs.

## You need your own copy of the game

No game files are included or ever will be. You need your own dump of the
**USA disc, GWWE01 (revision 0)** as an `.iso`. The installer checks that it is
the right version.

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

A one-click installer is in progress: it asks for your ISO and an install folder,
then builds the game for your PC. Until then, see
[docs/START_HERE.md](docs/START_HERE.md) for the build steps (Windows 10/11,
Python, Git, CMake, Visual Studio 2022 C++ build tools, LLVM/clang).

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
