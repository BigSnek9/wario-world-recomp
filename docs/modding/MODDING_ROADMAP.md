# Modding roadmap

Each mod is a separate, switchable layer; with every option at its accurate
setting the unmodified game runs (see ../ACCURACY_REVIEW.md for what
"accurate" does and does not prove). All shipped mods are in the in-game menu
(IN_GAME_MENU.md).

| Mod | Status (2026-10-27) | Key findings | Doc |
|---|---|---|---|
| Widescreen / ultrawide | done: Hor+, edge HUD, 4:3 pause book / boards / results paper | HC-0001, HC-0007, WS-001..010 | WIDESCREEN_SUPPORT.md |
| Frame generation (60-240 FPS) | done: camera + object interpolation by GPU replay, display-locked pacing | T001-T009, CAM-002/004 | FPS_UNLOCK.md |
| Internal resolution, HD textures, HDR | done | | GRAPHICS_ENHANCEMENTS.md |
| Audio mixer | done except a Voice slider | AU-001..007 | ../engine/AUDIO.md |
| Cheats | done | G-0010..G-0015 | CHEATS.md |
| Adjustable FOV | candidate constant only | HC-0002 (45 deg vertical) | ../engine/CAMERA.md |
| Draw distance | candidates only | HC-0004/HC-0005 | DRAW_DISTANCE.md |

Cross-mod dependencies: MOD_DEPENDENCIES.md.
