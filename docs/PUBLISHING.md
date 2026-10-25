# GitHub content boundary

The repository is intended to contain build/analysis scripts, authored patches,
configuration, hashes, and explanatory documentation. A user provides their own
disc. Nothing has been uploaded and no GitHub remote is configured.

Keep ISO/extracted files, game-derived C/assembly/objects/native modules, resource
data, saves, screenshots and memory captures out of the public tree and releases.
They live under ignored original/, generated/, reports/, build/, captures/ and
private/. Do not place a ROM in Git LFS. .gitignore does not remove files already
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
