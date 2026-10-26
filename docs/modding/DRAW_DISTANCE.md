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
