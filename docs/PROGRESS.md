# Progress log

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
gating remains possible. Practical consequence for the later FPS project: the
uncap work concentrates on main.dol's retrace wait and scheduler, not the RELs.

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

