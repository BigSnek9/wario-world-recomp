# Accuracy review - 26 October 2026

Status note (2026-10-27): this review is dated. Since then the game has been
played start to finish, all RELs run as native code, the water and slowdown
reports are closed (progress/KNOWN_ISSUES.md) and optional enhancements exist
as switchable layers. What stays true: none of that is bit-accuracy proof, the
rendering/video/DSP shortcuts in the table remain unvalidated against hardware,
and the acceptance gates below are still the bar for any accuracy claim.

The current build is an experimental, partially validated recompilation. It is
not a completed static-only port and it has not demonstrated whole-game or
original-hardware bit accuracy. The manual Greenhorn Forest stage clear confirms
playability along that played route, not equivalence to the original game.

This review was triggered by automatic aspect detection in a 4:3 game. The
mistake was accepting inherited runtime settings without auditing the manual
launcher against the test configuration. This is a validation-process defect,
not merely a cosmetic preference. Earlier bounded test results remain bounded.

## What was rechecked

- Re-ran the disc/extraction audit: the pinned ISO, main DOL and all 245 FST
  files match the input identities; all eight original REL hashes match.
- Replayed patches from the four pinned upstream revisions: every patched file
  matches current sources. This proves source reproducibility, not complete
  binary provenance or correctness. Fresh host runtime/runner builds completed
  for the focus fix. The clean game DLL was not regenerated or modified.
- Inspected actual manual-launch arguments, frontend config, GFX/Dolphin INIs,
  the bundled GWWE01 GameINI, runtime forced settings, and renderer defaults.
  A private before/after audit records 301 source defaults and user overrides,
  binary identities and configuration snapshots. These are configuration
  provenance, not telemetry proving every effective setting after boot.
- Generated game module compile logs use /fp:strict and translator exact mode.
  These are necessary implementation choices, not proof of all PPC semantics.
- Re-ran 36 Python cases, nine compiled verifier-context controls, six exact-PCM
  comparator controls, and six compiled focus/dispatch controls. Focus controls
  fail four cases before the repair and zero after. They simulate Win32 answers
  without creating a visible window or sending OS input.

## Findings and disposition

| Area | Finding | Current disposition |
| --- | --- | --- |
| Aspect ratio | Manual GFX.ini omitted AspectRatio; pinned runtime defaults to Auto and contains a 4:3/16:9 heuristic. | Explicit ForceStandard (2), widescreen hack off, crop off. Source Widescreen.cpp disables the heuristic with this combination. The reported transient stretch has not been reproduced and proven fixed. |
| Resolution | Frontend creates 1920x1080 (integer EFB scale 3); manual profile used it. Smoke tests wrote 640x528 (scale 1). | Both paths now explicitly initialize 1x. 640x528 is the EFB allocation label, not a claim that every guest framebuffer is that size or that square-pixel output should be 640x528. Presentation remains 4:3. Old files backed up. |
| CPU framebuffer access | Pinned GFX_HACK_EFB_ACCESS_ENABLE defaults false, with no user override. EFBInterface.cpp can return zero instead of a requested pixel read. | Unvalidated behavior shortcut. Determine whether the game uses these reads; validate an explicit faithful configuration separately. Not identified as the water cause. |
| Framebuffer copies | EFB/XFB copies to RAM default skipped; deferred EFB copies and early XFB output default enabled. | Unvalidated for this game. Need copied-framebuffer and guest-memory comparisons; do not infer compatibility from successful boot. |
| Pixel format/depth/textures | EFB format changes default un-emulated, fast depth and fast texture sampling enabled; texture hashing defaults to sampling 128 entries. | Unvalidated rendering assumptions. Need effects-focused comparisons and texture invalidation traces. No water fix is claimed. |
| Video fields | ForceProgressive defaults true; original field parity/cadence has not been measured. | Cannot claim original refresh/video-mode accuracy. Earlier 'no refresh patch' language described game bytes, not host video processing. |
| Audio | DSPHLE defaults true. Native/JIT audio comparison uses that same audio implementation. | One aligned idle signal matches; DSP hardware timing and full audio equivalence remain unverified. |
| Input focus | Win32 inherited a constant true focus flag; BackgroundInput=false could not enforce the intended gate. | Base query made virtual; Win32 queries foreground ownership, visibility mode and minimized state. Host rebuilt. Manual Alt-Tab/keyboard integration remains untested. |
| General/box slowdown | Playtest reports slowdown in Greenhorn Forest. No matched box-breaking benchmark or original-game timing exists. | Open defect. No evidence yet distinguishes host stall, runtime timing error or intentional original hit stop. Lower scale is a baseline correction, not a demonstrated cure. |
| Water | Playtest reports frozen water in Greenhorn Forest. | Open rendering/game-state defect. Need the same water scene over successive guest updates and a reference outside the shared renderer. |
| Controls | Earlier automated tests proved parsing/binding only. | Playtest now confirms Xbox input and stage-one completion. Rumble, exact analog response and original controller timing are not established. |

The bundled GameINI includes a *definition* of a widescreen Gecko code. It has
no enabled-code section, the manual launcher disables external mods, and the
observed original game code audits match. Presence of the definition is not
evidence that it ran. Still, effective cheats/mod configuration should be
recorded after boot rather than inferred solely from files.

## What existing comparisons actually establish

The original DOL/assets matching the disc establishes extraction integrity.
Loaded text/relocation comparisons validate the particular captured executable
regions. They do not validate all future dynamic linking or data mutations.

The first-stage transition's 12,785 checked contexts with zero reports is useful
CPU evidence. It is not an exhaustive instruction proof: helper blocks and
zero-instruction contexts are skipped, many paths remain unvisited, checks are
deduplicated within mapping generations, and guest event scheduling still comes
from the shared runtime. Do not sum per-run counts as unique game coverage.

The native and original-code JIT paths share the same Dolphin-derived renderer,
DSP/HLE, device emulation and settings. A shared defect can pass both paths.
Neither an identical screenshot nor identical PCM in that setup independently
validates the common runtime. The 16.0817-second idle audio equality also
required leading-zero alignment, so it does not establish onset-time equality.

All eight RELs compile; title/opening/hub exercise IDs 8/5/7. Greenhorn Forest's
observed active update is in main and its live REL queue is empty. Stage one
therefore does not prove REL1 executed. Remaining module lifetimes and the rest
of the game need actual execution and independent audits.

Instruction-level interpreter helpers remain even in zero-JIT routes. This must
remain visible in status and documentation; renaming a fallback is no fix.
Progression-save/reboot/Continue, deterministic SI-poll replay, original video
cadence, matched frame pixels and hardware comparisons are not established.

## Corrections made and next acceptance gates

configure_baseline.py explicitly applies 4:3/native 1x to manual and smoke paths,
backs up changed existing configs and preserves unrelated settings and saves.
ForceStandard uses the guest VI standard-aspect calculation; it disables inferred
widescreen. It does not crop or force every raw screenshot to an exact 4:3 pixel
rectangle. Original video active-area/pixel-aspect behavior still needs validation.
It deliberately does not claim to solve the other runtime assumptions above.
Launcher startup reapplies those presentation settings; existing saves and input
bindings remain intact. Focus repair is a reproducible upstream-source patch.

Before treating a build as an accuracy baseline:

1. Capture effective settings after boot, including GameINI overrides, shaders,
   CPU/event timing, DSP mode, cheats and every rendering shortcut. Store them
   with binary/source hashes. Fail validation when required settings drift.
2. Validate a conservative rendering/video profile in an isolated user folder;
   compare CPU pixel reads, EFB/XFB RAM copies, texture writes/invalidation,
   pixel formats, field output and water across guest updates. Record performance
   separately. Do not blindly toggle settings or label defaults faithful.
3. Establish input playback latched at SI polls, with matched initial state and
   guest-event checkpoints. Current host after-present probes are navigation.
4. Compare the same workload against a separately identified reference, including
   a renderer outside this fork and original hardware where available. Distinguish
   CPU/compiler failures from defects shared by both existing execution paths.
5. Cover combat, box effects, all stages/modules, bosses, transitions, death/retry,
   cutscenes and genuine progression save/Continue. Keep FPS uncapping separate.

Private evidence: reports/accuracy-review-before-20261026.json,
accuracy-review-after-20261026.json, inventory.json, patch-replay.json,
window-focus-regression.json, review-runtime-build.log and review-runner-build.log.
Playtest saves remain under private/playtest-user and are not test fixtures.

Additional harness finding: screenshot commands could overwrite last_command
before the half-second post-load settling check observed it, leaving the summary's
state_load_complete false despite a visually loaded stage. The harness now gates
captures, memory requests and state saves on load settling so they cannot race
that status observation. The first review smoke run (20261026T125756920333Z-0808a625)
exited cleanly with zero JIT/hash failures and a visible-in-file Greenhorn scene,
but its false settling flag means it is not evidence of deterministic load/replay.


Post-repair bounded check: 20261026T130139955936Z-319be01a, 35 seconds,
hidden/muted OpenGL, native 1x, ForceStandard. State settling acknowledged,
12,198 checked CPU contexts / zero reports; 94 helper skips / 52 zero skips,
zero JIT entries, 161 executable verifications / zero failures, clean exit.
The last sampled speed was 0.997992 with 59.9409 FPS / 59.94 VPS in an idle
stage view. This does not benchmark box breaking or validate water animation.
The rebuilt host also passes the existing 85 production input-conversion cases
and live binding inspection with no missing button bindings. No visible or
audible testing, software installation or publication was performed.
