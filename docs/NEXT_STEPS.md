# Focused follow-up work

## Current accuracy review - 2026-10-26

ACCURACY_REVIEW.md supersedes historical accuracy/settings assumptions below.
User confirms Xbox controls and stage-one clear; Greenhorn Forest has reported
frozen water, box/general slowdown and intermittent stretching. Human progression
save/reboot restoration is still unverified. Auto aspect and manual 3x drift
were found; manual/test presentation is now explicitly 4:3/native 1x with backups.
Win32 focus query fixed and runtime/runner rebuilt; six compiled predicate/dispatch
controls pass. Other framebuffer/video/DSP shortcuts remain unvalidated. No
whole-game, hardware or static-only claim is justified. Read the review's
acceptance gates before adding features or uncapping FPS. Historical notes
about pending user controller feedback are superseded by their confirmation.


## Deterministic input and capture

Current pad probes poll after-present status on a host thread. Their frame
thresholds are adequate for navigating but do not latch at a deterministic SI
poll. Restored renderer counters also require a settling delay. Do not call
these probes bit-accurate replay evidence or compare unmatched-frame pixels.

Available local primary implementation: vendor/dolphin Source/Core/Core/Movie.*.
MovieManager::PlayInput(path, optional<string>* state_path) loads DTM input;
from-savestate movies use a .sav sidecar. DoState stores input byte/frame indices,
so investigate saved movie metadata before mixing a non-movie state with a DTM.
PlayController feeds fixed 8-byte GC records at input polls; synthetic analogue
values and button bits must follow Movie.h rather than pad_frames field encodings.
MAIN_MOVIE_PAUSE_MOVIE invokes CPU::Break at EOF. BootSessionData already supports
savestate boot; runtime RuntimeConfig has load_state_path and the CLI already has
--load-state. Avoid adding duplicate public configuration fields unnecessarily.
A private diagnostic movie path hook and CPU-thread snapshot at a specified poll
may support stronger comparisons. Verify stop boundaries/native chunk latency
before claiming register/memory parity; a host/GPU frame pause is insufficient.
No movie support was added to the recomp runtime in this turn; this is researched
implementation direction, not a finished feature.

## Interpreter helper reduction

inventory_helpers.py identifies observed helper sites: mfspr/mtspr for SPRG0,
HID0, L2CR, DEC, WPAR and BATs; plus dcbst/dcbf/dcbi/icbi. New counters distinguish
actual cache fast paths from SingleStepInner. Do not reduce a counter by renaming
an interpreter handler or removing faithful hardware side effects.

Existing HookSPRRead/HookSPRWrite implement many operations, but blanket routing
would need precise privilege/trap behavior, register masks, BAT invalidation,
HID0 cache flushing, decrementer/interrupt ordering, gather-pipe behavior and cycle
charges. SyncOut/SyncIn also refresh timebase caches, so removing their calls can
change later mftb observations even for an apparently simple SPRG register move.
Check the local Interpreter_SystemRegisters.cpp and SingleStepInner paths, then
write differential tests before changing a whitelist. Keep interpreted fallbacks
explicit until behavior is established. No helper semantics were changed here.

## Gameplay/save coverage

Greenhorn Forest entry is preserved in private/runs/
20261026T111939310041Z-8d4aab64/control/checkpoint.savestate, paired with user/.
Later movement state: 20261026T112414167280Z-ff64d01b/control/checkpoint.savestate.
Inputs so far do not establish enemy hits, defeat, collectibles, stage completion,
actual progression saving/Continue, boss modules or all REL unload/reload paths.
All slots remain New in the persisted-card boot test; do not conflate creating
and reading the outer GCI with saving a progressed slot. Do not fabricate a save
or modify game memory to bypass this work. Preserve the human's separate
private/playtest-user folder. Their later playtest is useful but not required
for continuing analysis, instrumentation and silent tests.

T007 newly documents opening-module signed update-call countdowns. Continue
this audit in movement, timers, camera, cutscenes, audio and bosses; negative
named-symbol timing scans do not exclude fixed-step dependencies.
