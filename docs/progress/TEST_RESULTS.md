# Test results

All runs hidden + muted. Sections are dated; the early ones used OpenGL, 1x,
4:3 and the MSVC module build/module-full-vectors/Release/gGWWE01_recomp.dll,
later ones the clang PGO module unless stated. Run folders are under
private/runs/ (private). Summaries: `python scripts/run_summary.py <run>`.
Current state: CURRENT_STATUS.md.

## Gameplay test matrix

| Area | Status | Evidence |
|---|---|---|
| Boot, Nintendo logo, title | pass | many runs |
| New save creation | pass (earlier session) | ../PROGRESS.md (2026-10-26) |
| Load progressed save (copy of human save, stage 1 cleared) | pass: slot shows 10/26/26 12:37, Start loads hub | 20261026T162208773301Z-b814d6ac |
| Hub / World 1 entry | pass | probes enter_world1 / enter_greenhorn |
| Greenhorn Forest walk to first river | pass, speed ~1.0 | 20261026T162357957453Z-71be5d71 |
| Water animation (first river) | animates | 20261026T162614917608Z-200ad64b |
| Combat / enemy defeat | human only | user report |
| Stage clear | human only (stage 1) | user report |
| Save after progression, reboot, Continue | pass via human save file loading | above |
| Stage 2 (first half) | human: no issues (2026-10-26 evening, clang build, fullscreen) | private/playtest-last.log |
| Whole game, all worlds, bosses, ending | human playthrough finished (by 2026-10-27) | owner report; play-tracker states in private/play-sessions |
| Every play-tracker area with frame generation | 46 states, 2x camera + objects | reports/fps-world-sweep.json |
| REL modules 1-4, 6 | loaded during the playthrough; only REL 5, 7, 8 independently audited | ../engine/ARCHITECTURE.md |
| Audio equivalence | one idle capture only | ../PROGRESS.md |
| Long-session stability | the full human playthrough; no dedicated soak test | |

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

## 2026-10-26 night: PGO twin incl. widescreen quad variable (default 320)

| Route | checks | reports |
|---|---|---|
| title -> save load -> hub | 14,243 | 0 |
| Greenhorn walk | 12,601 | 0 |

Earlier PGO twin (before the quad change): Greenhorn 12,555/0, title-hub
14,225/0, W1 arena R12 5,768/0, W2 boss B21 5,245/0.

## 2026-10-26 late night: optional 120 FPS interpolation (prof runner, hidden, OpenGL)

| Run | Interpolated | Skipped (cut / no cam / late) | Speed min | Notes |
|---|---|---|---|---|
| Greenhorn walk_punch, FPS on | 1790/1800 | 1 / 7 / 2 | 0.985 | mid frame 8.46 ms after real (avg) |
| Greenhorn, identity replay | 1790/1800 | - | 0.989 | 15/17 dumped pairs pixel-identical |
| CB41 boss, FPS on, final pacing | 2094/2100 | 1 / 3 / 109 | 0.992 | gaps 6-10 ms: 3833/4079 |
| CB21 boss, FPS on, final pacing | 2094/2100 | 1 / 3 / 30 | 0.999 | |
| CB41 / CB21 boss, FPS off | - | - | 1.000 / 0.999 | baseline |
| CB41 / CB21, first pacing (video-thread sleep) | 2094 | - | 0.931 / 0.907 | replaced |
| CB41 boss, release runner, Vulkan, FPS on | 2094/2100 | - / - / 72 | 0.969 (one 1 s sample) | gaps 6-10 ms: 3918 |
| CB41 boss, release runner, Vulkan, FPS off | - | - | 1.000 | baseline |

Regression suite --quick with FPS off (prof runner): ALL PASS
(reports/regression-20261026T224236Z.json).

## 2026-10-26 late night 2: object interpolation + queued pacing + overlay widening

| Run | Speed min | Notes |
|---|---|---|
| Hub savestate, FPS on (prof, OpenGL) | 1.000 | gaps 6-10 ms 2968/2988, matrices interpolated |
| CB41 boss, FPS on | 0.999 | gaps 6-10 ms 2852/2954 |
| Greenhorn walk_punch, FPS on | 0.992 | 96.5% matrix loads matched |
| Release runner, 16:9, FPS on, boot -> hub (Vulkan) | 0.873 (title boot dip, same as off) | no loading-coin trails; fade full width |
| Regression --quick, FPS off, new module | ALL PASS | reports/regression-20261026T233143Z.json |
| Hub A/B (prof): FPS off / on with sleep / no sleep | 0.998 / 0.954 / 1.000 | mid-frame sleep was the cost |

## 2026-10-27 early morning: game-level FPS interpolation

| Check | Result |
|---|---|
| Full regression incl. lockstep, hooked modules | ALL PASS; lockstep 12599/0, 14235/0 |
| Blob flicker (eroded), 2x camera + objects | boss 0.000, hub 0.000, Greenhorn 0.002, lava CF43 0.14 (camera-only 0.32) |
| Identity collisions (repeat with different matrix) | 0 in boss/Greenhorn/CF22/CF41; castle ribbon loop repeats are order-stable |
| World sweep, 46 play-tracker states (2x, objects) | reports/fps-world-sweep.json |
| 4x speed, heaviest areas (AR42, CF22, AR21, CTT, CF51, CF43), no dumps | 0.998-1.000 (AR42 1.000 after skipping idle clock reads) |
| Menu snapshot (MODERNGEKKO_WARIO_MENU_TEST) | renders; text follows display scaling, nothing clipped |

## 2026-10-27 evening: release zip v1.0 (clean-folder test)

`python scripts/make_release.py --version 1.0` (commit 6ad89d2): dist/WarioWorldRecomp-v1.0.zip,
46.3 MB (2683 files, 168 MB unpacked: runner, Sys, VC++ runtime DLLs, PGO module, starter,
licences). Release check passed (no disc-derived file by content hash, no sources/PDBs/logs/
user data); a negative test flagged a copied REL, boot.bin, a .c file and a user/ folder.

`python release/test_release.py --iso <USA iso> --seconds 30 --smoke` (hidden, muted), report
private/runs/20261027T193650560431Z-25169418-release-test/report.json:

| Check | Result |
|---|---|
| First-run setup (`--iso --setup-only --quiet`: hash 1.46 GB, extract, verify, config, icon) | 0.94 s, warm file cache; uncached read of the ISO on this NVMe drive 0.5 s |
| Extraction vs original/GWWE01 (250 files) and pinned DOL/REL hashes | byte-equal; all pinned hashes match; ISO size/mtime unchanged |
| Coin icon, C++ vs installer/coin_icon.py | byte-identical |
| config.ini, GFX.ini, Logger.ini, Dolphin.ini, GCPadNew.ini vs the Python starter | equal (parsed) |
| Wrong-disc paths (not GC, .rvz, PAL, rev 1, wrong size, same size + wrong hash) | clear messages, exit 5, existing game kept |
| Hidden boot through the starter (`--hidden-test 30`, OpenGL headless, muted) | exit 0; black at 10/15 s, title screen at 20/25 s |
| smoke_boot.py on the release runner/module/game (30 s, OpenGL) | exit 0, fps 59.94, speed 1.000 |

Not covered: the interactive dialogs (intro, file picker, progress, errors) and the window /
taskbar icon need a visible session; a machine without the VC++ runtime installed.
