# Frame and refresh dependency ledger

Intent: preserve original simulation speed and video cadence. The game's
simulation still runs at 59.94 Hz in every mode. The optional frame generation
(modding/FPS_UNLOCK.md) only adds presented frames by replaying GPU commands;
it does not change the guest loop, input sampling or any update math below
(display-locked pacing only nudges the host speed limiter, by at most 0.5%).
The optional widescreen mode changes guest aspect / HUD values only while it is
on (modding/WIDESCREEN_SUPPORT.md).

Review correction (2026-10-26): the host inherited ForceProgressive=true and
previously Auto aspect / 3x manual rendering; original video fields and cadence
have NOT been validated against hardware. See ACCURACY_REVIEW.md. Do not assume
that display refresh, VI interrupts, rendered frames and game updates have
identical rates.

## Uncap mod pointers (summary written for the FPS project)

These were the documented intervention points; frame generation keeps all of
them on the original schedule and interpolates presentation only.

1. Simulation gate: main.dol 0x8002FD2C -> 0x801A87C4 retrace wait (T001).
   The main loop updates gameplay, then sleeps until the VI counter changes.
   Any uncap must decouple updates from this wait without changing update math.
2. Input sampling: SISetSamplingRate(0) at 0x8004AA38 (T002). Latch inputs at
   original guest times; do not poll once per host frame.
3. Guest clock: OSGetTime/OSGetTick 0x801A4158/0x801A4170 and alarms (T003).
   Keep tick arithmetic, wraparound and frequency guest-accurate.
4. Modules: T004 found no named SDK timing references, but T006 confirms
   fixed-step title-module arithmetic. Audit all module update callbacks and
   counters; a negative symbol scan does not establish refresh independence.
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
Working hypothesis only: the observed outer update path is mediated by main.dol
(T001/T004). The negative scan cannot exclude REL counters, indirect time reads
or additional gates. T006/T007 already show fixed-step REL behavior. Investigate
main retrace scheduling AND all module update math before an FPS change.

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

## T007 - Opening cutscene transition counts update calls

Module WWUSOP, ID 5 (pinned hash in config/project.json), executable section 3
offset 0x59BC, active object's vtable +0x48 callback. In the intro snapshot,
object=0x804BB780, vtable=0x804B71EC, callback=0x804B5034. These are observed
allocations, not constants for the recompiled runtime. Evidence:
private/runs/20261026T110707530213Z-749f68a0/control/mem1-low.bin and
private assembly generated/analysis/WWUSOP/asm/auto_00_00000000_text.s,
fn_5_59BC. The loaded 30940 code bytes independently match original relocation
(reports/intro-rel-audit-20261026.json).

Signed 16-bit state is object+0x2C; signed 16-bit countdown is +0x2E.
In states 0, 2 and 3, each callback subtracts one and transitions only when
countdown < 0. State 1 accepts flag +0x31 or input rising edges masked 0x1100
from the controller object at global 0x801FDA90 (current +0xE0, previous +0xF0).
It then enters state 2, sets countdown to 0x5A (90), and passes that countdown
to main-module transition/fade calls (0x8007F928, 0x80059730). State 2's terminal
transition sets state=3 and countdown=3. State 3 eventually requests a main
state change via 0x80030550, choosing 3 or 4 by byte global 0x801FD952.

Confidence: high for per-callback countdown and control flow; screen/fade roles
are inferred, not named symbols. No elapsed-time operand is used. The strict
negative terminal check means a fresh countdown 90 needs 91 decrements, and a
fresh 3 needs four, unless another routine changes it. Do not label these as
seconds or rendered frames without measuring actual callback cadence. Like T006,
this module callback belongs to the main pre-retrace update path. Calling it
once per uncapped presentation would shorten skip/transition timing.

Future handling: retain original simulation updates and input edges, including
signed width and the terminal off-by-one rule. Required replay: resume the intro
checkpoint, apply the skip input, record state/countdown at guest ticks, and
compare update counts and transition boundaries at different host refresh rates.

## T008 - Main-loop tick handshake with a message-loop worker (2026-10-26)

Locations: main.dol fn_800589A8 (called from main), fn_80058A78 (no direct
callers; message loop, probably a thread entry), queue/object 0x801CF550,
globals 0x801FDAE4 (main tick counter), 0x801FDAE8 (worker tick counter),
0x801FDB01 (worker-busy flag), 0x801FDAEC (array of handler objects).
Evidence: dtk assembly; runtime MEM1 snapshots 6 s apart in Greenhorn Forest
(private/runs/20261026T165304735180Z-f5082ae1) show 0x801FDAE4 and 0x801FDAE8
advancing in lockstep with the VI counter 0x801FE00C (+328/+335/+325 each,
i.e. one per 59.94 Hz frame).
Behaviour: each main-loop frame, fn_800589A8 checks 0x801FDB01; if the worker
is idle it copies the worker count to 0x801FDAE4, sets the busy flag and posts
message type 0 (via fn_80058258) to the queue; it then always increments
0x801FDAE4. The worker (fn_80058A78) receives messages (fn_80058358/fn_80058468)
and switches over 9 types (jump table 0x801BBF00); type 0 clears the busy flag
and increments 0x801FDAE8; other types call vtable slots +0x0C/+0x10/... on
objects in [0x801FDAEC].
Implication for FPS work: the worker's tick rate equals the main-loop rate.
Running the main loop faster would tick this worker faster too. What the
worker does (streaming, audio, loading?) is not yet known - identify the
[0x801FDAEC] handlers before any uncap.
Confidence: confirmed for the counters and message flow; roles of the worker
and handlers unknown.

## T009 - Global frame counter and frame-counted soft reset (2026-10-26)

Location: main.dol fn_80031708 = scene vtable slot +0x58 (base class), called
once per main-loop frame. fn_801A20CC identified as OSGetResetButtonState
(reads PI 0xCC003000 reset-switch bit under OSDisableInterrupts/__OSGetSystemTime).
Behaviour: increments 0x801FD934 every frame (global frame counter). Tracks
reset-button hold in halfword 0x801FD94C. A state machine in 0x801FD94E with
counter 0x801FD950 watches held buttons `[0x801FDA90]+0xE0 & 0x1600`
(Start|X|B, the standard GameCube soft-reset combo): needs >10 consecutive
frames, then a 30-frame countdown, before calling fn_800306C4 (reset path).
Implication: the soft-reset hold times are frame counts (~0.17 s and 0.5 s at
59.94 Hz); an uncapped loop would shorten them unless kept on the simulation
tick. 0x801FD934 is a convenient frame clock for tests.
Confidence: confirmed for counters/thresholds/mask; fn_800306C4 = reset is
probable; pad +0xE0 = held buttons is probable.
