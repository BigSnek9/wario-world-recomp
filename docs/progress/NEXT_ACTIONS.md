# Next actions

Ordered (2026-10-27). The game is complete; these are follow-ups. Issue IDs:
KNOWN_ISSUES.md.

1. **Trapdoor glow flicker (KI-007).** Get an F12 snapshot (savestate +
   screenshot in `data\reports`, or the starter's report folder) from a
   playtest, reproduce hidden, then check whether the glow is an untagged draw
   (keeps frame N under frame generation) or a screen-copy effect. Tools:
   `scripts/fps_flicker_check.py`, `WARIO_MTX_DEBUG=<file>`, identity hooks in
   `build_rel_bundle.py` `MATRIX_STACK_HOOKS`.
2. **Confirm WS-009 / WS-010 on screen (KI-008).** Save a state with a speech
   board open and one on a stage results screen (F12 or the play tracker), then
   compare 16:9 against 4:3 captures.
3. **Each new release:** attach `WarioWorldRecomp-vX.Y-source.zip`, keep the
   upstream pins in SOURCE.txt reachable and the credits current. Upload only
   on explicit request (../PUBLISHING.md). (KI-010, GPL source, closed: public
   since 2026-10-27.)
4. **Voice slider (KI-009).** Needs a listening pass to list Wario's voice SFX
   ids (../engine/AUDIO.md AU-005); the mixer table is ready.
5. **Wide-aspect HUD leftovers.** Boss HP bars and minigame timers at
   16:9-32:9; remaining GXCopyTex callers (fn_80070028, fn_800703CC,
   fn_8007239C, fn_8007A8A4, fn_8007B6F8) if an artefact is seen.
6. **Runtime cost.** StaticRecompCore dispatch (Run, ResolveNativeAddress,
   RefreshRelSections) is about 5-10% of the emulation thread; an
   OSLink/OSUnlink notification would allow cheaper REL revalidation.
