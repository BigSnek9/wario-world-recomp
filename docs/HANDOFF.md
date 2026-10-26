# Agent handoff

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


Canonical project: F:/AI Projects/Recomp/Wario World/Recomp.
Input: ../Game/Wario World (USA).iso. Date started: 2026-10-24.
Read AGENTS.md, PROGRESS.md, TIMING.md, TOOLING.md and VALIDATION.md.

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
seven non-title RELs - currently blocked by A009 (memory-card writes fail in
the runtime, so the menu path cannot reach gameplay; EXI trace shows a correctly
formatted empty card and zero write attempts; the failure also reproduces under
the runtime JIT, ruling out the recomp CPU), data/BSS relocation parity (A007
now verified for the observed title snapshot), the unresolved vector experiment
stall (kept out of default builds), and full-gameplay/audio/pixel validation
against a reference. No game code was patched for any of this.

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
