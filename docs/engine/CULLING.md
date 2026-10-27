# Culling and visibility

- Camera far plane and a "far - 16" distance: defaults 1024.0 / 1008.0
  (HC-0004/HC-0005), set per stage (Greenhorn Forest 2048 / 2032; CAMERA.md
  CAM-002).
- The per-frame camera update fn_80042714 builds four frustum side planes from
  FOV, aspect and the +0x40 distance (CAMERA.md CAM-004), so a wider aspect
  widens this culling too; the widescreen mode relies on that.
- Rendering vs gameplay activation culling is not yet distinguished; object
  activation distances are unmapped (../modding/DRAW_DISTANCE.md).
