# Current status (2026-10-27)

This is the authoritative summary of where the project stands. Read it first,
then NEXT_ACTIONS.md and KNOWN_ISSUES.md. History: DEVELOPMENT_LOG.md (from
2026-10-26 afternoon) and ../PROGRESS.md (2026-10-24..26). Index of all docs:
../README.md.

## Works

- **Full game:** playable start to finish. The owner finished a full
  playthrough by 2026-10-27.
- **Static recomp:** main.dol and all eight RELs are compiled to native code
  (clang, PGO). On the tested routes no game instruction runs in Dolphin's
  interpreter or JIT (hook_interp=0, JIT entries 0; see ../ACCURACY_ISSUES.md
  A003). This is not a bit-accuracy claim (../ACCURACY_REVIEW.md).
- **Regression:** `scripts/regression_suite.py` passes (boot, no interpreter /
  JIT, Greenhorn speed, river animation, two lockstep routes with 0 reports).
  Evidence: TEST_RESULTS.md.

## Enhancements (all optional, all in the in-game menu)

Open with Back on the controller or Tab. Changes apply live and are saved to
`<user>/Config/WarioWorld.ini`. The accurate choices (native 1x, original 4:3,
60 FPS) are labelled in the menu. Details: ../modding/IN_GAME_MENU.md.

- **Frame generation:** 60 / 120 / 180 / 240 FPS or match the monitor. Each
  game frame is re-rendered with the camera and objects in between, using
  identities from the game's own matrix stack. Display-locked pacing (a vblank
  clock thread; one frame per refresh). ../modding/FPS_UNLOCK.md.
- **Widescreen:** any aspect, Hor+. HUD anchored to the screen edges; the pause
  book, speech boxes and results paper keep their 4:3 shape.
  ../modding/WIDESCREEN_SUPPORT.md.
- **Internal resolution:** up to 8x, or match the window.
- **HDR (Vulkan):** paper white, peak, highlight boost, white level, vibrance,
  contrast, saturation, gamma, black level, menu brightness in nits. Warmth was
  removed.
- **HD texture packs** with background streaming (at most 32 MB of uploads per
  frame), plus a texture extractor (`scripts/extract_textures.py`).
- **Audio mixer:** master, music, SFX, mute pause-menu music. No Voice slider
  yet (KNOWN_ISSUES.md KI-009). ../engine/AUDIO.md.
- **Performance mode:** Dolphin dual core; applies after a restart.
- **Cheats:** walk through walls, super punches, jump height (formerly "moon
  jump"), unlock all stages, collect all. The last two are permanent once the
  game saves. ../modding/CHEATS.md.
- **Controls:** GameCube-layout defaults, rebinding, rumble. ../CONTROLS.md.
- **Other:** fullscreen, OpenGL / Vulkan, menu styles and size, F12 bug-report
  snapshot (savestate + screenshot).

## How it is started and shipped

- **From this repo:** `Play-WarioWorld.cmd` runs the windowless starter
  `launcher/wario_launcher.pyw` with the owner's profile in
  `private/playtest-user` (saves kept). The old cheats helper and
  `Launch-WarioWorld.cmd` were removed; cheats are in the menu.
- **Release zip (ShadowRecomp style):** `WarioWorldRecomp.exe` (native starter,
  `release/launcher/`) plus runtime and compiled module; the player supplies
  their own ISO and setup takes about 1 s. Built by `scripts/make_release.py`,
  tested by `release/test_release.py`. ../PUBLISHING.md, ../release/v1.0.md.
  Not uploaded.
- **Build from ISO:** `Install-WarioWorld.cmd` (`installer/`) builds and
  installs the game on the player's PC.

## Open

See KNOWN_ISSUES.md: trapdoor glow flicker (needs an F12 snapshot), speech
board figure and results paper not yet confirmed on screen, Voice slider
parked, GPL source availability before any public release. The repository is
private.

## Builds

| Artifact | Path | Use |
|---|---|---|
| Release runner | build/moderngekko/Release/moderngekko-run.exe | starter and release zip |
| Profiling runner (PDB, same /O2) | build/moderngekko-prof/RelWithDebInfo/moderngekko-run.exe | hidden tests |
| Clean module, clang PGO | build/module-full-vectors-clang-pgo/gGWWE01_recomp.dll | starter and release zip |
| Lockstep twin, clang PGO | build/module-rel-bundle-vectors-clang-pgo/gGWWE01_recomp.dll | lockstep checks |

## Reproduce

```powershell
python scripts/apply_tool_fixes.py                                  # runtime source fixes
python scripts/build_rel_bundle.py --vectors --clean --clang --pgo-use private/pgo/merged.profdata
python scripts/build_rel_bundle.py --vectors --clang --pgo-use private/pgo-twin/merged.profdata
python scripts/regression_suite.py                                  # add --quick to skip lockstep
python scripts/fps_world_sweep.py                                   # every play-tracker state
python scripts/make_release.py --version X.Y --build-launcher       # see ../PUBLISHING.md
```

Progressed-save seed: private/seeds/progress-save. Play-tracker states for
every area: private/play-sessions. All tests hidden and muted (../../AGENTS.md).
