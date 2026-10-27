# Engine index (GWWE01 rev 0)

Start here for engine knowledge. Every finding has a stable ID and an original
main.dol/REL address. Machine-readable records: ../research/*.json.
Look up any main.dol address in the private disassembly with
`python scripts/asm_lookup.py <addr>` (prints containing function + callers).

| System | Doc | Key IDs |
|---|---|---|
| Architecture / main loop / modules | ARCHITECTURE.md | F-0001, F-0007, F-0008 |
| Frame timing | FRAME_TIMING.md -> ../TIMING.md | T001-T007 |
| Camera | CAMERA.md | CAM-001, HC-0001..0006 |
| Widescreen / 4:3 assumptions | WIDESCREEN.md | WS-001..003 |
| UI / HUD | UI.md | HC-0007, WS-003 |
| Culling / draw distance | CULLING.md | HC-0004, HC-0005 |
| Rendering | RENDERING.md | F-0005, F-0006 |
| Input | INPUT.md | T002 |
| Audio (MusyX, BGM streams, runtime mixer) | AUDIO.md | AU-001..AU-007 |
| Memory / module loading | MEMORY.md | |
| Disc assets / texture banks | ASSETS.md | |
| Physics, player, progress/save data, cheats | PHYSICS.md, ../modding/CHEATS.md | G-0007, G-0010..G-0015 |
| Animation, scripting | ANIMATION.md, SCRIPTING.md | (mostly unmapped) |

ID prefixes: F- function (FUNCTION_DATABASE.json), HC- hardcoded constant
(HARDCODED_CONSTANTS.json), T- timing (TIMING.md), WS- widescreen, CAM- camera, AU- audio,
KI- known issue (../progress/KNOWN_ISSUES.md), A- accuracy issue
(../ACCURACY_ISSUES.md).

Confidence vocabulary: confirmed (traced in code and/or measured at runtime),
probable (strong static evidence, role inferred), speculative (pattern only).
