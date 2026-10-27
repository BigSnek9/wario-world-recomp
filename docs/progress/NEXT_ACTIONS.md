# Next actions

Ordered. Update as items finish (2026-10-27 early morning).

1. **Human feedback on game-level object interpolation.** The menu default is
   now frame rate 240 with Motion = camera + objects. Watch for anything still
   moving wrongly in the in-between frames. Any report → reproduce with the
   play-tracker state for that area:
   - `scripts/fps_world_sweep.py`, `fps_flicker_check.py`;
   - `WARIO_MTX_DEBUG=<file>` for identity collision sites.
2. **Untagged draws.** Anything not drawn through the engine matrix stack
   (0x801FDA38) keeps frame N (camera only). If an effect looks 60 Hz, find its
   matrix path and add an identity hook (build_rel_bundle.py
   `MATRIX_STACK_HOOKS`, `wario_mtx_hook`).
3. **Pacing at 3x/4x.** It follows the game's own frame-time irregularity.
   Possible improvement: estimate the game's frame period and spread
   in-between frames over it (needs care not to add latency).
4. **Widescreen HUD.** Check boss HP bars, minigame timers and the pause menu
   at 16:9-32:9 (HUD_EDGE_SITES covers hearts, coins, counters and the
   indicator).
5. **Other screen-copy effects.** The remaining GXCopyTex callers
   (fn_80070028, fn_800703CC, fn_8007239C, fn_8007A8A4, fn_8007B6F8) may have
   widescreen or interpolation artifacts; trace their draw-backs when seen.
6. **Coverage.** World 4/5 and the ending, as the human plays (the play
   tracker saves states). Lockstep-check the new states with the PGO twin.
7. **Runtime cost.** StaticRecompCore dispatch (Run, ResolveNativeAddress,
   RefreshRelSections) is still about 5-10% of the emulation thread; an
   OSLink/OSUnlink notification would allow cheaper REL revalidation.
