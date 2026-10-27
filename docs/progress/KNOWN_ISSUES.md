# Known issues

IDs here are stable. Older accuracy items A001-A019 live in ../ACCURACY_ISSUES.md.

## Open (2026-10-27)

| ID | Issue | Status |
|---|---|---|
| KI-007 | Trapdoor glow flicker | Open. Needs an F12 bug-report snapshot from the spot to reproduce hidden. |
| KI-008 | Widescreen speech board figure (WS-009) and stage results paper icons (WS-010) | Fixed in code, not yet confirmed on screen: no savestate with a board open or a results screen exists. |
| KI-009 | No Voice slider | Parked. Wario's voice clips are ordinary SFX with unidentified ids; needs a listening pass (../engine/AUDIO.md AU-005). |
| KI-004 | Capture commands lost during long pad holds | Test-harness limitation, below. |

Also not checked in a hidden capture: boss HP bars and minigame timers at wide
aspects. Real HDR output on an HDR display and rumble strength need a player's
eyes and hands (../modding/IN_GAME_MENU.md, ../CONTROLS.md).

## KI-001 Host slowdowns (A018) - resolved

- Human report (2026-10-26): slowdowns in Greenhorn Forest, including when
  breaking boxes. Hidden runs found a boot dip to ~0.53-0.57x at the title load.
- Fixes: clang-built module (game code ~1.75x faster), host_call only wired
  when mods are loaded, allocation-free REL revalidation (boot dip -> ~0.88x),
  then clang PGO (KI-006). Later hub / charge-dash slowdowns were the HD texture
  pack's uploads, fixed by upload streaming (../modding/FPS_UNLOCK.md).
- No slowdown report is open after these fixes.

## KI-002 Frozen water (A017) - closed: not a bug

Human side-by-side with Dolphin 2606a (2026-10-26): that water does not animate
in Dolphin either. Hidden captures at the first river show the water there
animating with an ~8 s period.

## KI-003 Transient stretching - closed

Cause candidate: Dolphin's Auto aspect heuristic (the Dolphin wiki reports this
game flipping 4:3/16:9 at the World 1 boss). The original 4:3 mode forces
ForceStandard; the widescreen modes set the host aspect explicitly, so the
heuristic is never used. Not reported again during the playthrough.

## KI-004 Capture commands lost during long pad holds - test harness

smoke_boot.py screenshot requests issued during a long `pad_frames` hold are
marked processed but no PNG is written. Use captures between holds or idle
checkpoints. Not a game bug.

## KI-005 Brighter image than the human's Dolphin - closed: Dolphin-side HDR

The human's Dolphin had HDR processing on (D3D12, HDROutput=True). With it
matched, a side-by-side of the file-select screen shows the same brightness and
colour. The recomp renders the same frame on OpenGL and Vulkan (file-select mean
luma 107.8 vs 107.7).

## KI-006 Speed dips in "Area R" wave arenas - mitigated

- Playthrough telemetry (2026-10-26): R12/R21 arenas showed 1-3 s dips to
  0.79-0.95x. Profile: the generated C cost several times the JIT's code for the
  same work.
- Clang PGO module (profiles from boot, Greenhorn and playthrough checkpoints):
  game code 38.7% -> 29.5% of the emulation thread on the R12 checkpoint. The
  PGO lockstep twin passed (TEST_RESULTS.md) and the PGO module is now the
  default. Further gains would need DolRecomp emitter changes (registers kept
  in ctx, per-instruction pc stores) with lockstep re-validation.

## KI-010 GPL source for a public release - closed

The runtime is GPL. Closed 2026-10-27: the repository is public, each release
attaches its source zip, and the licence notices of every linked component ship
in the zip (../PUBLISHING.md).
