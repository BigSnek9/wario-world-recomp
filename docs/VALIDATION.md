# Accuracy and acceptance

The PC executable cannot have the same machine-code bytes as a GameCube DOL.
The acceptance goal is equivalent guest-visible behavior. Source extraction
can and does have a separate literal byte-for-byte check.

## Status (2026-10-27)

Sections below are dated checkpoints. Current state: progress/CURRENT_STATUS.md.
The criteria in "Not established" still define what a parity claim needs; the
full manual playthrough and zero-interpreter routes are playability and coverage
evidence, not proof. The FPS work was done as a separate, optional layer
(modding/FPS_UNLOCK.md).

## Review correction, 2026-10-26

Read ACCURACY_REVIEW.md before interpreting historical results below. Manual
3x/Auto settings differed from 1x tests; runtime rendering shortcuts were not
validated. Shared native/JIT rendering cannot detect common renderer defects.
Presentation now explicitly 4:3/native 1x; this does not close rendering accuracy.

## Already established

- Disc identity/hash pinned; all 245 FST files and extracted main DOL match ISO.
- DOL/REL structure and import-ID inventory; no original bytes patched.
- Exact FP semantics requested for first translation.

## Not established

Successful translation does not prove code discovery completeness, relocation
correctness, branch dispatch, floating-point parity, or game playability.
Matching a screenshot does not prove CPU state or future behavior matches.
An emulator reference is valuable, but cannot alone prove hardware bit accuracy.

Before declaring a complete static recomp:

1. Main DOL and all eight RELs must execute through compiled code with their
   original runtime linking/lifetime behavior. Record and eliminate unexpected
   interpreter/JIT fallback; a fallback-enabled boot is a diagnostic milestone.
2. Review every generated SMC warning, exception/vector setup, code copy and
   relocation; justify ignored false positives with evidence.
3. Differential-test registers, CR/XER/FPSCR, GQR, floating-point/paired-single
   bit patterns, relevant RAM, exceptions and guest cycle/event ordering.
4. Replay fixed controller inputs from clean boot and known memory-card states.
   Cover intro/title, menus, each stage/module, bosses, saves/loads, pause,
   transitions, death/retry, resets, movies and audio effects/streaming.
5. Compare EFB/XFB output at original resolution and video modes, including
   blending, depth, texture conversion, interlacing/field parity and gamma;
   compare audio sample counts and buffers, not host capture timestamps alone.
6. Record exact source revisions, settings, input replay, save hashes, first
   divergence and known differences. Keep captures and game memory private.

Only after baseline acceptance begin the separate FPS change set. Keep a fixed
simulation clock, use interpolation where valid, and repeat parity/replay tests
at 30/60/120/144/165/240 Hz and with irregular presentation intervals.

## Diagnostic comparison boundaries

Use build_instrumented.py then smoke_boot.py --instrumented --lockstep
--lockstep-limit 0 for broad checks with an exact instruction-count boundary.
Confirm exact_instruction_count=1 in the log. The normal DLL uses the older
cycle-based heuristic. Neither path checks skipped helper blocks or JIT RELs.

--reference uses the same runtime's original-code JIT as a diagnostic comparison,
not hardware or an independently validated emulator. Probes use frame counters;
verify actual input latching and initial save/controller state before claiming
deterministic replay. Input probes currently reach differing save prompts.

The original fallback counter covers interpreter steps only. Check separate
[wario-jit] entries as well as hook_fb. These count JIT transfers, not guest
instructions. Cache fast paths also increment hook_fb.

## Latest verified checkpoint: 2026-10-26, clean hub build

All testing is hidden and muted (project rule). The main runtime now
supports an invisible Windows rendering surface; do not launch a GUI test.
F project write access was available for this checkpoint; source and patches are integrated.

Best uninstrumented candidate: build/module-full-vectors/Release/gGWWE01_recomp.dll
SHA256 d848261fe4c8277e0164cdd746f9daa479fbaccadc9a1c702042471f9798ed9f.
It includes main, all eight RELs and the SDK vector/startup copies. Export audit
confirms required ABI/REL hooks and absence of the instruction-count journal.
Run 20261026T105730237471Z-91c90501: 120 seconds, natural save creation, hub and
pause book rendered, clean exit, original speed near 59.94 FPS/VPS; JIT entries
zero, 97 executable hash checks, smc_failed=0. It is NOT a lockstep run.

Checked twin: build/module-rel-bundle-vectors/Release/gGWWE01_recomp.dll.
Hub run 20261026T105101421481Z-379aa3dc: 9066 checks / zero reports / zero JIT.
Movement run 20261026T105549637900Z-c1ec75df: 150 seconds, actual hub movement,
8903 checks / zero reports / zero JIT; 45 helper skips and 75 zero-instruction
skips, no cap/filter/undercharge events; 97 code-hash checks, no failures.
Counts are deduplicated PER RUN; do not add them as unique cumulative coverage.
The movement test visibly changed Wario/camera position but did not establish
entry into a stage. Per-instruction hardware helper calls remain in both builds.

Evidence summaries: reports/hub-validation-20261026.json,
reports/hub-rel-audit-20261026.json, reports/full-vectors-exports.json.
Loaded WWUSPF (ID 7) code: all 190272 bytes match independent relocation;
all 757 initialized-data relocation sites match, one legal non-site marker change.
Patch replay reproduces every changed upstream source file from its pinned HEAD
across all four checkouts: scripts/verify_patch_replay.py, reports/patch-replay.json.
Original DOL/eight REL hashes were rechecked unchanged after these runs.

Rebuild: python scripts/build_rel_bundle.py --clean --vectors
Checked build: python scripts/build_rel_bundle.py --vectors
Bounded hidden run: python scripts/smoke_boot.py --full --vectors --graphics OpenGL
--seconds 120 --probe-file config/probes/start_adventure.json --pad-hold 12
For CPU checking omit --full and add --lockstep --lockstep-limit 0.
Use --probe-file config/probes/hub_movement.json --seconds 150 for movement.
Detailed probe format/limits are in docs/PROBES.md. Do not use the old D-pad Yes
probe; analog main_y=1 resolves the supposed memory-card failure without patches.

Next required work: navigate into the first stage, exercise additional RELs and
load/unload/reload lifetimes, combat/collision/cutscenes/audio/save reload; inventory
remaining hardware/interpreter helpers; deterministic input/tick replay and
pixel/audio/reference comparisons; continue the frame-dependency audit. T006
already proves fixed-step REL arithmetic. FPS is still capped at original speed.
Full-game bit accuracy and full static coverage remain unproven. No installation
or publication was performed. Historical checkpoints follow below.


## 2026-10-26 additional validation

Greenhorn Forest transition: 12785 checks / 0 reports / 0 JIT, followed by
checked and uninstrumented stage checkpoint reload/input tests. Full loaded main
text audit compares 1599232 original bytes exactly. The stage's active update
is in main; live REL queue is empty, so this does not exercise WWUSS1.

The verifier now deduplicates by PC and code-map generation, not PC alone.
Nine compiled regression controls pass. Nine module-queue controls pass; audits
exclude stale unlinked headers. Six exact-PCM negative controls pass, including
single-bit errors and retained trailing silence. Normal unittest discovery runs
29 Python cases without invoking an incidental native build on import.

Silent native/reference audio captures from one idle stage checkpoint match
515064 stereo 16-bit sample frames (16.0816785 seconds at reported 32028 Hz)
after explicit initial-zero alignment. No timing/onset or hardware/full-game
parity claim follows from this alignment. Neither WAV was played.

A fresh-boot outer-card-read test passes 18678 checks / zero reports / zero JIT,
with genuine copied diagnostic user data. Slots still say New: actual gameplay
save-point/stage-clear/reboot/Continue progression is NOT validated by this test
(the later manual playthrough exercised it in practice).
