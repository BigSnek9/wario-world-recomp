# Accuracy and acceptance

The PC executable cannot have the same machine-code bytes as a GameCube DOL.
The acceptance goal is equivalent guest-visible behavior. Source extraction
can and does have a separate literal byte-for-byte check.

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
