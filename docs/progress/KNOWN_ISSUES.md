# Known issues

IDs here are stable. Older accuracy items A001-A019 live in ../ACCURACY_ISSUES.md.

## KI-001 Host slowdowns (A018) - mitigated, awaiting human retest

- Human report: slowdowns in Greenhorn Forest, including when breaking boxes.
- Hidden evidence (2026-10-26): host speed falls to ~0.53-0.57x for 1-2 s
  around 14-17 s after boot (title/intro load), reproducible across runs.
  Not fixed by dual-core mode (Core.CPUThread=True gave the same dip).
- Sampling profile of that window: the emulation thread ("CPU-GPU thread",
  single-core mode) spends ~0.75 s fully busy inside the runtime executable
  (not game code, not waiting). Symbol-enabled runtime build in progress to
  name the hot functions.
- Calm gameplay (river scene): emulation thread ~49% game code, ~24% waiting.
  Hardware: Ryzen 7 9800X3D, RTX 5090 - GPU is not the bottleneck.
- Box-breaking slowdown not reproduced yet (no box scenario captured).
- Mitigations 2026-10-26: clang-built module (game code ~1.75x faster;
  gameplay idle 23% -> ~43%), host_call only wired when mods are loaded,
  allocation-free REL revalidation. Boot dip 0.53x -> ~0.88x. Needs the human to
  replay Greenhorn Forest with Play-WarioWorld.cmd.

## KI-002 Frozen water (A017) - not reproduced

- Human report: frozen water in Greenhorn Forest (played at 3x / Auto aspect).
- Hidden test at the first river + waterfall (checkpoint
  private/runs/20261026T162519351895Z-ac6873d6): 15 captures at 1 s show the
  water and waterfall changing every capture (mean abs luma diff 13-21/255,
  repeating with an ~8 s period). So that water animates at 1x.
- Still possible: a different water surface, 3x-only, or an intermittent stop.
  Needs the exact location from the human or a broader sweep.

## KI-003 Transient stretching - probably fixed

- Cause candidate: Dolphin Auto aspect heuristic (the Dolphin wiki reports this
  game flipping 4:3/16:9 at the World 1 boss under Auto). Launcher now forces
  4:3 (ForceStandard). Not re-verified by the human.

## KI-004 Capture commands lost during long pad holds - test harness

- smoke_boot.py screenshot requests issued during a long `pad_frames` hold are
  marked processed but no PNG is written. Use captures between holds or idle
  checkpoints. Not a game bug.
