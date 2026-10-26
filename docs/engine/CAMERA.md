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

## CAM-002 Camera block layout - CONFIRMED at runtime (2026-10-26)

Evidence: Greenhorn Forest MEM1 snapshot (private/runs/20261026T165304735180Z-f5082ae1,
snapshot 1). Global `0x801FDA50` -> active camera block (0x804AF520 there; heap,
always go through the pointer). Same block type that fn_80068250 initializes.

| Offset | Greenhorn value | Default (fn_80068250) | Role |
|---|---|---|---|
| +0x38 | 0.5 | 0.125 | near plane |
| +0x3C | 2048.0 | 1024.0 | far plane |
| +0x40 | 2032.0 | 1008.0 | far - 16 (fog end or cull radius; still unconfirmed) |
| +0x44 | 1.33333 | 1.33333 | aspect (width/height) |
| +0x48 | 45.0 | 45.0 | vertical FOV, degrees |
| +0x4C | 0.025 | 0.025 | unknown |
| +0x54..+0x93 | 4x4 matrix | - | GX perspective projection |
| +0x98 | matrix? | - | passed to fn_800479F4 after projection upload (view matrix candidate) |

The +0x54 matrix equals the SDK C_MTXPerspective result for those values:
m00 = cot(fovy/2)/aspect = 1.81066, m11 = cot(fovy/2) = 2.41421,
m22 = -n/(f-n) = -0.000244, m23 = -f*n/(f-n) = -0.50012, m32 = -1.
So changing +0x44 (aspect) or +0x48 (FOV) takes effect only when the game
rebuilds +0x54; find that rebuild (not yet located) before patching values.
Near/far differ from the defaults, so stages set them: draw distance is a
per-stage parameter (see ../modding/DRAW_DISTANCE.md).

## CAM-003 GX projection/viewport call sites - CONFIRMED (static)

- fn_8019B0FC = GXSetProjection(mtx, type): writes XF 0x1020 with the SDK
  ortho/perspective packing. fn_8019B1B0 = GXSetProjectionv (from __GXInitGX).
- fn_8019B500 = GXSetViewport (calls jitter variant fn_8019B3FC, XF 0x101A).
- fn_8019B524 = GXSetScissor (BP offsets +342).
- Perspective uploads (type 0) from `[0x801FDA50]+0x54`: fn_8006F764, fn_800702E8,
  fn_800722B8, fn_8007B580, fn_800E0808; also fn_80067F44 (obj+0x10).
  Orthographic (type 1): fn_80046F34, fn_80067C34, fn_8006F954, fn_800756E8,
  fn_8007A75C, fn_800E071C.
- fn_80067C34: GXSetViewport(0, 0, [0x801FDA20], [0x801FDA24], obj+0x50, obj+0x54),
  GXSetScissor(0, 0, u16 [0x801CEFBC+4], u16 [0x801CEFBC+6]), ortho projection.
  0x801FDA20/24 = 512.0 / 448.0 at runtime: the 3D render target is 512x448, and
  0x801CEFBC is likely the GXRenderModeObj (fbWidth/efbHeight).
