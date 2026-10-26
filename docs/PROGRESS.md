# Progress log

## Current accuracy review - 2026-10-26

ACCURACY_REVIEW.md supersedes historical accuracy/settings assumptions below.
User confirms Xbox controls and stage-one clear; Greenhorn Forest has reported
frozen water, box/general slowdown and intermittent stretching. Human progression
save/reboot restoration is still unverified. Auto aspect and manual 3x drift
were found; manual/test presentation is now explicitly 4:3/native 1x with backups.
Win32 focus query fixed and runtime/runner rebuilt; six compiled predicate/dispatch
controls pass. Other framebuffer/video/DSP shortcuts remain unvalidated. No
whole-game, hardware or static-only claim is justified. Read the review's
acceptance gates before adding features or uncapping FPS.
Post-review hidden/muted 35s stage reload: 12198 CPU checks/zero reports,
zero JIT/hash failures, load settling acknowledged. 36 Python, 85 input,
6 focus, 9 context and 6 PCM controls pass. Idle view only; no box/water claim. Historical notes
about pending user controller feedback are superseded by their confirmation.


## 2026-10-24 - Initial baseline

The user requested a faithful static recompilation, a progressive agent handoff,
and a record of frame/refresh dependencies for a later uncapping project.
Local downloads/builds of DolRecomp, ModernGekko and their dependencies are approved.
No GitHub publication or new system installation is approved.

Completed:

- Read the provided tool documentation: Ghidra MCP, IDA MCP, REA, ILSpy.
- Found installed Python 3.12.6, Git, CMake 4.3.3, Ninja, MSVC 19.39,
  LLVM 23.1.3, Java 21, Dolphin and dtk 1.8.4. No system software installed.
- Identified GWWE01 rev 0; extracted with the existing dtk.
- Independently compared every one of 245 filesystem entries and the main DOL
  against the original disc's own FST/offsets. All compared bytes match.
- Saved full SHA-256 and size manifests in ignored reports/inventory.json.
- Parsed all eight version-2 REL modules (IDs 1..8), sections/imports, and confirmed
  every imported module ID is present (including module 0, the main DOL).
- dtk recovered 4,546 main functions from exception metadata and produced local
  DOL/REL assembly and object metadata under generated/analysis.
- Built the standalone C recompiler; main DOL translation completed with
  399,808 words scanned, 398,164 known instructions, 1,644 embedded-data words,
  zero unknown instructions, and 99 generated chunks. These are tool claims,
  not proof that every data/code decision is correct or execution matches.
- Saved the recompiler's self-modifying-code warnings for review.
- Generated 297 static timing candidates; reviewed main-loop retrace wait and
  input sampling setup (docs/TIMING.md).

Tool findings:

- 19/20 upstream C tests initially pass. disc_extract fails when the Windows
  test invokes _spawnv with unquoted paths containing spaces. The identical
  test and executable pass when copied to a path without spaces and called
  with relative arguments. This is a test harness path issue, not a game fix.
- REL translation initially stops on two relocations per module targeting an
  empty section 2. The original OSLink semantics use zero section address plus
  addend. A narrow tool fix and synthetic regression are being validated.
- Runtime configuration succeeds with the installed MSVC. Initial build exposed
  a missing output-directory creation (a copy creates a file named Release),
  and libspng's assignment warning treated as an error. Local build fixes retain
  game bytes. See scripts/apply_tool_fixes.py and docs/TOOLING.md.

This is an in-progress project. No complete, validated playable native build exists
at this checkpoint. See HANDOFF.md for the latest continuation state.

## 2026-10-25 - Native title-screen milestone

- All 20 standalone recompiler test groups pass, including the empty-section
  regression; fixed the Windows extraction test's argument quoting.
- Main DOL and all eight RELs translate with zero unknown-instruction reports.
  REL translations apply 150,511 relocations across 610,180 instruction words.
- Runtime and main DLL compile using existing MSVC, C11 and /fp:strict.
  Fixed two lambda spellings, #elifdef spelling and two fixed-table size casts
  for this compiler; these retain source semantics.
- 20-second Null-renderer boot exits cleanly; native=63,189,880,
  block fallback=0, instruction-hook fallback=1,033,441, SMC failures=0.
- Early lockstep initially reported two differences. Both were inlined loops
  whose native return PC was a continuation inside the loop; the shadow stopped
  on its first visit. Extended the existing loop-boundary detector to cover
  local loop interiors and exclude linked calls as loop edges. Eight synthetic
  cases compile and pass using the actual patched production detector.
- Repeated early lockstep: 228 checks, 0 reports, 16 fallback skips, 1 zero skip,
  0 step-cap hits, 0 undercharges; no whitelist or filter was used.
- OpenGL at 1x internal scale renders Nintendo boot screen and Wario title
  screen, approximately 59.94 FPS/VPS near full guest speed. No image/reference
  diff or audio sample comparison performed.
- Found a Windows shutdown deadlock from synchronous window-title updates on a
  worker while the main thread joined it. Queueing those updates on the host
  window thread fixes the observed shutdown; 40-second render run exits cleanly.
- That run: native=101,124,598, block fallback=0, hook fallback=1,120,593,
  SMC failures=0, 68 chunk verifications. It does not cover the full game.
- Indexed 15,844 function entries and 90,224 call sites across main and RELs in
  private CSVs, with direct assembly file/line locations for agent navigation.
- Audit utility passes five synthetic corruption/path/truncation tests.
- User approved portable Ghidra 12.1 plus GameCube loader for deeper analysis.
  Official Ghidra 12.1.3/loader downloads are being checksum-verified locally.

Still required: all-eight-REL native module integration, privileged/helper fallback
classification, wider CPU-state checks, gameplay/input/save coverage, and actual
pixel/audio/reference parity. FPS uncapping remains deferred.

## 2026-10-25 - Measured hybrid execution and broader verification

- Finished portable Ghidra/loader/connector setup; main import has 7717 functions.
  Bootstrap/main-loop and module-loader decompilations saved privately. Recorded
  nonfatal demangler failure and analysis/type limitations.
- 90-second OpenGL menu test exits cleanly around original guest speed. Captured
  24 MiB of paused MEM1 and classified 14 boot/menu helper sites.
- Observed linked title REL WWUSTT at header 0x804AF580, executable section 3
  0x804AF678, size 39244. Documented OSLink/OSUnlink and prolog/epilog paths.
- Found old fallback counters exclude JIT. Added explicit accounting: subsequent
  75-second native-main menu test enters JIT 606085 times at 436 entry PCs.
  This confirms hybrid execution, not a complete static recomp.
- Audited REL runtime metadata: linked section-table pointers do not satisfy its
  file-offset header matcher. Unload/reload and relocated hash validation remain
  prerequisites to native REL integration.
- Extended lockstep past the early 10000-dispatch window: 5405 checks, 100
  reports, 24 helper skips, 33 zero skips, no cap hits or recorded undercharges.
  These reports are unresolved except for a reproduced reference compare bug.
- Reference float-compare mask test: 224/256 failures before fix, 0/256 afterward.
  It now clears FPCC bits within the unshifted FPRF field. No game patch involved.
- Building a separate exact-instruction-count diagnostic DLL to distinguish
  real CPU differences from mismatched loop iterations in the verifier.

### Exact CPU boundary and FMA repair

Built the separate instrumented DLL with 403263 generated instruction sites
(includes counted-loop copies). Its first full-menu run checks 5403 PCs and
reduces reports from 100 to 29; remaining printed reports differ in FPSCR FI.
Reproduced a real legacy generated-code FMA helper discrepancy: 59 failures in
512 comparisons against the runtime opcode helper. Fixed pre-rounding FI/FR
handling and NI rounding by using existing NI arithmetic helpers.

Repeat run 20261025T105720807268Z exits cleanly: 5401 checks, 0 reports,
24 helper skips, 35 zero skips, 0 cap hits, filters or undercharges. Seventy
chunks verify with no SMC failures. JIT still receives 852734 entries at 438 PCs.
This is a stronger main-executable checkpoint, not full-game bit-accuracy proof.

Independent loaded-code audit: seven synthetic relocation cases pass. Modeled
OSLink patches produce a byte-exact match for the captured 39244-byte WWUSTT
code section at 0x804AF678. Across eight RELs all code patches are HA/LO/REL24;
all REL24 imports target main and all modules import only main and themselves.
This narrows the relocatable-C implementation requirements without assuming that
synthetic translator bases are actual load addresses. Native REL execution is
still unimplemented. Normal main DLL was relinked with the verified FMA repair.

### Native title REL milestone

Added actual-address code/data/BSS resolution using OSLink's live module queue,
position-independent HA/LO operands, preserved real LR/PC/exception addresses,
and independent expected relocated-code hashes. Thirteen compiled support checks
and five synthetic C-transform checks pass. All 111398 relocation operands across
eight RELs are accounted for. Built 99 main plus 152 REL chunks in one diagnostic
DLL, instrumenting 1014689 instruction sites including counted-loop copies.

90-second run 20261025T111939416970Z: clean exit, rendered save prompt,
6010 distinct-PC checks, 0 reports, 24 helper skips, 45 zero skips, 0 filters,
cap hits or undercharges. 133 chunk verifications, no SMC failures. Title-module
JIT entries are eliminated; remaining JIT entries come from SDK physical paths.
No gameplay/other-module coverage claim yet. Updated timing ledger with an
identified fixed-step title-module damped update and its main-loop call path.

### Physical SDK paths under investigation

Derived and compiled 14 common exception vectors, the syscall vector and the
physical Config24MB routine directly from pinned original DOL bytes and the
observed SDK exception-ID patch. Twenty standard-library synthetic tests pass
across audit, relocation, C transformation and vector derivation.
Separate 20-second vector run exits cleanly with 0 JIT entries; its screenshot
is black. Shadow verification stalls before rendering on the new vector path.
Keep this experiment separate from the checked main-plus-REL default build.

## 2026-10-25 (later) - Clean full port DLL and REL timing scan

### Clean shipping bundle

Added `--clean` to scripts/build_rel_bundle.py. It builds the same
main-plus-eight-REL bundle without per-instruction counters and without the
instruction-journal exports, into build/module-full/Release/gGWWE01_recomp.dll.
smoke_boot.py gained --full to select it and rejects --full --lockstep because
the lockstep verifier needs the instruction journal of the instrumented twin.
All 111,398 relocation operands across the eight modules were emitted again for
this build; the executable-byte hash-verification path is unchanged.

Verification run 20261025T124003224068Z (30 s, OpenGL, windowed, capture):
exit 0, no forced stop, fps/vps settle at 59.94 with speed 1.0, fallback=0,
smc_failed=0, 74 chunk verifications, JIT fallback_entries=30088 at 5 distinct
entry PCs (the known physical vectors/Config24MB set). This is the first
main-plus-REL build that is not carrying diagnostic counting code. It still is
not a bit-accuracy or full-gameplay validation; other modules remain unexercised
until gameplay loads them.

### REL timing inventory completed (negative result)

New scripts/rel_timing_candidates.py extends the static timing inventory to the
eight RELs using relocation records (exact sites) plus word scans, reporting
module ID + section index + section offset only. Result across all 610,180
executable words and 30,289 initialized data words: zero candidates of any
scanned kind. Recorded in docs/TIMING.md under T004 with coverage limits:
unnamed main-module wrappers are invisible to the symbol check, so indirect
gating remains possible. This scan does not exclude frame-dependent REL logic;
T006 already identifies fixed-step arithmetic in the title REL. Both main and
REL update paths require a later FPS audit.

### Vector experiment status

Runs 20261025T114357191381Z through 20261025T115110463512Z all stalled with
frame_count=0 and required bounded termination; the shadow-check stall on the
physical FP-unavailable vector entry remains unresolved. The default and clean
full builds do not include the vector experiment.

## 2026-10-25 (evening) - Data-section audit, gameplay-path investigation

### Data relocation parity (A007 update)

audit_loaded_rel.py now compares initialized data sections of a linked module
against the independent relocation model. For the captured WWUSTT snapshot all
145 data relocation sites match the modeled link values; the only non-site
difference is the vtable boundary marker word (0xFFFFFFFE -> 0xFFFFFFFF, legal
guest mutation). BSS remains out of scope by construction.

### Gameplay path blocked by memory-card failure (A009)

Automated pad probes drive the menus correctly: title -> file-select hall
renders, dialogs advance. Data creation fails on both the default GCI folder
card and the raw card (new smoke_boot.py --memcard raw writes
user/Config/Dolphin.ini SlotA=1). EXI instrumentation ([wario-mc] fprintf in
EXI_DeviceMemoryCard.cpp, in RecompCore.patch) shows correct mount sequences,
correctly formatted empty-card content (header checksum, empty dir, valid BAT),
and zero write commands - the game's SDK declines to write. The identical
failure occurs under --reference (runtime JIT), so this is a runtime EXI/
memcard emulation issue, not a static recomp CPU issue. Runtime classification
helper scripts/classify_captures.py identifies menu states from captures.
Full details in ACCURACY_ISSUES.md A009 with next-step candidates.

### Tools

smoke_boot.py: --capture-cadence N (numbered screenshots), --full, --memcard,
--full --lockstep guard. classify_captures.py added. rel_timing_candidates.py
added (see TIMING.md T004). audit_loaded_rel.py data-section checks. Runtime
source has a [wario-exi]/[wario-mc] diagnostic fprintf set (in patches).


## Latest checkpoint: 2026-10-26, workspace overlay

The current authored updates are in the chat workspace work/project, because
F:/AI Projects/Recomp/Wario World/Recomp remains read-only under this session's
actual permissions. Do not overwrite the newer F tree with an old staging copy.
User consent to project-folder access was received, but the permission tool did
not grant it. No system installation is required for the current work.

Run private/runs/20261025T205523324085Z used the vector-inclusive main + eight
REL diagnostic DLL from F and the workspace-built runtime-overlay runner.
It exited cleanly after 120 seconds: 6,043 CPU lockstep checks, zero reports,
45 helper skips, 47 zero-instruction skips, zero cap/filter/undercharge events;
JIT entries=0, distinct JIT PCs=0; 80 executable chunk verifications,
smc_failed=0. The title/file hall rendered near 59.94 FPS/VPS. This supersedes
the earlier unresolved vector-check stall, not the limits on gameplay coverage.

The stall was a verifier restoration bug: after a native rfi/mtmsr, the checker
restored its entry cached MSR instead of post-native canonical guest state.
That left instruction translation disabled at virtual PC 0x8019B270, invoking
a hidden fatal-address dialog. Restoring canonical CPU state and refreshing
MSR-derived caches fixes this run. scripts/build_runtime_overlay.py builds
against the existing F objects without modifying them; apply_tool_fixes.py now
contains the same reproducible fix for the next full source build. The actual
F source/binary has not yet received this fix. Overlay Sys resources must be
copied from third_party/ModernGekko/vendor/dolphin/Data/Sys before running.

Zero JIT entries is limited to this title/menu trace. 2,133,698 instruction
helper callbacks remain (including cache/privileged interpreter-backed paths).
Other level RELs have not been exercised. There is no full-game, pixel, audio,
or hardware bit-accuracy claim. A clean non-instrumented vector-inclusive
build still needs validation after integrating the verifier repair.

Next: isolate the memory-card/menu failure using installed standalone Dolphin
2606a with private user data. Existing runtime JIT reference also fails, which
rules out a failure unique to native generated CPU code but does not establish
the cause. Record an independent observed comparison before changing EXI.
T006 in TIMING.md proves a REL per-call fixed-step dependency despite T004's
negative named-symbol scan; audit other RELs for similar arithmetic/counters.


## Current status: 2026-10-26, integrated silent testing and save creation

Main project access is now granted and the workspace fixes have been integrated
at F:/AI Projects/Recomp/Wario World/Recomp. Earlier read-only/overlay notes
below describe history. Read this section first. User requires all further tests
to remain invisible and inaudible; smoke_boot.py rejects --windowed and always
passes --mute. Do not launch standalone Dolphin GUI for testing.

The canonical-MSR verifier fix is now in the main source and rebuilt runtime:
build/moderngekko/Release/moderngekko-run.exe. Headless graphical tests on Windows
now create an HWND without showing or activating it, preserving WGL rendering;
audio uses No Audio Output. Headless alerts log and fail on panic rather than
opening a dialog. An inventory check during rendering found no visible game
window. Source changes are reproducible in apply_tool_fixes.py and patches/.

Build note: parallel MSBuild node execution stalled twice in this session.
Single-node /m:1 /nr:false succeeded for core.vcxproj, moderngekko.vcxproj and
moderngekko-run.vcxproj, with /p:BuildProjectReferences=false after existing
prerequisites. The separately linked build/silent-runtime runner also works.
No software install was needed.

Run private/runs/20261026T104743933654Z used the rebuilt main runtime and existing
vector-inclusive main + eight-REL DLL. 120 seconds, clean exit; 6,189 CPU checks,
zero reports, 45 helper skips, 51 zero-instruction skips, zero cap/filter/
undercharge events, zero JIT entries/PCs, 80 code-hash verifications and no
SMC failures. Original speed, around 59.94 FPS/VPS. Helper calls remain
(2,155,598), and level gameplay/other REL execution remain unverified.

A009's suspected memory-card defect was an INPUT-PROBE mistake. The menu
selection responds to analog main_y=1, whereas dpad_up did not select the
intended option. config/probes/repeated_analog_yes.json causes real guest erase/
program operations and creates 01-GWWE-WARIO WORLD.gci (81,984 bytes, 10 blocks)
in the fresh private user folder. Header/length audit: reports/save-creation-
20261026.json. No game bytes, save data or EXI timing were patched. Standalone
Dolphin's earlier synthetic D-pad test was confounded by the same input mistake.
The current reached screen is 'Please choose a file' with New slots. Advancing
into an adventure is the next immediate task; use the corrected analog controls.

Current paired probes use config/probes/start_adventure.json, comparing native
and runtime --reference JIT with identical inputs. These are behavioral probes,
not synchronized hardware parity evidence. smoke_boot.py adds a random suffix
to run folders to prevent simultaneous test collisions observed this session.

Twenty local synthetic/extraction/relocation/vector tests pass. The source-tree
publication check passed (59 files at that point); no upload/push was made.
Regenerate patches and this checkpoint after the paired tests finish. Clean
vector-inclusive non-instrumented build is still pending; do not claim full
static completion, full gameplay, pixel/audio/hardware bit accuracy or FPS uncapping.


## 2026-10-26 - Hub reached and independently audited

Native run private/runs/20261026T105101421481Z-379aa3dc and runtime JIT run
private/runs/20261026T105034146274Z both used config/probes/start_adventure.json,
hidden OpenGL, mute, fresh user data and 120-second bounds. Native reached
the in-game hub and pause book, exited cleanly, and reported 9066 deduplicated
CPU checks with zero reports; 45 helper skips, 69 zero skips, no cap/filter/
undercharge events; JIT=0 entries/PCs; 97 executable hash verifications,
smc_failed=0. 2,958,577 instruction helper callbacks remain. Native near
59.94 FPS/VPS at original speed. This extends coverage beyond title/save menus,
not a full level/playthrough or hardware/pixel/audio parity proof.

Snapshot independently audits loaded WWUSPF (ID 7), executable section 3 at
observed 0x809E75C0: 190272 bytes exactly match modeled OSLink relocation,
SHA256 7e54ddaff63860bcc50e783d1a03e621f31b6e0c8e888618217a1efe70845a57.
All 757 initialized-data relocation sites match; one non-site marker byte
changed legally. See reports/hub-boot-20261026.json and hub-rel-audit-20261026.json.
Header scans can also see stale unlinked modules; they do not alone prove execution.

A movement probe is now exploring the hub with analog holds. Probe format now
supports optional per-step hold durations and signed stick values; docs/PROBES.md.
One run (20261026T105515260324Z-e569cc9e) aborted due to a harness NameError;
it is explicitly invalid accuracy evidence. The unpacking was corrected and
child cleanup now runs in finally. Successful subsequent results must be recorded.
A simultaneous native/reference launch also revealed a timestamp directory
collision; random suffixes prevent mixing their independent user folders.

The clean vector-inclusive candidate is building via build_rel_bundle.py
--vectors --clean into build/module-full-vectors; no instruction counters or
journal. Its smoke validation and export audit are pending. The existing checked
vector bundle remains separate and unchanged. No software installation, game
patch, FPS change or publication was performed.

## Latest verified checkpoint: 2026-10-26, clean hub build

All testing is hidden and muted at the user's request. The main runtime now
supports an invisible Windows rendering surface; do not launch a GUI test.
F project write access was granted for this turn; source and patches are integrated.

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


## Latest verified checkpoint: 2026-10-26, Greenhorn Forest

User said to keep working without waiting for their later playtest. No user input
is currently required. All tests remain hidden and muted, no new installation.
Main project is F:/AI Projects/Recomp/Wario World/Recomp; access granted this turn.

The first playable stage, Excitement Central / Greenhorn Forest, now loads.
Transition run private/runs/20261026T111939310041Z-8d4aab64:
180-second bounded run, clean exit; 12785 CPU checks, zero reports, zero JIT;
98 helper skips / 95 zero-instruction skips, zero cap/filter/undercharge events;
163 executable code-hash checks, smc_failed=0. Main DOL text independently
matches all original 1599232 bytes in its two nonempty executable sections:
reports/greenhorn-main-audit-20261026.json. The active stage object vtable
is 0x801C68B0, update callback 0x8015BF2C in MAIN, not WWUSS1. Observed object
0x804AF4E0. Module queue head/tail are zero in this stage snapshot. Do not count
WWUSS1 or any other boss/level REL as exercised just because this stage loaded.
Only title WWUSTT(8), opening WWUSOP(5), hub WWUSPF(7) have module evidence so far.

Native stage checkpoint reload/movement/jump/attack-input run:
20261026T112414167280Z-ff64d01b, 120 seconds, clean exit, 12562 CPU checks,
zero reports/JIT, 163 code-hash checks, no failures. Clean uninstrumented twin:
20261026T112414180436Z-582447cf, same 120-second reload/input exploration,
clean exit, original speed near 59.94, zero JIT, no code-hash failures. Inputs
were legitimate pad commands, not memory/game patches; no enemy hit/kill,
full combat, full stage completion, pixel or audio parity is established.
Summary counters: reports/stage-validation-20261026.json.

Checker repair: old PC-only dedupe skipped a different REL reusing the same
address, and persisted across state reload. It now stores code-map generation
per PC; mapping changes and cache/state restoration force fresh checks.
verify_lockstep_context.py compiles actual production predicates: one of nine
cases fails before, zero after. Distinct PCs and check counts now differ when
code/context is rechecked. Do not compare historical counts as equal coverage.
Actual helper tiers are now separated: hook_fb=hook_cache+hook_interp.
For the transition: 4257983 helper calls = 3781585 cache fast-path calls +
476398 actual interpreter single steps. Zero JIT is not zero interpretation.
The 33 traced helper sites are cache operations and special-register accesses;
reports/helper-inventory-hub-20261026.json, scripts/inventory_helpers.py.

Auditor repair: inspect_boot.py walks and validates the live OSLink module queue
(head/tail 0x800030C8/CC); audit_loaded_rel.py excludes stale unlinked absolute
headers and rejects inconsistent/missing inventory. Greenhorn's REL audit has
active_module_ids=[] and zero audited REL code bytes, not a successful REL1
check. Opening REL5 independently audits 30940 code bytes exactly; all 100 data
relocation sites match, one legal non-site marker change. Its new timing entry
T007 records signed update-call countdowns (including 90 -> 91 decrement rule).

Private checkpoints, paired with each run's genuine user folder:
- Intro narrative: 20261026T110707530213Z-749f68a0/control/checkpoint.savestate.
- Hub initial spawn: 20261026T111042914312Z-af4e8602/control/checkpoint.savestate.
- World 1 entrance area: 20261026T111619475186Z-8f313f72/control/checkpoint.savestate.
- First stage spawn: 20261026T111939310041Z-8d4aab64/control/checkpoint.savestate.
- First stage after input exploration: 20261026T112414167280Z-ff64d01b/control/checkpoint.savestate.

smoke_boot.py --load-state <private state> --seed-user <its run/user> resumes in
a fresh copied user folder. It waits for post-load renderer-counter status before
setting a relative probe origin; this uses a settling delay, not deterministic
input-latch synchronization. Optional --save-state-at <seconds> writes private
control/checkpoint.savestate. --seed-user accepts only this project's private
folders; normal user emulator data is untouched. Inputs can also be queued in
control/commands using runtime pad_frames (multiple controls per command work).
Manual steering in the transition run is preserved under control/processed as
210-steer01..06; those inputs are behavioral evidence, not a synchronized replay.

Next: deterministic input-poll replay/capture for native vs original-code CPU
comparisons; extend gameplay through enemies/collision/collectibles and further
module loads/unloads; audit/nativize interpreted SPR helpers only with precise
privilege/side-effect/tick tests. Do not swap interpreter calls merely to hide a
counter. Current uninstrumented DLL stays build/module-full-vectors/Release/
gGWWE01_recomp.dll (unchanged hash d848261f...); rebuilt runtime includes the
checker/counter repairs. Full-game bit accuracy remains unproven; FPS unchanged.


## Latest additions: silent audio comparison and manual playtest preparation

No user input is currently required. The user explicitly authorized continuing
before their later playtest. Automated testing is still always hidden/muted.
Play-WarioWorld.cmd is prepared for the user's own later launch; it has NOT been
opened by the agent. It forces static recomp mode, uses the clean full-vectors
DLL, disables lockstep diagnostics/mods, and keeps human saves in
private/playtest-user. Preserve that folder. Output is private/playtest-last.log
(overwritten per manual launch). Default keyboard guide: docs/PLAYTEST.md.
The manual launcher enables a normal visible window/audio only when the user
chooses to launch it. No binary/game content is included in source archives.

Silent audio runs, 30-second bounds, same first-stage checkpoint, no input:
- clean native: 20261026T114054938759Z-ecb830eb (zero JIT / code-hash failures);
- runtime original-code JIT reference: 20261026T114054938759Z-52d07795.
Both exit cleanly with audio backend No Audio Output. --dump-audio enables raw
private DSP/DTK WAV captures while speakers stay disabled. DSP captures contain
nonzero stereo signed 16-bit PCM at reported 32028 Hz. After removing only
leading exactly-zero stereo frames (42192 native, 47000 reference), both have
515064 frames / 16.0816785 seconds and match every sample exactly. SHA256:
89cf3b4547333640c5cab631389a30ce1bdd20fce21d2ef1ca73c6ddeef53689.
No resampling, gain, or trailing-silence removal was used. This proves equality
of that one idle checkpoint's captured DSP signal against the runtime JIT,
not original-hardware parity, onset timing equality, sound-device behavior,
full audio quality or full-game accuracy. DTK captures are silent in this scene.
Reports: silent-audio-20261026.json and aligned-stage-audio-20261026.json.
compare_audio.py provides exact comparison / explicit leading-silence alignment;
verify_audio_comparison.py passes six controls, including single-bit corruption,
trailing-silence differences and mismatched sample rates. Files were never played.

Persisted-card fresh-boot check (NOT savestate loading):
20261026T114814916012Z-bbe001d6, copied genuine user data from the native stage
run, original boot, 80 seconds. Existing GCI is mounted/read, no creation prompt,
Start/Cancel on a New slot, game reaches the hub. 18678 CPU checks, zero reports,
zero JIT, no code-hash failures; clean exit. Important limit: all slots still
say New. This validates reading the persisted outer card file and starting a
game; it does NOT validate saving/restoring actual gameplay progression. A real
save-point/stage-clear/save/reboot/Continue cycle is still required. Do not call
this a completed progression-save test. Human playtest data remains separate.

Additional regression coverage this turn: nine live-module-queue cases and nine
compiled verifier-context cases, plus six exact-audio controls. Original DOL
text remains unmodified in the first-stage snapshot. No installation, FPS
uncapping, game byte patch, synthetic save, upload or publication was performed.


## Latest controller repair: Xbox/XInput, 2026-10-26

User could not interact and requested real controller mappings; they specified
Xbox/XInput. The previous launcher relied on keyboard-only upstream defaults.
Installed explicit Player 1 bindings in private/playtest-user/Config/GCPadNew.ini,
with XInput slots 0..3 OR keyboard bindings, explicit GameCube port SIDevice0=6,
12% stick dead zones/circular calibration and analog/digital trigger separation.
Xbox face buttons map by label, RB->Z, LB->L click, Menu/Start->Start,
left/right sticks->Control/C sticks; LT/RT analog and >90% digital clicks.
No game bytes, runtime semantics, FPS or saves were changed; no installation.

scripts/configure_controls.py preserves other controller/core settings, backs up
changed existing files, and is idempotent. Play-WarioWorld.cmd initializes a
missing profile on first use, while preserving existing mappings on later
launches. The current profile is already installed. User must CLOSE/REOPEN an
already running game to load it; the agent did not stop their game or open a
visible/audible test. Rumble is unchanged/untested.

Native tools/verify_controls.cpp loads the generated INI through real
ControllerEmu/GCPad logic with isolated in-process fake devices; 85 cases pass,
including every mapped button in each Xbox slot, eight stick directions,
partial/full triggers, dead zone, keyboard and simulated reconnect/release.
No virtual hardware driver or OS key injection was used. verify_controls.py
also creates the actual runtime hidden/muted WITHOUT automation overrides,
using copied input/core configs only. Real device inventory includes
DInput/0/Keyboard Mouse, SDL Xbox One, WGInput Xbox One and XInput/0/Gamepad.
Every Player 1 face/Z/Start expression has two live bindings (Xbox + keyboard),
connected=1 and missing_button_bindings=0. Reports/controller-mapping-test.json
and controller-runtime-bindings.log. Five config preservation tests also pass.
The earlier plain Python XInput probe returned no devices; the actual runtime
subsequently discovered the Xbox. Prefer the runtime inventory for diagnosis.

Physical user button presses/in-game response are NOT yet confirmed. An async
verification question asked them to restart and try Menu/Start, A and left stick;
feedback is pending and does not block other technical work. If they report
continued failure, inspect focus/input gate and live SI pad status instead of
relying on injected automation. The manual launcher intentionally has no
--automation-dir; automation's touch overrides would replace physical input.
Docs/CONTROLS.md and PLAYTEST.md have current controls/restart instructions.

