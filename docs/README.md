# Documentation index

One line per document. Start with [progress/CURRENT_STATUS.md](progress/CURRENT_STATUS.md).

## Players

- [release/v1.0.md](release/v1.0.md) - release notes and how to play from the release zip.
- [CONTROLS.md](CONTROLS.md) - default GameCube-layout controls, rebinding, rumble, keyboard.
- [PLAYTEST.md](PLAYTEST.md) - playing from this repository, F12 bug reports, textures, play telemetry.
- [modding/IN_GAME_MENU.md](modding/IN_GAME_MENU.md) - every in-game menu option and how it applies.

## Building and releasing

- [START_HERE.md](START_HERE.md) - quick resume for agents: rules, how to run, hidden test example.
- [HANDOFF.md](HANDOFF.md) - agent handoff: constraints, verified disc baseline, tool traps, Ghidra notes.
- [PUBLISHING.md](PUBLISHING.md) - what may go into Git and releases, GPL notes, release checklist.
- [TOOLING.md](TOOLING.md) - tool choices, pinned sources, local tool fixes, automation protocol.
- [REL_RUNTIME.md](REL_RUNTIME.md) - how the eight RELs are compiled and mapped at run time.
- [PROBES.md](PROBES.md) - hidden test probe format and its timing limits.

## Accuracy

- [ACCURACY_REVIEW.md](ACCURACY_REVIEW.md) - what the evidence does and does not prove; acceptance gates.
- [ACCURACY_ISSUES.md](ACCURACY_ISSUES.md) - accuracy issues A001-A019 with current status.
- [VALIDATION.md](VALIDATION.md) - acceptance criteria and dated validation checkpoints.
- [TIMING.md](TIMING.md) - frame and refresh dependency ledger (T001-T009).
- [NEXT_STEPS.md](NEXT_STEPS.md) - longer research notes for further accuracy work.

## Engine research

- [engine/ENGINE_INDEX.md](engine/ENGINE_INDEX.md) - entry point, ID prefixes and confidence vocabulary.
- [engine/ARCHITECTURE.md](engine/ARCHITECTURE.md) - main loop, scene/module manager, module lifetime.
- [engine/FRAME_TIMING.md](engine/FRAME_TIMING.md) - summary of the timing ledger.
- [engine/CAMERA.md](engine/CAMERA.md) - camera block, projection and per-frame update.
- [engine/WIDESCREEN.md](engine/WIDESCREEN.md) - 4:3 assumptions, screen cameras, EFB-pixel viewports (WS-001..010).
- [engine/UI.md](engine/UI.md) - HUD and 2D layout pointers.
- [engine/RENDERING.md](engine/RENDERING.md) - host renderer, backends, unvalidated shortcuts.
- [engine/CULLING.md](engine/CULLING.md) - far plane, frustum side planes, open culling questions.
- [engine/INPUT.md](engine/INPUT.md) - SI sampling and the pad manager.
- [engine/AUDIO.md](engine/AUDIO.md) - MusyX layout, volume groups, pause music, runtime mixer.
- [engine/PHYSICS.md](engine/PHYSICS.md) - player pointer, progress block, jump, punch, collision.
- [engine/ASSETS.md](engine/ASSETS.md) - RSC archives and texture banks.
- [engine/MEMORY.md](engine/MEMORY.md) - REL loading and module list.
- [engine/ANIMATION.md](engine/ANIMATION.md), [engine/SCRIPTING.md](engine/SCRIPTING.md) - mostly unmapped.
- [research/FUNCTION_DATABASE.json](research/FUNCTION_DATABASE.json), [research/HARDCODED_CONSTANTS.json](research/HARDCODED_CONSTANTS.json), [research/ENGINE_DEPENDENCIES.json](research/ENGINE_DEPENDENCIES.json) - machine-readable findings.
- [research/UNRESOLVED_FUNCTIONS.md](research/UNRESOLVED_FUNCTIONS.md) - functions whose role is unknown.

## Modding

- [modding/MODDING_ROADMAP.md](modding/MODDING_ROADMAP.md) - status of every mod.
- [modding/FPS_UNLOCK.md](modding/FPS_UNLOCK.md) - frame generation design, pacing, measurements; HD texture streaming; performance mode.
- [modding/WIDESCREEN_SUPPORT.md](modding/WIDESCREEN_SUPPORT.md) - Hor+ widescreen implementation and tests.
- [modding/GRAPHICS_ENHANCEMENTS.md](modding/GRAPHICS_ENHANCEMENTS.md) - resolution, HD textures, extractor, HDR.
- [modding/CHEATS.md](modding/CHEATS.md) - cheat exports, mechanisms and verification.
- [modding/DRAW_DISTANCE.md](modding/DRAW_DISTANCE.md) - draw distance plan (not implemented).
- [modding/MOD_DEPENDENCIES.md](modding/MOD_DEPENDENCIES.md) - what each mod must change together.

## Progress

- [progress/CURRENT_STATUS.md](progress/CURRENT_STATUS.md) - authoritative current state, builds, reproduce commands.
- [progress/NEXT_ACTIONS.md](progress/NEXT_ACTIONS.md) - ordered follow-ups.
- [progress/KNOWN_ISSUES.md](progress/KNOWN_ISSUES.md) - open and closed issues (KI-001..KI-010).
- [progress/TEST_RESULTS.md](progress/TEST_RESULTS.md) - hidden test results by date.
- [progress/DEVELOPMENT_LOG.md](progress/DEVELOPMENT_LOG.md) - log from 2026-10-26 afternoon, newest first.
- [PROGRESS.md](PROGRESS.md) - chronological log of 2026-10-24..26 and the 2026-10-25 handoff notes.
