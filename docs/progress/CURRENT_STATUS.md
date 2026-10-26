# Current status (2026-10-26, evening)

Read this first, then NEXT_ACTIONS.md, KNOWN_ISSUES.md, ../START_HERE.md.

## Works (evidence in TEST_RESULTS.md)

- Boot, title, new save, hub, World 1 entry, Greenhorn Forest movement.
- Human: Xbox controller, stage one cleared and saved.
- Loading the human's progressed save (copy) from the file menu reaches the hub.
- Water animates at the first Greenhorn river in hidden tests.

## Broken / open

- KI-001 slowdowns: mitigated (clang module + runtime dispatch fixes; idle
  headroom ~2x, boot dip 0.53x -> ~0.9x). Lockstep-validated. Human retest pending.
- KI-002 frozen water: not reproduced at 1x; location unknown.
- Greenhorn Ruins, bosses, worlds 2-4, ending: untested.

## Latest builds

| Artifact | Path | Status |
|---|---|---|
| Release runner | build/moderngekko/Release/moderngekko-run.exe | launcher; dispatch fixes (2026-10-26 17:26); previous copy private/moderngekko-run.before-20261026-dispatch.exe |
| Profiling runner (PDB, same /O2) | build/moderngekko-prof/RelWithDebInfo/moderngekko-run.exe | same source as release |
| Clean module, clang | build/module-full-vectors-clang/gGWWE01_recomp.dll | launcher default |
| Clean module, MSVC | build/module-full-vectors/Release/gGWWE01_recomp.dll | fallback (set WARIO_MODULE=msvc) |
| Lockstep twin, clang | build/module-rel-bundle-vectors-clang/gGWWE01_recomp.dll | validated, 0 reports |

## Reproduce

```powershell
python scripts/build_rel_bundle.py --clean --vectors --clang   # clang clean module
python scripts/build_rel_bundle.py --vectors --clang           # clang lockstep twin
python scripts/smoke_boot.py --module build/module-full-vectors-clang/gGWWE01_recomp.dll --full --vectors --graphics OpenGL --seconds 40 --load-state <checkpoint> --seed-user <run>/user --profile-at 25 --profile-ms 8000
python scripts/run_summary.py private/runs/<run>
```

Water checkpoint: private/runs/20261026T162519351895Z-ac6873d6 (control/checkpoint.savestate + user/).
Progressed-save seed: private/seeds/progress-save (copy of the human's GCI).

## Regression suite

`python scripts/regression_suite.py` (~7 min, hidden/muted; `--quick` ~3 min):
boot -> save load -> hub, Greenhorn walk+punch speed, river water animation,
and two lockstep routes. Last run 2026-10-26 17:39 UTC: ALL PASS
(reports/regression-20261026T173902Z.json). Run it after every runtime or
module change.
