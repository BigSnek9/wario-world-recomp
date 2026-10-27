# Current status (2026-10-27, night)

Read this first, then NEXT_ACTIONS.md, KNOWN_ISSUES.md, ../START_HERE.md.

## Works (evidence in TEST_RESULTS.md)

- **Human playthrough:** Xbox controller via launcher/wario_launcher.pyw. Worlds 1-3
  done, World 4 in progress, no gameplay bugs reported. Play tracker states for
  every area are in private/play-sessions.
- **Boot to hub:** boot, title, file select and hub load from the progressed
  save.
- **Regression:** scripts/regression_suite.py passes (boot, no
  interpreter/JIT, Greenhorn speed, river animation, two lockstep routes with
  0 reports).

## Release package (2026-10-27)

- `WarioWorldRecomp.exe` (release/launcher, native C++): first run checks and extracts
  the player's disc, then starts the game like launcher/wario_launcher.pyw (no play
  tracker). `scripts/make_release.py` builds dist/WarioWorldRecomp-vX.Y.zip (46 MB for
  v1.0); `release/test_release.py` is the clean-folder test. Checklist:
  ../PUBLISHING.md. Notes draft: ../release/v1.0.md. Not uploaded.
- Game icon (starter and installer): the gold W coin texture from the player's disc
  (ATT.RSC 0x1148A0, 32x32 CMPR, tex1_32x32_m_5b7df270a43b0ca3_14); the exe's own icon is
  an original coin drawing.

## Static-recomp status

All game code (main.dol + 8 RELs) is compiled to native code. On the tested
routes no game instruction runs in Dolphin's interpreter or JIT
(hook_interp=0, JIT 0).

## Optional enhancements

All are off or "Original" for accuracy, and all are in the in-game menu (Back on
the controller, or Tab). Changes apply live and are saved to
`<user>/Config/WarioWorld.ini`. See ../modding/IN_GAME_MENU.md.

- **Resolution:** Auto (fits the window), 1x-8x.
- **Aspect ratio:** Auto / 16:9 / 16:10 / 21:9 / 32:9.
  - Hor+ with culling widened.
  - Edge HUD anchored to the real screen edges; fades and afterimage widened.
  - See ../modding/WIDESCREEN_SUPPORT.md.
- **Frame rate:** 60 / 120 / 180 / 240 / Auto (monitor refresh). Each game frame
  is re-rendered with the camera and objects in between. Objects carry exact
  identities from the game's own matrix stack (module hooks), so there is no
  guessing. See ../modding/FPS_UNLOCK.md.
- **Other:** HD textures, HDR (Vulkan), volume, moon-jump cheat, menu size.
- **Launcher:** now only build, backend, Play and texture tools.

## Broken / open

- KI-002 frozen water: not reproduced; the human says the water is not meant
  to animate there.
- **FPS pacing at 3x/4x** follows the game's own frame-time irregularity (some
  frames take two refreshes). At 2x, 97-99% of gaps are on pace in steady
  scenes.
- **HUD anchoring:** boss HP bars, minigame timers and the pause menu are
  unchecked in wide aspects.
- World 4 and the ending: human playthrough in progress.

## Latest builds

| Artifact | Path | Status |
|---|---|---|
| Release runner | build/moderngekko/Release/moderngekko-run.exe | launcher; FPS, menu, aspect, state-load reset |
| Profiling runner (PDB, same /O2) | build/moderngekko-prof/RelWithDebInfo/moderngekko-run.exe | same source; used by hidden tests |
| Clean module, clang PGO | build/module-full-vectors-clang-pgo/gGWWE01_recomp.dll | launcher default; HUD/overlay sites, matrix-stack hooks |
| Lockstep twin, clang PGO | build/module-rel-bundle-vectors-clang-pgo/gGWWE01_recomp.dll | 12557/0, 14242/0 (2026-10-27) |

## Reproduce

```powershell
python scripts/apply_tool_fixes.py                                  # runtime source fixes
python scripts/build_rel_bundle.py --vectors --clean --clang --pgo-use private/pgo/merged.profdata
python scripts/build_rel_bundle.py --vectors --clang --pgo-use private/pgo-twin/merged.profdata
python scripts/regression_suite.py                                  # add --quick to skip lockstep
python scripts/fps_matrix.py --multipliers 2 4 --scenes hub boss greenhorn
python scripts/fps_flicker_check.py --scene boss --objects
python scripts/fps_world_sweep.py                                   # every play-tracker state
```

Progressed-save seed: private/seeds/progress-save. Hub savestate:
private/runs/20261026T232050303943Z-da9e08f9.
