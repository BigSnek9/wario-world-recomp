# Regional support work

## Status

This branch is preparing support for the user's local PAL disc, Wario World
GWWP01 revision 0. This is not yet a working PAL recompilation.

The existing playable build remains the USA GWWE01 revision 0 build. Keep its
pins, generated module and runtime behavior unchanged.

## Known PAL input identity

The local user dump is a trimmed ISO:

- Disc ID: `GWWP01`
- Revision: `0`
- File size: `275240820` bytes
- ISO SHA-256: `6D9C7A4460C13A2066C4A1CEDC4DCEF899C7A032227C37CA95E43605F49EEEDE`
- Extracted main DOL SHA-256:
  `DC1136BE0C47FE3E35551FCE2F0E715FEC9B488B9F6E5D3BE27A9342D6034C13`

The matching local PAL profile metadata is in
`config/profiles/GWWP01.json`. Its hashes identify the user's local input;
they are not public game assets.

## Required work before PAL can be called supported

1. Extend the project configuration/build tooling to select a profile by
   disc ID, without changing the USA default.
2. Make extraction and launcher validation profile-aware. Do not assume a
   full 1:1 GameCube image size: this PAL dump is trimmed. Validate the disc
   structure and pinned hashes instead.
3. Analyze the PAL DOL and all eight PAL RELs independently. Do not reuse USA
   addresses, symbols, relocation maps, generated C, or module binaries unless
   equivalence is demonstrated.
4. Generate PAL-specific analysis and recompilation outputs locally in ignored
   directories. Never commit game-derived generated sources or binaries.
5. Build a distinct PAL module/runtime selection (or a verified multi-profile
   module architecture) and preserve the USA module path.
6. Run the project's hidden, muted regression checks and verify boot, title,
   gameplay, module loading, saves, and regional video behavior.
7. Update the launcher and user documentation only after a tested PAL build
   exists.

## Current blockers

- The PAL DOL/RELs have not yet been analyzed and recompiled in this branch.
- The launcher currently pins a single USA profile and rejects non-USA IDs.
- The launcher CMake currently assumes a full-size ISO, which does not match
  the user's trimmed PAL dump.
- A PAL profile JSON file alone does not make the runtime compatible.

## Safety and repository hygiene

Keep the user's ISO and all extracted/game-derived material local and ignored.
Do not commit game data, generated recompilation C/assembly, module DLLs,
saves, captures, or reports. Before staging any future source changes, run:

```powershell
python scripts/check_public_tree.py --source-tree
```

Follow `AGENTS.md` and the existing project test rules.
