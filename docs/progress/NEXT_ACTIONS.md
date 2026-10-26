# Next actions

Ordered. Update as items finish.

1. Human retest of Greenhorn Forest slowdown/water with Play-WarioWorld.cmd
   (now clang module + dispatch-fixed runtime). Not blocking agent work.
2. Reproduce box-breaking slowdown headlessly: navigate with player pointer
   0x801FDA00 (+0x14 position) to breakable boxes/enemies; measure speed/fps
   and profile. Distinguish host stall from intentional hit-stop (fps drops
   with speed ~1.0 would be guest-side).
3. Remaining per-dispatch runtime cost (~20% of the emulation thread):
   StaticRecompCore::Run loop, ResolveNativeAddress -> RefreshRelSections on
   every REL dispatch in runtime-PC mode. A cheaper exact revalidation would need
   an OSLink/OSUnlink notification instead of polling.
4. Generated-code cost: profile the clang module per guest function (link with
   /MAP or PDB) to find hot guest code; consider DolRecomp output options that
   avoid storing ctx->pc per instruction only if lockstep stays clean.
5. Coverage: Greenhorn Ruins, World 1 boss, worlds 2-4 - needs progressed saves
   from the human or long scripted routes; WWUSS1 already loads in Greenhorn.
6. Engine research backlog: projection matrix build from the camera block
   (+0x44 aspect, +0x48 FOV), GXSetViewport/Scissor sites, frame counters, what
   triggers WWUSS1 linking.
