# Frame and refresh dependency ledger

Baseline: no FPS, refresh, widescreen, logic, or speed patches. A future renderer
must preserve the original guest simulation clock, interrupt schedule and input
sampling until measured evidence justifies a change. Do not assume that display
refresh, VI interrupts, rendered frames and game updates have identical rates.
Actual cadence and region-specific timing have not yet been measured.

## Uncap mod pointers (summary for the later FPS project)

Nothing below is patched today; these are the documented intervention points.

1. Simulation gate: main.dol 0x8002FD2C -> 0x801A87C4 retrace wait (T001).
   The main loop updates gameplay, then sleeps until the VI counter changes.
   Any uncap must decouple updates from this wait without changing update math.
2. Input sampling: SISetSamplingRate(0) at 0x8004AA38 (T002). Latch inputs at
   original guest times; do not poll once per host frame.
3. Guest clock: OSGetTime/OSGetTick 0x801A4158/0x801A4170 and alarms (T003).
   Keep tick arithmetic, wraparound and frequency guest-accurate.
4. Modules: all eight RELs show zero direct timing evidence (T004 scan,
   2026-10-25); their cadence arrives through main's vtable-driven update path,
   so uncap changes stay in main.dol scheduling.
5. Presentation: framebuffer toggles at 0x80041B30 and draw-done callback
   0x80042280 (T005). Presents already outnumber frame callbacks roughly 2:1 in
   diagnostics; interpolate only after validating guest completion events.
6. Fixed-step logic example: WWUSTT title damped update (T006) has no elapsed
   time argument; calling it per uncapped present would change damping and
   transition timing. All such fixed-step callbacks must stay on the original
   schedule with presentation-side interpolation.


## T001 - Main loop waits for a VI counter transition

Location: main.dol main at 0x8002FC00; call at 0x8002FD2C to 0x801A87C4.
Evidence: dtk assembly auto_main_text.s and auto_03_8018D34C_text.s.
The callee saves interrupt state, reads counter 0x801FE00C, sleeps on queue
0x801FE014 through 0x801A3EBC, then loops until the counter changes. This is
strong static evidence for VIWaitForRetrace behavior; the name is inferred,
not recovered by the signature scanner. Main's update path contains virtual
calls at 0x8002FCBC, 0x8002FCD4, 0x8002FCE4, 0x8002FCFC, 0x8002FD10 and
0x8002FD28 before this wait. Their exact gameplay/render roles remain unknown.

Implication: simply removing the wait or changing VI frequency could change
simulation and input updates. Preserve it for baseline. Later measure calls,
state changes, counter increments and field parity over the same input replay.
Confidence: high for the wait pattern; unconfirmed for full gameplay cadence.

## T002 - Controller sampling setup

Location: main.dol 0x8004AA14; call at 0x8004AA38 to signature-identified
SISetSamplingRate (0x801A7C68), with r3 = 0.
Evidence: auto_fn_8004AA14_text.s, dtk-main-info.txt.
Implication: preserve serial-interface sample scheduling and latch inputs at
original guest times. Polling once per host-rendered frame could alter button
edges, repeats, analog paths, or latency. The meaning of rate index zero and
effective cadence must be confirmed with the target's SI/VI tables at runtime.
Confidence: high for the call/argument; no runtime rate measurement yet.

## T003 - Guest time-base functions

Locations: OSGetTime 0x801A4158, OSGetTick 0x801A4170, plus system-time/alarm
callers listed in reports/timing-candidates.csv.
Evidence: identified SDK functions and encoded time-base read instructions.
Implication: guest tick arithmetic must retain wraparound, paired reads,
frequency and alarm scheduling. Do not tie it to host presentation count.
Confidence: static instruction/call evidence only. Many uses are SDK I/O
timeouts rather than gameplay frame dependencies.

## T004 - Module update paths

Locations: eight RELs; use module ID + original section index + section offset,
never an assumed runtime address. The main loop calls the active object at
global 0x801FD910 through its vtable. Module prologs populate this object.
Implication: audit update functions in every module, not just main.dol.
Status: entry/vtable path identified; physics, animation, particles, camera,
collision, hit stop, RNG, timers, cutscenes and audio synchronization unaudited.

### REL timing scan, 2026-10-25 (negative result)

scripts/rel_timing_candidates.py scanned all eight RELs over all 610,180
executable words and 30,289 non-executable initialized data words:
- zero timebase/decrementer SPR reads or writes;
- zero addis of 0xCC00/0xCD00 hardware bases (any destination register);
- zero absolute 0xCC000000..0xCDFFFFFF words in data sections;
- zero REL24/ADDR32/HA/LO relocations whose main-module symbol matches a
  timing routine (447 identified SDK/main symbols from reports/dtk-main-info.txt;
  addends mostly target unnamed game functions, so unnamed wrappers remain
  invisible to this check).
Output: reports/timing-candidates-rel.csv (header only, zero rows).
Confidence: high that no REL contains direct timing evidence of the kinds
scanned; low coverage for indirect timing through unnamed main-module wrappers.
Working conclusion: module cadence is fully mediated by main.dol via the
vtable-driven update path (T001/T004). A future FPS uncap therefore centers on
main.dol's retrace wait and its scheduling, not inside the RELs. Revisit with
renamed wrappers (Ghidra) before treating this as proof that modules never
gate on time.

## Raw candidate inventory

reports/timing-candidates.csv currently contains 297 linear-scan candidates:
169 hardware-base loads; 115 direct calls to recognized SDK timing routines;
13 timing-SPR reads/writes. Embedded data can produce false positives, and
indirect calls or game counters can evade this scan. This is not a complete
frame-dependency audit. Preserve raw instruction words and locations privately.

## Required evidence for each new entry

Record module/version/hash, address or section offset, original operation,
units/cadence, call chain and evidence location, confidence, proposed future
handling, and a replay that detects behavior drift. Promote a candidate to
confirmed only after checking control/data flow or runtime measurements.

## Decompiler follow-up, 2026-10-25

Ghidra confirms T001's wait. Object 0x801FD910 receives vtable calls at offsets
0x48, 0x4C, 0x50 when flag 0x801FD930 bit 2 is clear, otherwise 0x44; calls
0x58 then 0x54 occur before waiting. Their exact simulation/render roles remain
unassigned. Evidence: reports/ghidra-bootstrap/8002fc00.c and 801a87c4.c.

T002 clamps the sampling index to 0..11, chooses tables at 0x801CD850 or
0x801CD880 by VI television format, and scales a parameter by VI register
0xCC00206C bit 0 (factor one or two) before SISetXY. Index zero does not imply
host-frame polling. Evidence: reports/ghidra-loader-timing.json, 0x801A7C68.

## T005 - Framebuffer swaps and draw completion

Location: main.dol 0x80041B30 toggles framebuffer index 0x801FDA14 as 1-index;
graphics setup 0x80040F58 installs draw-completion callback 0x80042280.
Evidence: reports/ghidra-loader-timing.json. Confidence: static control flow.
Future handling: distinguish guest draw completion, XFB swaps, VI fields and
host presents before inserting interpolated frames. A 90-second diagnostic
reports about twice as many presents as frame callbacks. Neither counter proves
game update cadence. Measure callback/swap timestamps against guest ticks and
replay fixed input through loading, gameplay and cutscenes before changing it.

## T006 - Title module has a fixed-step damped update

Module: WWUSTT, ID 8, pinned SHA-256 in config/project.json. Section 3 offset
0x4734 is the active title object's vtable +0x48 callback in the paused snapshot.
It calls section 3 offset 0xAB4 through the object pointer at +0x3C.
Evidence: private/runs/20261025T103819667331Z/control/mem1-low.bin and
generated/analysis/WWUSTT/asm/auto_00_00000000_text.s. Observed vtable 0x804B91A8,
callback 0x804B3DAC; addresses are observations, not fixed allocation assumptions.

The callee updates float fields x=object+0x2C and v=object+0x30 on each call.
When byte +0x38 is nonzero: v += 0.5*(1-x), then v *= 0.75.
Otherwise: v += 0.25*(-x), then v *= 0.5, and byte +0x39 is set to one.
Then x += v. The lower bound clamps x/v to zero; upper bound clamps x to one,
negates v and clears byte +0x39. Preserve actual fused/single operations when
validating; these equations describe control flow, not equivalent replacement C.
Constants come from original section 6 offsets 0, 0x14, 0x18 and 0x1C.

Confidence: high for per-call fixed-step arithmetic; the visual property's role
is not yet identified. There is no elapsed-time argument in this routine. Its
caller is on the main loop's pre-retrace update path, so running it per uncapped
presentation would change damping, bounds and transition timing. Keep it on the
original simulation schedule and interpolate presentation only after validation.
Required replay: trigger the corresponding title/menu transition, record x/v,
flags and update count at guest ticks, and compare at differing host refresh rates.
