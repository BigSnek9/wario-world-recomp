# Linux (build from source)

The game can be built and played from this repository on Linux. There is no Linux release
zip yet: everything below builds from source with your own disc, the same way as on Windows.

Built and tested on CachyOS (Arch based, x86-64, AMD GPU with Mesa's Vulkan driver) in a
Wayland session.

## What you need

- A Wayland session and a Vulkan driver. Vulkan is the only graphics backend on Linux:
  ModernGekko builds Dolphin without EGL, so OpenGL has no Wayland context.
- A controller. The runtime has no keyboard input device on Wayland, so the keyboard only
  works for the window and menu keys listed below, not for playing.
- clang, Ninja, CMake, Python 3, ModernGekko's Linux build dependencies (the package list in
  its `.github/workflows/build.yml`) and the wayland-client, wayland-egl, egl and xkbcommon
  development files.
- For `scripts/extract_textures.py` only: numpy, Pillow and xxhash for Python.

## Build

From the repository root, with your USA disc (GWWE01, revision 0):

```sh
python3 scripts/build.py fetch
python3 scripts/build.py tools --jobs 6
python3 scripts/build.py extract --iso "/path/to/Wario World (USA).iso"
python3 scripts/build.py translate --jobs 6
python3 scripts/build.py module-main --jobs 6
python3 scripts/build_rel_bundle.py --vectors --clean --clang --jobs 6
```

Ninja puts the runtime in `build/moderngekko/` (no `Release/` folder) and the game module in
`build/module-full-vectors-clang/gGWWE01_recomp.so`. The module build is the long step;
lower `--jobs` if the compiler runs out of memory.

## Play

```sh
python3 launcher/wario_launcher.pyw
```

The starter uses the playtest profile in `private/playtest-user` (saves and settings), starts
the runner with `--wayland --graphics Vulkan` and writes the log to `private/playtest-last.log`.

Keys on Linux: Tab opens the in-game menu, F12 saves a bug report snapshot, F11 or Alt+Enter
toggles fullscreen. The menu also works with the controller (Back) and the mouse.

## Hidden tests

`scripts/smoke_boot.py` finds the Linux build outputs. Pass `--graphics Vulkan` (the headless
OpenGL path needs a hidden Win32 window and does not exist on Linux), for example:

```sh
python3 scripts/smoke_boot.py --module build/module-full-vectors-clang/gGWWE01_recomp.so \
    --graphics Vulkan --seconds 60 --capture-cadence 15
```

## Not available on Linux yet

- The release starter (WarioWorldRecomp.exe) and the release zip.
- Clang PGO module builds (`--pgo-generate` / `--pgo-use` use clang-cl flags) and
  `scripts/build_instrumented.py`.
- The menu's "Extract all textures", "Open extracted textures", "Open HD texture folder" and
  "Open last log" buttons (they start Windows processes) and the graphics backend choice.
- "Auto" frame rate reads the monitor's refresh rate through Windows calls; on Linux it
  always picks 2x (120 FPS). The fixed 60/120/180/240 settings work.
- Frame pacing against the display's vblank (D3DKMT on Windows); interpolated frames are
  paced without a display clock.
- Menu scaling for the monitor's DPI.

## Linux-specific notes

- The game module is linked with ModernGekko's version script `module.exports`, which hides
  every symbol it does not list. `build_rel_bundle.py` adds `wario_*` to it: without
  `wario_runtime_pc_module` the runtime falls back to scanning guest RAM for REL headers on
  every instruction cache invalidation, and the game runs at about a tenth of full speed.
- The in-game menu finds the module's exports with `dlopen("gGWWE01_recomp.so", RTLD_NOLOAD)`,
  the Linux counterpart of `GetModuleHandleW(L"gGWWE01_recomp.dll")`.
