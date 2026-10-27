# GitHub content boundary

The repository is intended to contain build/analysis scripts, authored patches,
configuration, hashes, and explanatory documentation. A user provides their own
disc. The repository is on GitHub as a private repo (BigSnek9/wario-world-recomp,
2026-10-27).

Releases (decided by the owner on 2026-10-27, the same model as ShadowRecomp,
Zelda 64: Recompiled and Unleashed Recompiled): a release zip may contain the
compiled runtime and the compiled game module, so a player unzips, picks their own
disc and plays. The disc supplies every asset; it is verified and extracted on the
player's PC on first run. This distributes game-derived compiled code: a widely
used but legally untested practice, accepted by the owner.

Keep ISO/extracted files, game-derived C/assembly sources and objects, resource
data, saves, screenshots and memory captures out of the repository and releases.
The one exception: README screenshots the owner chose, in docs/images/ (2026-10-27).
They live under ignored original/, generated/, reports/, build/, captures/ and
private/. The compiled module and runtime go only into release archives, never
into Git. Do not place a ROM in Git LFS.

GPL note: the runtime is GPL-licensed (Dolphin-derived); a public binary release
must make the corresponding source available (this repository plus the pinned
upstream commits) and keep the licence notices in the zip. Open before going
public (progress/KNOWN_ISSUES.md KI-010), together with a full credits pass. .gitignore does not remove files already
in history; review the actual index, history and release archive before posting.

Run scripts/check_public_tree.py before staging/releasing and inspect the staged
diff. The check is a practical guard, not legal clearance or a provenance audit.
Ignored third-party clones are fetched from pinned upstream URLs by build scripts;
their original notices and licenses must be preserved in source/binary releases.

DolRecomp and ModernGekko's top-level licenses are GPLv3; the runtime includes
other components with their own notices (including Dolphin-derived material).
For distributed binaries, review the complete corresponding-source and notice
requirements for the exact component combination. Tool licensing does not grant
rights to Nintendo/Treasure game code, assets, music, names, or branding.
An original-content-only repository reduces redistribution exposure but cannot
guarantee freedom from copyright/trademark claims or GitHub takedowns.

Sources checked 2026-10-24:

- https://github.com/ExpansionPak/DolRecomp/blob/main/LICENSE
- https://github.com/ExpansionPak/ModernGekko/blob/master/LICENSE
- https://docs.github.com/en/site-policy/content-removal-policies/dmca-takedown-policy

## Release checklist (player zip)

Tools: `release/launcher/` (WarioWorldRecomp.exe, native Win32 starter, CMake),
`scripts/make_release.py` (packages existing builds, never rebuilds the runtime or
module), `release/test_release.py` (clean-folder test, hidden and muted).

1. Nothing else running: no `moderngekko-run.exe` with `playtest-user`, no
   `MSBuild`. Never touch the player's install or
   `private/playtest-user`.
2. The runtime (`build/moderngekko/Release`) and the clang PGO module
   (`build/module-full-vectors-clang-pgo/gGWWE01_recomp.dll`) are the builds the
   player has been testing; `scripts/regression_suite.py` passes on them.
3. Commit the source first (the zip's SOURCE.txt names the commit; a dirty tree is
   marked "plus uncommitted changes").
4. `python scripts/make_release.py --version X.Y --build-launcher`
   - builds the starter (static CRT, disc pins compiled in from config/project.json,
     icon drawn by `release/launcher/make_exe_icon.py`);
   - checks the embedded controller profile against `configure_controls.py`;
   - stages the exe, `runtime\` (runner, `Sys\`, the VC++ runtime DLLs the runner
     imports, from the Visual Studio redist folder), `module\`, `LICENSES\` (project,
     ModernGekko, DolRecomp, Dolphin and every linked Dolphin external), README.txt,
     SOURCE.txt;
   - checks every imported DLL is shipped or part of Windows;
   - fails on any disc-derived file (content hash against `original/GWWE01`, disc
     magic words, game-id names), C/assembly sources, PDBs/objects, logs, saves,
     icons, or a `game` / `user` / `data` / `private` folder;
   - writes `dist/WarioWorldRecomp-vX.Y.zip`, `-source.zip` (git archive of HEAD) and
     a `.json` file list with SHA-256s.
5. `python release/test_release.py --iso <your.iso> --version X.Y --smoke`
   unzips into `private/release-test`, runs `--iso ... --setup-only --quiet` (timed),
   checks the extraction byte for byte against `original/GWWE01` and the pinned
   hashes, the coin icon against `release/coin_icon.py`, the configuration against
   the Python starter, then boots hidden through the starter (`--hidden-test`) and with
   `scripts/smoke_boot.py`; report and captures go to `private/runs/*-release-test`.
   Look at the captures (title screen by ~20 s).
6. Release notes: `docs/release/vX.Y.md` (New / Fixes / To play).
7. GPL: before a public release the source must be available. The repository is
   private; attach `WarioWorldRecomp-vX.Y-source.zip` to the release (or make the
   repository public) and keep the upstream pins in SOURCE.txt reachable.
8. Upload only when the owner asks (`gh release create vX.Y dist/WarioWorldRecomp-vX.Y.zip
   dist/WarioWorldRecomp-vX.Y-source.zip -F docs/release/vX.Y.md`). Never commit the zip,
   the module or any binary.
