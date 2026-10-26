# Mod dependencies

- Widescreen needs guest camera aspect (HC-0001), 2D half-width (HC-0007), HUD immediates (WS-003) AND host aspect change together.
- FPS unlock depends on the retrace gate (T001), fixed-step module updates (T006/T007) and input latching (T002); see FPS_UNLOCK.md.
- Draw distance touches the camera far plane (HC-0004) which may also drive fog/culling; gameplay activation must be checked separately.
