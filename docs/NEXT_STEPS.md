# Research follow-ups (accuracy)

The current task list is progress/NEXT_ACTIONS.md. This file keeps longer
research notes for accuracy work that is not on that list. Written 2026-10-26;
status updated 2026-10-27.

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

## Interpreter helper reduction - done on tested routes

Supervisor mtspr/mfspr and cache operations now run natively with Dolphin's
side effects inside the same SyncOut/SyncIn (ACCURACY_ISSUES.md A003,
scripts/tool_fix_native_spr.py); hook_interp=0 on the tested routes and the
regression suite fails if it is not. Routes not yet observed use the same code
path. Do not reduce a counter by renaming an interpreter handler or removing
faithful hardware side effects.

## Gameplay/save coverage - superseded

The owner's full playthrough covers enemies, collectibles, stage clears, bosses,
saving and Continue in practice. What it does not give is a deterministic
replay or a parity proof (ACCURACY_REVIEW.md gates). Fixed-step audits of
movement, timers, camera, cutscenes, audio and bosses (TIMING.md) remain
relevant for any change to the simulation clock.
