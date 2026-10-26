# Wario World Recomp

In-progress Windows static recompilation of **Wario World USA, GWWE01 revision 0**.
The original game behavior and speed are the baseline. FPS uncapping is a later,
separate project; timing dependencies are recorded as they are discovered.

**Status: experimental, partially validated build. The user completed stage one,
but reports frozen water, slowdowns and transient stretching. Shared renderer
shortcuts remain unvalidated; whole-game/hardware accuracy and static-only
execution are not established.** See [the accuracy review](docs/ACCURACY_REVIEW.md). Read [START_HERE](docs/START_HERE.md)
for a concise checkpoint and [the handoff](docs/HANDOFF.md) for detailed evidence.

## What is established

- The extracted main executable and all 245 disc filesystem files match the
  supplied ISO byte for byte; their hashes and offsets are preserved locally.
- Main executable plus all eight dynamically loaded RELs translate to C using
  exact-semantics mode after an empty-section relocation tool fix.
- No original game bytes or FPS-unlock patches applied. Host rendering defaults
  previously included Auto aspect and forced progressive output; see the review.
  Presentation is now explicitly 4:3 at native 1x; other assumptions remain open.
- Runtime and native main DLL build with installed MSVC. OpenGL startup reaches
  the title screen near 59.94 FPS at 1x internal scale and exits cleanly.
- The clean main-plus-eight-REL port DLL (no diagnostic instrumentation) builds
  via `python scripts/build_rel_bundle.py --clean --vectors` into
  `build/module-full-vectors/Release/gGWWE01_recomp.dll`; its bounded
  `smoke_boot.py --full --vectors` hub run renders near 59.94 FPS, original
  speed, clean exit, zero JIT entries on this route.
  The instrumented twin for lockstep verification is still built without
  `--clean`. Original bytes and behavior are unpatched in both.
- Native first-stage transition: 12,785 differential checks, zero reports,
  zero JIT entries and natural memory-card file creation. Greenhorn Forest loads.
  A 16-second idle DSP audio capture matches the runtime reference after onset
  alignment. Instruction helpers
  remain, and gameplay/full accuracy are still unverified. Tests are hidden and muted.
- [Timing ledger](docs/TIMING.md), [validation criteria](docs/VALIDATION.md),
  [tool review](docs/TOOLING.md), [progress](docs/PROGRESS.md) and
  [publication boundary](docs/PUBLISHING.md) are maintained progressively.

## Local build stages

Python 3.11+ and existing Git, CMake, Ninja and Visual Studio 2022 C++ tools.
The current route is Windows x64 with portable C; LLVM backend is disabled.
The scripts do not install global tools. `fetch` explicitly downloads pinned
third-party source/dependencies into this folder. Review source licenses.

```powershell
python scripts/build.py check
python scripts/build.py fetch
python scripts/build.py tools --jobs 8
python scripts/build.py extract --iso "path\to\Wario World (USA).iso"
python scripts/build.py audit --iso "path\to\Wario World (USA).iso"
python scripts/build.py translate --jobs 8
python scripts/build_rel_bundle.py --clean --vectors
```

The final stage produces the uninstrumented main-plus-eight-REL candidate,
including physical SDK paths, under `build/module-full-vectors/Release/`.
Drop the `--clean` flag to build the instrumented
diagnostic twin used by lockstep verification instead. `scripts/rel_timing_candidates.py`
regenerates the REL portion of the frame/refresh dependency inventory.

Extraction refuses to overwrite existing inputs. For this local project the
already extracted disc is under `original/GWWE01`; do not extract over it.
`module-main` is an experimental main-module-only compilation stage requiring an
x64 Visual Studio developer shell; the full port is the `--clean` bundle above.
For bounded diagnostics after building:

```powershell
python scripts/smoke_boot.py --seconds 8 --lockstep
python scripts/smoke_boot.py --full --vectors --seconds 120 --graphics OpenGL --probe-file config/probes/start_adventure.json --pad-hold 12 --capture
```

The latter runs hidden and muted. Each run gets a new private user folder;
captures and logs remain private. Instruction-level interpreter helpers are still
used. See [open accuracy issues](docs/ACCURACY_ISSUES.md) before interpreting results.

Build logs, manifests and disassembly stay local under ignored directories.
The eight module IDs are 1=WWUSS1, 2=WWUSS2, 3=WWUSS4, 4=WWUSS5, 5=WWUSOP,
6=WWUSED, 7=WWUSPF and 8=WWUSTT. Runtime addresses must be measured/relocated;
the translator's synthetic fixed bases must not be confused with actual loads.

## Sharing

This repository is designed to publish authored scripts, configuration, patches
and explanatory documentation. Supply your own original disc. Never commit
the disc, extracted assets, generated game code, compiled game modules or captures.
Run `python scripts/check_public_tree.py` and review the actual index/history
before publishing. No GitHub upload has been made.

Upstream tools: [DolRecomp](https://github.com/ExpansionPak/DolRecomp) and
[ModernGekko](https://github.com/ExpansionPak/ModernGekko), including its
Dolphin-derived runtime. See [publishing notes](docs/PUBLISHING.md) for licensing
and the limits of the publication guard.

Original project scripts and authored patches are provided under GPLv3; preserve
the component licenses/notices that apply to upstream material.

For your own later test, double-click `Play-WarioWorld.cmd`; see [keyboard and
playtest notes](docs/PLAYTEST.md). The agent does not run this visible/audible
launcher during automated tests. Full-game accuracy remains unverified.
