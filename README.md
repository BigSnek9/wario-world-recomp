# Wario World Recomp

**Wario World** (Nintendo GameCube, 2003) as a native Windows PC game.

This is a *static recompilation*: the game's own code was translated into C and
compiled for the PC, running on a GameCube-compatible runtime based on Dolphin. It
plays the whole game, start to finish, and adds optional enhancements such as high
frame rates, widescreen and HDR.

**Made entirely by Claude** (Anthropic's AI), working autonomously at the project
owner's direction: the recompilation, runtime fixes, enhancements, tools, tests and
these docs.

> **You need your own copy of the game.** No game files are included. You need a
> plain `.iso` dump of the **USA disc (GWWE01, revision 0)**; other regions and
> revisions are not supported. The game checks the disc before using it.

> **Windows only.** Windows 10 or 11 (64-bit), the only system it has been built and
> tested on.

## Quick start

1. Download `WarioWorldRecomp-vX.Y.zip` from the
   [Releases](https://github.com/BigSnek9/wario-world-recomp/releases) page (about 46 MB).
2. Unzip it into a folder you own (your Desktop or Documents, not Program Files).
3. Double-click **`WarioWorldRecomp.exe`** and pick your `.iso`.

The first time, it checks the disc and copies the game files next to the exe, which
takes a few seconds. After that it starts straight away. Nothing else needs installing.

To update, unzip a new version over the old folder. Your saves and settings in
`user\` are kept.

## Enhancements

Open the in-game menu with **Back** on the controller or **Tab** on the keyboard.
Options apply straight away. Out of the box the picture fills your screen at its
resolution and shape; the game itself plays exactly like the original, and
every enhancement can be switched off for the original 4:3 look.

| Feature | What you get |
|---|---|
| **Frame rate** | 60, 120, 180 or 240 FPS, or match your monitor. The extra frames come from the game's own camera and object positions, not from guessing between pictures, and are paced to your display. |
| **Widescreen** | Any aspect ratio (16:9, 16:10, 21:9, 32:9). You see more of the world instead of a stretched picture; the HUD moves to the screen edges and menus, speech boxes and the pause book keep their shape. |
| **Resolution** | Up to 8x the original, or match your window or monitor (4K and above). |
| **HDR** | On Vulkan, with paper white, peak brightness, white level, contrast, saturation, vibrance and menu brightness, each with a reset. |
| **HD textures** | Texture packs load in the background without stutter. Builds made with the installer can also extract every game texture for upscaling. |
| **Audio** | Master, music and sound-effect volume, and an option to mute the pause-menu music. |
| **Controls** | Xbox and PlayStation pads and keyboard out of the box, with buttons where they sit on a GameCube pad. Rebind any button; rumble on/off and strength. |
| **Cheats** | Jump height, walk through walls, super punches, unlock all stages, collect everything. The last two are permanent once you save. |
| **Performance mode** | Runs the graphics on their own thread for slower PCs (takes effect after a restart). |
| **Other** | OpenGL or Vulkan, fullscreen (F11 / Alt+Enter), menu themes and size, and **F12** saves a bug-report snapshot to `data\reports`. |

## Controls

| GameCube | Xbox | PlayStation | Keyboard | In the game |
|---|---|---|---|---|
| A | A | Cross | X | Jump |
| B | X | Square | Z | Punch, grab, throw |
| R | RT | R2 | W | Dash, ground pound, piledriver |
| L / Z | LT / RB | L2 / R1 | Q / D | Hyper Suction (pull in coins) |
| Control Stick | Left stick | Left stick | Arrows | Move |
| C Stick | Right stick | Right stick | I J K L | Camera |
| Start | Menu | Options | Enter | Pause book |

The game's Yes/No prompts use the stick, not the D-pad. Full details:
[docs/CONTROLS.md](docs/CONTROLS.md).

## Your files

Everything stays in the folder you unzipped to:

- `game\` the files copied from your disc
- `user\` saves, settings and HD texture packs (`user\Load\Textures\GWWE01`)
- `data\` logs and F12 bug-report snapshots

To set up from the command line without a dialog:
`WarioWorldRecomp.exe --iso <your.iso> --setup-only` (add `--quiet` to write errors
only to `data\launcher.log`).

## Build it yourself (optional)

If you would rather build everything on your own PC, double-click
**`Install-WarioWorld.cmd`** in this repository. It asks for your `.iso` and an
install folder, then downloads the pinned DolRecomp and ModernGekko sources, applies
this project's fixes, translates the game's code to C, compiles it and installs the
result with desktop and Start-menu shortcuts. Build files are deleted when it
finishes.

- Takes 20-60 minutes and needs about 5 GB free while it builds (about 0.5 GB after).
- Needs Python 3.11+, Git, CMake, Ninja, Visual Studio 2022 C++ build tools
  ("Desktop development with C++") and LLVM/clang. The installer checks each one and
  links to it, or installs it with `winget` if you click that button.
- It can be stopped and resumed. Running it again on the same folder rebuilds and
  keeps your saves.

Without the window: `python installer\wario_installer.pyw --no-gui --iso <your.iso>
--install-dir <folder>` (`--check` only checks the prerequisites). Manual build steps
are in [docs/START_HERE.md](docs/START_HERE.md); making a release zip is in
[docs/PUBLISHING.md](docs/PUBLISHING.md).

## Status

- The full game has been played through on this build.
- Known issues: [docs/progress/KNOWN_ISSUES.md](docs/progress/KNOWN_ISSUES.md).
- Current status and test results:
  [docs/progress/CURRENT_STATUS.md](docs/progress/CURRENT_STATUS.md).
- All documentation: [docs/README.md](docs/README.md).

Found a bug? Press **F12** where it happens and include the snapshot from
`data\reports` in your report.

## Credits and licences

- Built on [DolRecomp](https://github.com/ExpansionPak/DolRecomp) and
  [ModernGekko](https://github.com/ExpansionPak/ModernGekko), which includes code from
  the [Dolphin](https://dolphin-emu.org/) emulator (GPLv2 or later).
- This project's scripts and patches are GPLv3 ([LICENSE](LICENSE)). Upstream
  components keep their own licences, included in the release zip under `LICENSES\`.
- Wario World is © Nintendo. This is an unofficial fan project, not affiliated with
  or endorsed by Nintendo. Neither this repository nor the release zip contains any
  game files: the graphics, sound and data all come from your own disc.
