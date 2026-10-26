# Resume quickly

Work in F:/AI Projects/Recomp/Wario World/Recomp. No user response is currently
needed. Build a faithful GWWE01 rev0 static recomp first; FPS uncapping is later.
All agent tests must be hidden and muted. Ask before new installations. Existing
local DolRecomp/ModernGekko dependencies and portable Ghidra/loader are approved.
No subagents authorized. Preserve private/playtest-user (the human's saves).

## Accuracy review and user feedback take priority

Read ACCURACY_REVIEW.md first. The user confirms Xbox controls work and stage
one is completed, but reports slowdown (including box breaking), frozen water
and transient stretching in Greenhorn Forest. Full accuracy is unverified.
4:3/native 1x are now explicit in launcher/tests; old manual settings were
3x/Auto, unlike 1x tests. Other rendering/audio shortcuts remain unvalidated.
Win32 focus query repaired/rebuilt with six compiled predicate/dispatch controls;
human Alt-Tab verification remains open. Preserve all human saves.

## Working candidate

Runner: build/moderngekko/Release/moderngekko-run.exe.
Clean module: build/module-full-vectors/Release/gGWWE01_recomp.dll.
Checked twin: build/module-rel-bundle-vectors/Release/gGWWE01_recomp.dll.
Clean DLL SHA256: d848261fe4c8277e0164cdd746f9daa479fbaccadc9a1c702042471f9798ed9f.
The user can later double-click Play-WarioWorld.cmd; the agent has not run this
visible/audio-enabled launcher. Keyboard notes: PLAYTEST.md. Logs/saves are private.

## Evidence and limits

- Main DOL and all eight RELs compile, zero unknown translated instructions.
- Title, genuine card-file creation, opening narrative, hub, first-stage entry
  and basic movement/jump/attack inputs run. Agent automation did not prove enemy hits or a stage clear; human confirms stage one cleared.
- Title REL8, opening REL5, hub REL7 are exercised. Greenhorn Forest runs MAIN
  (update 0x8015BF2C); its module queue is empty. Do not count REL1 as exercised.
- First-stage transition: 12785 CPU checks / zero mismatches / zero JIT;
  loaded main text matches all 1599232 original bytes. New context-aware dedupe
  rechecks PCs after code-map/state changes. Counts are not cumulative coverage.
- Fresh-boot existing-card read: 18678 checks / zero reports / zero JIT. Slots
  still say New, so actual gameplay save/Continue restoration is NOT validated.
- One idle stage DSP capture: 515064 stereo frames (16.0817 s at 32028 Hz) match
  runtime JIT after explicit initial-zero alignment. No onset/hardware/full-game
  audio or physical sound-device claim. WAVs were never played.
- Real interpretation remains: hook_interp counts single steps; hook_cache counts
  direct cache helpers; hook_fb must equal their sum. Zero JIT is not zero
  interpretation. See helper-inventory-hub-20261026.json under private reports.

## Reproduce a hidden stage test

Use the existing private checkpoint and COPY its user data into a fresh run:

```powershell
python scripts/smoke_boot.py --vectors --lockstep --lockstep-limit 0 --graphics OpenGL --seconds 60 --load-state private/runs/20261026T111939310041Z-8d4aab64/control/checkpoint.savestate --seed-user private/runs/20261026T111939310041Z-8d4aab64/user --capture-cadence 10
```

For clean execution replace --lockstep --lockstep-limit 0 with --full.
For runtime original-code comparison replace those flags with --reference.
--dump-audio writes private WAVs with No Audio Output; --save-state-at 45 writes
a private checkpoint. PROBES.md explains relative inputs and their timing limits.

Tests: python -m unittest discover -s scripts (36 cases), then
scripts/verify_lockstep_context.py (9 compiled controls) and
scripts/verify_audio_comparison.py (6 exact-PCM controls). Tool source patches
replay exactly via scripts/verify_patch_replay.py; pins/digests are in patches/.
For local MSBuild prefer /m:1 /nr:false; parallel node reuse stalled this session.

## Next work

Read NEXT_STEPS.md, current HANDOFF.md sections, TIMING.md and ACCURACY_ISSUES.md.
Extend real gameplay and save progression; build deterministic input-poll replay;
then compare more pixels/audio/CPU contexts and additional module lifetimes.
Do not uncap FPS or change original game bytes. Keep all game-derived code,
binaries, saves, captures and reports ignored. Run check_public_tree.py
--source-tree before staging/packaging. Nothing has been published.
