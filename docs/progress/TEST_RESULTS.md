# Test results

All runs hidden + muted (OpenGL, 1x, 4:3), clean module
build/module-full-vectors/Release/gGWWE01_recomp.dll unless stated. Run folders
are under private/runs/ (private). Summaries: `python scripts/run_summary.py <run>`.

## Gameplay test matrix

| Area | Status | Evidence |
|---|---|---|
| Boot, Nintendo logo, title | pass | many runs |
| New save creation | pass (earlier session) | docs/HANDOFF.md |
| Load progressed save (copy of human save, stage 1 cleared) | pass: slot shows 10/26/26 12:37, Start loads hub | 20261026T162208773301Z-b814d6ac |
| Hub / World 1 entry | pass | probes enter_world1 / enter_greenhorn |
| Greenhorn Forest walk to first river | pass, speed ~1.0 | 20261026T162357957453Z-71be5d71 |
| Water animation (first river) | animates | 20261026T162614917608Z-200ad64b |
| Combat / enemy defeat | human only | user report |
| Stage clear | human only (stage 1) | user report |
| Save after progression, reboot, Continue | pass via human save file loading | above |
| Stage 2 (first half) | human: no issues (2026-10-26 evening, clang build, fullscreen) | private/playtest-last.log |
| Rest of stage 2, boss, worlds 2-4, ending | untested | |
| REL modules 1-4, 6 executed | untested | |
| Audio equivalence | one idle capture only | docs/HANDOFF.md |
| Long-session stability | untested | |

## 2026-10-26 performance probes

| Run | Setting | min speed | slow at (s) |
|---|---|---|---|
| 20261026T163124497303Z-f4224d8b | single core | 0.568 | 16-17, 41-42 |
| 20261026T163210433169Z-f1e0ae56 | Core.CPUThread=True | 0.559 | 14-16 |
| 20261026T163301271908Z-dad1790e | single core + profile 13-19 s | 0.525 | 14-16 |

## 2026-10-26 compiler / runtime A/B (water checkpoint, profile 25-33 s)

Share of emulation-thread samples (game code / runtime / idle):

| Module | Runtime | game | runtime | idle |
|---|---|---|---|---|
| MSVC | release | 53.4% | 21.9% | 24.7% |
| clang | release | 33.5% | 22.5% | 44.0% |
| clang | dispatch fixes | 37.2% | 20.3% | 42.5% |

Boot dip (min host speed, ~15 s after launch): MSVC 0.53-0.57; clang 0.68-0.69;
clang + mod early-outs 0.69-0.77; + host_call unwired 0.87-0.88.

## Lockstep (native vs interpreter shadow), zero reports in all

| Twin | Runtime | Route | checks | distinct PCs |
|---|---|---|---|---|
| MSVC | release | Greenhorn walk to river | 12,597 | 7,937 |
| clang | release | Greenhorn walk to river | 12,539 | 7,881 |
| clang | release | title -> save load -> hub | 14,258 | 8,195 |
| clang | dispatch fixes | Greenhorn walk | 12,604 | 7,943 |
| clang | dispatch fixes | title -> save load -> hub | 14,241 | 8,178 |
