# Tool review and route

## Provided packages

| Package | Finding | Use here |
| --- | --- | --- |
| Ghidra MCP | Source bridge/plugin; requires an actual Ghidra installation and setup | Suitable for later PowerPC analysis once Ghidra/loader capability is verified; no connected server exists in this chat |
| IDA MCP | Requires IDA 9.4+, idalib and Python | No suitable IDA installation found in checked locations; do not install paid tooling without consent |
| REA | Analysis orchestration; Windows Ghidra P0 is limited to approved x86-64 PE targets | Its documented Windows admission does not fit Gekko DOL; do not claim support based on its generic name |
| ILSpy | .NET decompiler | Wario World is native PowerPC, so it does not decompile the game |

The packages are sources, not complete installed reverse-engineering environments.
No global agent/MCP configuration was changed. Read the actual package README
and AGENTS.md before modifying those repositories.

## Existing usable tools

- dtk 1.8.4, commit a0c455e46cab58e1d2e0885623f85089ff0499db, found in an
  adjacent existing recomp project. Used read-only on original game inputs.
  On Windows, its VFS DOL paths need a relative path from the disc extraction
  directory; an absolute F: path was misparsed. Disc extraction accepted it.
- Python 3.12.6 for independent standard-library format/hash audits.
- MSVC 19.39.33521, CMake 4.3.3, Ninja; LLVM 23.1.3 present.
- Existing Dolphin 2606a for isolated reference comparisons (used by the owner
  for side-by-sides; agents do not launch its GUI for tests).
- Java 21 present; Ghidra itself not found in checked project/program locations.

## Chosen implementation route

DolRecomp portable C backend + ModernGekko/Dolphin-derived hardware runtime.
This reuses a hardware model rather than rewriting GX/audio/device timing.
Exact FP mode is selected; no fast-math or FPS patches are authorized for baseline.
The optimized DolRecomp LLVM backend requires LLVM 19/20; installed LLVM 23
does not satisfy it, so it is disabled. This does not prevent the C backend.

Source pins are in config/project.json. ModernGekko has its own separately pinned
DolRecomp in vendor/dolphin/DolRecomp (71ce7f97419b1bb1ba9a9596c41507f6629e0fb0).
Do not mix its ABI/runtime with standalone output without checking compatibility.
The upstream port builder recompiles only the main DOL. Automatically loading
the disc's REL data in the runtime is not equivalent to compiling the REL code;
this project's scripts/build_rel_bundle.py compiles all eight RELs into the
module (REL_RUNTIME.md).

## Local fixes

scripts/apply_tool_fixes.py applies explicit, idempotent changes to pinned sources:

- Empty REL target sections contribute zero base plus addend, matching original
  OSLink behavior. Synthetic regression checks nonzero addend on an empty section.
  Patch bounds checks remain enforced for actual write locations.
- Create the runtime output directory before copying the recompiler. Otherwise
  CMake's copy can create a regular file called Release before executables link.
- Disable MSVC warning C4706 only for the vendored PNG target, whose intentional
  assignment expression was failing under its warnings-as-errors setting.
- Use explicit empty lambda parameter lists and #elif defined for compatibility
  with installed MSVC, plus explicit casts for the fixed-size socket table.
- Fix Windows _spawnv test quoting; the extraction test now passes in this path.
- Correct the lockstep detector for a continuation address inside a local loop;
  regression uses the actual detector and eight synthetic control-flow cases.
- Queue title updates on the host thread to avoid a Windows shutdown deadlock.

Upstream source patches are tool fixes, not game patches. Keep original inputs
unchanged and preserve diffs/provenance. Do not suppress relocation errors or
pretend rejected/omitted modules are successfully translated.

Portable Ghidra 12.1.3 and GameCubeLoader 1.3.1 were approved on 2026-10-25.
These are for deeper analysis, not required to run the current C build. No
system-wide installation or global agent registration is implied by that approval.

Installed under third_party/ghidra/ghidra_12.1.3_PUBLIC. Verified archives:

- ghidra_12.1.3_PUBLIC_20260817.zip: SHA-256
  93a5d11a9ad510622acaaf908c556a7b9b764d338e78a7567f3689bf5081fd54.
- Loader release 1.3.1 asset identifies its build as 1.3.0-921504c for Ghidra 12.1:
  SHA-256 9892f28fc1e7f19bb3fcec7cfb4ad2ab7504503b571d93de8b142a6f7bec8ed0.

The supplied connector builds as GhidraMCP 7.0.0 with Gradle 9.7.1 and Java 21.
ghidra_local.py binds loopback and redirects child APPDATA/LOCALAPPDATA privately.
import_ghidra.py disables symbol-map autoload to avoid the loader's GUI prompt.
Main import/decompilation succeed despite a nonfatal CodeWarrior-demangler error.

Additional fixes: reference interpreter FPCC field mask (256 regressions), explicit
JIT-entry accounting, and optional instruction-count-based shadow boundaries.
build_instrumented.py creates a separate ignored diagnostic DLL. refresh_patches.py
exports current source-only diffs, hashes and pinned checkout revisions.

## Automation protocol status

tools/automation_protocol.cpp serves pad injection (command=pad_frames) and
screenshots, both confirmed working in private runs; pad presses reliably
advance the title/menu flow. The status line's navigation_* fields are unwired
stubs: the struct exists in automation_protocol.hpp and is printed by
formatStatus, but no runtime code populates it from guest memory, so they read
zero forever. Gameplay detection currently requires screenshots. Wiring these
fields to real game state (after identifying the structures in Ghidra) is open
work. smoke_boot.py --capture-cadence N saves numbered screenshots every N
seconds for observing menu progression.

## Private replay and audio checks, 2026-10-26

smoke_boot.py supports private --load-state/--seed-user/--save-state-at replay
and --dump-audio with No Audio Output. Probe origin waits for post-load renderer
counter status; this is behavioral navigation, not deterministic input polling.
compare_audio.py compares raw PCM and optionally aligns initial exact silence;
verify_audio_comparison.py tests negative controls. audit_loaded_main.py pins
original input hashes and audits all loaded DOL text. inspect_boot.py now also
validates the live module queue; audit_loaded_rel.py requires queue membership.
inventory_helpers.py separates traced helper categories and verifies measured
fast-cache/interpreter counter accounting. verify_lockstep_context.py compiles
production predicates against code reuse/window regressions. The legacy
scripts/test_lockstep_boundary.py is now a guarded compatibility entry point,
so unittest discovery no longer compiles code as an import side effect.
