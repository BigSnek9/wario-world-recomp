# Resume quickly

Work in F:/AI Projects/Recomp/Wario World/Recomp. Rules: ../AGENTS.md (all
tests hidden and muted, ask before new installs, keep game-derived material
private, preserve private/playtest-user, the owner's saves).

## Where things stand

The game is complete and playable start to finish; enhancements live in the
in-game menu. Status, builds and reproduce commands:
[progress/CURRENT_STATUS.md](progress/CURRENT_STATUS.md). Then read
[progress/NEXT_ACTIONS.md](progress/NEXT_ACTIONS.md) and
[progress/KNOWN_ISSUES.md](progress/KNOWN_ISSUES.md). All docs:
[README.md](README.md).

## Running it

- Owner's game: `Play-WarioWorld.cmd` (windowless starter
  `launcher/wario_launcher.pyw`, profile `private/playtest-user`). Agents do
  not launch this visible, audible session for tests.
- Release zip and its clean-folder test: [PUBLISHING.md](PUBLISHING.md).
- Build from an ISO: `Install-WarioWorld.cmd` (`installer/`).

## Hidden test example

Resume a private checkpoint in a fresh run folder (copies its user data):

```powershell
python scripts/smoke_boot.py --vectors --lockstep --lockstep-limit 0 --graphics OpenGL --seconds 60 --load-state private/runs/20261026T111939310041Z-8d4aab64/control/checkpoint.savestate --seed-user private/runs/20261026T111939310041Z-8d4aab64/user --capture-cadence 10
```

For the uninstrumented module replace `--lockstep --lockstep-limit 0` with
`--full`; for the runtime's original-code JIT use `--reference`.
`--dump-audio` writes private WAVs with No Audio Output; `--save-state-at 45`
writes a private checkpoint. Probe format and timing limits:
[PROBES.md](PROBES.md).

Checks: `python scripts/regression_suite.py`, `python -m unittest discover -s
scripts`, `scripts/verify_lockstep_context.py`,
`scripts/verify_audio_comparison.py`. Tool source patches replay with
`scripts/verify_patch_replay.py`; pins and digests are in patches/. For local
MSBuild prefer `/m:1 /nr:false` (parallel node reuse stalled before).

## Before staging

Keep game-derived code, binaries, saves, captures and reports ignored; run
`python scripts/check_public_tree.py --source-tree`. Never commit the module or
release zips. Accuracy limits: [ACCURACY_REVIEW.md](ACCURACY_REVIEW.md).
