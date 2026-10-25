# Agent handoff

Canonical project: F:/AI Projects/Recomp/Wario World/Recomp.
Input: ../Game/Wario World (USA).iso. Date started: 2026-10-24.
Read AGENTS.md, PROGRESS.md, TIMING.md, TOOLING.md and VALIDATION.md.

## User intent and constraints

Deliver a full faithful static recompilation of Wario World, with progressive
documentation another agent can resume. Preserve original behavior first.
Record every frame/refresh dependency for later FPS uncapping; do not uncap now.
Ask before installing new software. Local DolRecomp/ModernGekko downloads and
builds/dependencies are already approved. Portable Ghidra 12.1 + GameCube loader
were additionally approved on 2026-10-25. No system tools installed or GitHub
content published. User asked about sharing: public tree excludes game material.

## Verified baseline

GWWE01 rev 0; ISO SHA-256
37b1d6d8c1d8e5629941c6418aba64d05184837544cd2839ab83b19664239007.
Main DOL SHA-256
3550d57e1d76bbac4265158360294a5b9d3a0c1157eee88fd4b7e8591af2d49e.
Entry 0x80005304, main 0x8002FC00, original r13 base 0x802056E0 and r2 base
0x80206100. Extracted DOL length 1,898,016 bytes; 245 FST files totaling
267,617,800 bytes. Independent audit compared extracted contents to ISO offsets.

Eight REL version-2 modules are present; names/IDs in README. No missing import
IDs. Full section/import/hash inventory is reports/inventory.json.
4546 main function locations recovered from exception tables by dtk 1.8.4.
generated/analysis contains private assembly/objects for main and all RELs.

## Current checkpoint

Standalone DolRecomp builds; all 20 upstream C test groups now pass, including
a synthetic regression for empty-section addends. The Windows extraction-test
harness was also fixed to quote _spawnv arguments under paths containing spaces.
Main DOL and all eight RELs translate with zero reported unknown instructions.
See reports/translate-main.log and translate-rels-fixed.log.

ModernGekko runtime and native main DLL now compile with installed MSVC. The
native main build reaches the Wario World title screen using OpenGL at 1x internal
scale, approximately 59.94 FPS/VPS. A 40-second render run exits cleanly after
fixing a window-title worker deadlock. See scripts/apply_tool_fixes.py for all
source-only tool/runtime fixes and patches/ for diffs. Last known good run:
private/runs/20261024T231606871108Z (UTC folder name; local date 2026-10-25).

Early lockstep initially found two reports; both arose from the verifier stopping
at an earlier loop continuation. A correction with eight synthetic regression
cases produces 228 checks and zero reports, 16 fallback skips, one zero skip,
zero cap hits and zero undercharges. See ACCURACY_ISSUES.md. This is a limited
early check, not full-game bit accuracy. Instruction-hook fallback remains used.
Full playthrough, REL compiled execution and pixel/audio parity remain unverified.

The compiled DLL is under build/modules/GWWE01/<dolhash>-e5ef81a9f9902943/.
Runtime and port builder are build/moderngekko/Release/*.exe. Main module CMake
uses /fp:strict. The project includes scripts/build.py and bounded smoke_boot.py.
Private reports/functions.csv indexes 15,844 functions; calls.csv has 90,224
call sites with assembly file/line navigation across main and all RELs.

## Current checkpoint, 2026-10-25 (later)

The port no longer exists only as an instrumented diagnostic. build_rel_bundle.py
--clean builds build/module-full/Release/gGWWE01_recomp.dll: main DOL plus all
eight RELs, no instruction counters, same independent executable-hash
verification. Run 20261025T124003224068Z: exit 0, 59.94 FPS, speed 1.0,
fallback=0, smc_failed=0, 74 verifications, JIT entries only at the five known
physical SDK entry PCs. smoke_boot.py --full selects it; --full --lockstep is
rejected because lockstep needs the instrumented twin's instruction journal.

scripts/rel_timing_candidates.py extends the timing inventory to all RELs:
640,469 words scanned, zero candidates (docs/TIMING.md T004). Module cadence is
mediated by main.dol's retrace wait; the future FPS uncap centers there.

Remaining after this checkpoint: gameplay-driven execution/verification of the
seven non-title RELs, data/BSS relocation parity (A007), the unresolved vector
experiment stall (kept out of default builds), and full-gameplay/audio/pixel
validation against a reference. No game code was patched for any of this.

## Critical next steps

1. Preserve the new broad CPU baseline: run 20261025T105720807268Z makes 5401
   distinct entry-PC checks, zero reports, 24 helper skips, 35 zero skips, no
   cap hits, filters or undercharges. Uses exact instruction counting plus fixed
   reference FPCC and generated-code FMA helpers (256 and 512 regressions).
   This supersedes earlier heuristic-loop reports; retain raw logs. Extend
   checks through each native REL after integration; never whitelist differences.
2. REL integration now exists as the diagnostic bundle and the clean full port
   (build_rel_bundle.py, with/without --clean) using real OSLink load
   addresses/sections/lifetimes. Remaining: verify every module under gameplay
   load/unload, audit data/BSS relocation parity (A007), and decide whether the
   full port should replace the main-only default port build. Synthetic
   translator bases 0x80500000..0x808C0000 are NOT observed loads.
3. Review every SMC warning under generated/**/generated_smc.txt. Do not ignore
   runtime executable writes, generated trampolines, exception vector setup,
   paired-single quirks, or REL relocation patches.
4. Bring up a diagnostic boot with an isolated runtime user folder and no cheats,
   speed/widescreen patches or existing Dolphin config changes. Log all fallback.
   A fallback-enabled boot must remain labeled diagnostic.
5. Establish input replay/state/frame/audio comparison against original/hardware
   or an explicitly identified reference build. Cover all modules and transitions.
6. Update progress/handoff and timing ledger at each milestone. Use original
   module/section offsets for REL evidence and retain exact hashes.

## Important tool fixes and traps

- scripts/apply_tool_fixes.py is idempotent and verifies expected source text.
  It patches tools, never the original game. Run after fetching pinned source.
- Original RELs contain 16 HA/LO relocations (two per module) to empty section 2.
  The original OSLink leaves that section base zero and adds the relocation
  addend. Original recompiler rejected it. The synthetic regression uses a zero
  section with nonzero addend; do not replace game files or drop relocations.
- dtk split warns and skips the same empty section for its analysis output;
  that disassembly is evidence, not a complete matching rebuild.
- ModernGekko's nested DolRecomp pin differs from standalone; preserve ABI
  compatibility. Installed LLVM 23 is not the optional LLVM 19/20 backend.
- Before the output-directory fix, a file named build/moderngekko/Release was
  created by copy_if_different. It was moved to misplaced-dolrecomp.exe after
  verifying its hash. The real Release directory now exists.
- Reports, generated C, assembly, native modules and game assets are private.
  Do not force-add them or upload release binaries containing game code.

## Portable analysis and runtime evidence, 2026-10-25

Ghidra 12.1.3 and GameCubeLoader are installed locally. The supplied connector
builds with its Gradle wrapper and existing Java 21. Main DOL imported as
PowerPC:BE:32:Gekko_Broadway, 7717 functions after seeding dtk entries and
setting analysis-only r2/r13 assumptions. Five bootstrap functions decompile.
CodeWarrior demangler raises a nonfatal null-pointer exception; types/names are
inferred and analysis completeness is not guaranteed. Main project:
private/ghidra/projects/WarioWorld-GWWE01.gpr. Server metadata:
private/ghidra/server.json. Close the project through its connector before
headless writes to the same project; never force-remove lock files.

Use -loader-autoloadMaps false for headless import, avoiding a GUI map prompt.
Connector annotation parameters use JSON POST; old README form examples are
stale. /get_functions accepts comma-separated addresses and a fields list.
Raw private evidence: reports/ghidra-bootstrap, ghidra-connector-bootstrap.json,
ghidra-loader-timing.json. scripts/import_ghidra.py reproduces main import.

Main module transition 0x800302CC calls inferred OSLink 0x801A0B40, then REL
header +0x34 prolog. Teardown 0x800304AC calls header +0x38 epilog, inferred
OSUnlink 0x801A0FD4 and frees BSS. Desired/current states are 0x801FD914/924;
loaded module pointer 0x801FD95C; BSS pointer 0x801FD960. Builtin states 0..2
construct objects directly; state 3 observed with title REL WWUSTT (ID 8).

90-second run 20261025T103819667331Z clean exit, native=243350083,
hook_fb=1586277, SMC failures=0, 70 chunk verifications. Its paused 24-MiB MEM1
snapshot locates linked WWUSTT header 0x804AF580, code section 3 at 0x804AF678,
39244 bytes. scripts/inspect_boot.py creates a private JSON summary. It records
14 observed helper sites (cache/system registers) and confirms original words.

CRITICAL: fallback=0 in old logs excludes JIT runs. New accounting in run
20261025T104315290208Z reports 606085 JIT entries, 436 distinct PCs. Native
main+JIT title is a diagnostic hybrid. RefreshRelSections also rejects linked
headers because +0x10 becomes an absolute table pointer. See A006/A007.
The longer-press original-code JIT comparison and native menu probes reached
different save prompts; input timing/session behavior is not yet deterministic.

New diagnostic options: smoke_boot.py --reference (same runtime JIT, not hardware),
--pad-hold 12, --lockstep-limit 0, and --instrumented. build_instrumented.py
copies generated main C into a separate ignored tree, adds attempted-instruction
counting, and builds build/module-instrumented/Release/gGWWE01_recomp.dll.
No game inputs or normal baseline DLL are modified by instrumentation.

Latest runtime FMA repair is also linked into the normal DLL via module-main.
The upstream port cache omits local GXRuntime source changes; build.py now asks
CMake to refresh module dependencies and republishes the linked DLL on every
module-main invocation. Upstream manifest.txt hardcodes stale revision strings;
use actual revisions in patches/manifest.json and config/project.json instead.

Independent relocation model: relocation_model.py supports exactly the four
patch kinds observed in this revision (ADDR32, ADDR16_LO, ADDR16_HA, REL24),
and rejects others. Seven synthetic edge cases pass. audit_loaded_rel.py verifies
the captured WWUSTT executable section: all 39244 bytes match after modeled
relocation, SHA-256 f5ffd15575934773ac6cfe9014e94104c2d5b2e67b76f613d1763acd8cc9dd7b.
Evidence reports/loaded-rel-audit.json. Mutable data sections are not compared.

All eight RELs import only main (ID 0) and themselves. Across all files there
are 55699 HA, 55699 LO, 29605 REL24 and 9508 ADDR32 patches. Code sections
contain only HA/LO/REL24. Every HA patches addis (opcode 15); LO patches addi
or D-form memory instructions. Every REL24 targets main. Preserve relocated
immediate values, actual LR/CTR/exception PCs and all data/BSS pointers when
making C relocatable; translating only effective memory addresses is inadequate.
Small BSS exists in WWUSPF (4 bytes), WWUSS4 (32), WWUSS5 (8); others zero.
OS module-list head/tail at 0x800030C8/CC both point to observed WWUSTT header;
header +4/+8 are zero in the snapshot. Use real linked-list lifetime evidence,
not scanning stale unlinked headers, for future load/unload notifications.
