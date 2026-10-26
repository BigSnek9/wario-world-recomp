# Modding roadmap

Baseline first: no mod is applied until the original game is stable and its
behaviour measured (see ../ACCURACY_REVIEW.md gates). Each mod must be a
separate, switchable layer; the unmodified build stays the reference.

| Mod | Status | Key findings | Doc |
|---|---|---|---|
| Widescreen / ultrawide | research: patch sites mapped from the community 16:9 code and verified against original code | HC-0001, HC-0007, WS-003 | WIDESCREEN_SUPPORT.md |
| Adjustable FOV | candidate constant found | HC-0002 (45 deg, speculative) | ../engine/CAMERA.md |
| 60+ FPS | research: simulation gated by retrace wait; fixed-step updates confirmed | T001-T007 | FPS_UNLOCK.md |
| Draw distance | candidates only | HC-0004/HC-0005 | DRAW_DISTANCE.md |
| Higher internal resolution | host setting exists; held at 1x for baseline | | GRAPHICS_ENHANCEMENTS.md |

Suggested order once the baseline is stable: widescreen (lowest risk, data and
immediates only) -> FOV -> draw distance experiments -> FPS (needs
interpolation design and per-system audit).
