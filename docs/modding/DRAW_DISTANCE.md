# Draw distance plan

Candidates: camera far plane 1024.0 (HC-0004) and 1008.0 (HC-0005) set by
camera init fn_80068250 (../engine/CAMERA.md). Unknown whether 1008 is fog end
or an object cull radius.

Before changing anything:
1. Trace the projection matrix build to confirm which offset feeds the far plane.
2. Find object visibility tests (distance compares against camera position) and
   separate render culling from actor update/activation culling.
3. Check fog setup (GXSetFog call sites) - extending the far plane without fog
   adjustment exposes level edges.

## Update 2026-10-26

Confirmed: the active camera block ([0x801FDA50]) holds near +0x38 and far
+0x3C, and Greenhorn Forest uses near 0.5 / far 2048 (defaults 0.125 / 1024),
so each stage sets its own range. +0x40 = far - 16 in both cases. Extending
draw distance = raising +0x3C (and probably +0x40) after the stage sets it,
then rebuilding the +0x54 projection; depth precision gets worse as far/near
grows. Object activation distances are still unmapped.
