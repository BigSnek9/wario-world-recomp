# Widescreen support plan

Findings: ../engine/WIDESCREEN.md (WS-001..003).

## Strategy (Hor+)

1. Camera: set the aspect default HC-0001 (0x801FE5B0) to `w/h` of the output;
   keep vertical FOV HC-0002 unchanged so 4:3 framing is preserved vertically.
   Find any other writers of camera block `+0x44` (cutscenes/bosses) first.
2. 2D space: set HC-0007 (0x801FE6CC) to `320 * (w/h) / (4/3)` so the
   orthographic 2D space widens instead of stretching.
3. HUD anchors: the WS-003 immediates move left/right HUD elements out to the
   new edges. For arbitrary aspects compute `x * (w/h) / (4/3)` instead of the
   16:9 constants. The fn_80062F3C / fn_8006EF1C group replaces computed
   values with constants that are only right for 16:9 - understand them first.
4. Host: set presentation aspect to match (custom aspect or Stretch to window
   with the guest doing the correction). Must not use Dolphin's Auto heuristic.

## Implementation route in the recomp

Prefer a host-side hook at the generated function level (func_8006xxxx) or a
data write at boot from a mod config, not edits to generated C. Keep the
original bytes for the baseline and record every changed address.

## Tests required

- Screenshot sweep: title, hub, Greenhorn Forest, pause menu, HUD at 4:3/16:9/21:9.
- Check sprites/fades that cover the screen (full-screen quads may assume 640).
- Verify culling at screen edges (wider view may expose popped objects).

## Update 2026-10-26: where the camera values are consumed

fn_80042714 (CAM-004) rebuilds the projection every camera update from block
+0x44 (aspect) and +0x48 (FOV), and also builds the culling side planes from
the same aspect. So a Hor+ mod can write aspect into the active camera block
([0x801FDA50]+0x44) or the default HC-0001 and both projection and culling
follow; no separate culling patch is needed for the side planes. HUD (WS-003)
and the 2D half-width (WS-002) still need their own changes.
