# Agent handoff

Canonical project: this repository (the folder holding AGENTS.md).
Input: ../Game/Wario World (USA).iso (GWWE01 rev 0). Started 2026-10-24.
Rules: ../AGENTS.md. Master brief: ../../READ ME AGENTS.txt.

## Current handoff (2026-10-27)

The recompilation is complete and the game is playable start to finish; the
owner has finished a playthrough. Optional enhancements (frame generation,
widescreen, resolution, HDR, HD textures, audio mixer, cheats, controls) live
in the in-game menu. Start from:

- [progress/CURRENT_STATUS.md](progress/CURRENT_STATUS.md): state, builds,
  reproduce commands (authoritative);
- [progress/NEXT_ACTIONS.md](progress/NEXT_ACTIONS.md) and
  [progress/KNOWN_ISSUES.md](progress/KNOWN_ISSUES.md): what is open;
- [README.md](README.md): index of every doc.

No user input is needed for the open items except an F12 snapshot of the
trapdoor glow flicker (KI-007) and the owner's go-ahead for any upload.

History: the dated checkpoints of 2026-10-24..26 that used to be here are in
[PROGRESS.md](PROGRESS.md); later work is in
[progress/DEVELOPMENT_LOG.md](progress/DEVELOPMENT_LOG.md).

## User intent and constraints

Original brief (2026-10-24): deliver a full faithful static recompilation of
Wario World, with progressive documentation another agent can resume. Preserve
original behavior first. Record every frame/refresh dependency for later FPS
uncapping; do not uncap yet.
Ask before installing new software. Local DolRecomp/ModernGekko downloads and
builds/dependencies are already approved. Portable Ghidra 12.1 + GameCube loader
were additionally approved on 2026-10-25. No system tools installed or GitHub
content published. User asked about sharing: public tree excludes game material.

Since then: the owner started the FPS project (frame generation is an optional,
presentation-side layer; the simulation still runs at 59.94 Hz), approved
subagents (2026-10-26) and the ShadowRecomp-style release model (2026-10-27).
The repository is public on GitHub (2026-10-27) with release v1.0.

## Verified baseline

GWWE01 rev 0; ISO SHA-256
37b1d6d8c1d8e5629941c6418aba64d05184837544cd2839ab83b19664239007.
Main DOL SHA-256
3550d57e1d76bbac4265158360294a5b9d3a0c1157eee88fd4b7e8591af2d49e.
Entry 0x80005304, main 0x8002FC00, original r13 base 0x802056E0 and r2 base
0x80206100. Extracted DOL length 1,898,016 bytes; 245 FST files totaling
267,617,800 bytes. Independent audit compared extracted contents to ISO offsets.

Eight REL version-2 modules are present; names/IDs in engine/ARCHITECTURE.md. No missing import
IDs. Full section/import/hash inventory is reports/inventory.json.
4546 main function locations recovered from exception tables by dtk 1.8.4.
generated/analysis contains private assembly/objects for main and all RELs.

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
  Never force-add them. Release zips may carry the compiled runtime and module
  (owner decision 2026-10-27, ../AGENTS.md and PUBLISHING.md), never disc data,
  generated sources, saves or captures.

## Ghidra (portable, local)

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
