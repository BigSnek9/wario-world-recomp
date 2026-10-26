# Camera system findings

## CAM-001 Camera parameter defaults - fn_80068250 (probable)

- main.dol 0x80068250, callers `fn_8006B29C`, `fn_8006C118`.
- Calls `fn_800375D0(r3=obj, r4=0xE)` then `fn_80068050(obj+0x264, 3)`;
  stores `obj` to global `lbl_801FDB20` (sda), so 0x801FDB20 is probably the
  active camera/scene-view singleton.
- Writes a parameter block reached through `[obj+0x14]`:
  `+0x14..+0x30` identity-like 0/1 values, `+0x34` -1.0, `+0x38` 0.125,
  `+0x3C` 1024.0, `+0x40` 1008.0, `+0x44` 1.3333 (aspect, see WIDESCREEN.md
  WS-001), `+0x48` 45.0, `+0x4C` 0.025.
- Then a virtual call through `lbl_801FDA00` vtable slot +8 with
  `[obj+0x14]+0x94`.
- Interpretation: 45 = vertical FOV (deg), 0.125 = near plane,
  1024 = far plane, 1008 = possibly fog end or a cull distance just inside
  the far plane. **Speculative** until the projection build (C_MTXPerspective
  / GXSetProjection equivalent) is traced back to these offsets.
- Relevance: FOV/aspect mods (WIDESCREEN), draw distance (CULLING / DRAW_DISTANCE).
- Regression test needed: compare a stage screenshot before/after changing one
  value in a private experiment build; never in the baseline.

Constants file: research/HARDCODED_CONSTANTS.json (HC-0001..HC-0008).
