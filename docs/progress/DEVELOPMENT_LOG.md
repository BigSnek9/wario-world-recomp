# Development log

Newest first. Earlier history (2026-10-24..26 morning): ../PROGRESS.md and ../HANDOFF.md.

## 2026-10-26 (late night): optional 120 FPS frame interpolation

- New runtime fix scripts/tool_fix_wario_fps.py (env MODERNGEKKO_WARIO_FPS=1,
  launcher checkbox "Smooth 120 FPS", default off). It records each frame's GPU
  commands and start state, then at the XFB copy replays the frame with the
  main-camera projection corrected to the halfway camera (eye/up/target lerp,
  LookAt). The result goes to a private texture and is presented between VI
  swaps. Simulation, input and audio are unchanged. Design and numbers:
  docs/modding/FPS_UNLOCK.md.
- Replay fidelity: identity replay equals the real frame pixel-for-pixel in
  15/17 samples (the 2 others: stage-entry afterimage feedback effect).
- Pacing: the game's XFB copy lands ~15 ms into each frame, so the real frame
  is held half a frame after the in-between one. Sleeping on the video thread
  for that cost 7-9% speed in boss arenas; holding it from the command loop
  fixed it (CB41 0.992x, CB21 0.999x; 94% of present gaps 6-10 ms).
- Pitfall: Present.cpp is inside namespace VideoCommon; globals defined there
  need VideoCommon:: when declared extern elsewhere.
- Pitfall: re-applying an edited tool_fix block duplicates it. For the six
  VideoCommon files only this fix touches, `git checkout` them in
  vendor/dolphin and re-run apply_tool_fixes.py.

## 2026-10-26 (night)

- A003 resolved on tested routes: native system-register mtspr/mfspr
  (tool_fix_native_spr.py); hook_interp 0, JIT 0; differential check mode
  WARIO_SPR_CHECK=1 0 mismatches; regression passes; suite guards hook_interp=0.
  A first variant without the full SyncOut/SyncIn broke early boot (stale
  segment/MMU state) - kept the full sync.
- Launcher: live volume slider (set_volume automation command), static texture
  extractor (scripts/extract_textures.py, 1,701 textures, HD-loader names; RSC
  format in docs/engine/ASSETS.md), play tracker (stage log, perf log, per-area
  savestate checkpoints, save history).
- KI-002 (water) and KI-005 (brightness = Dolphin HDR processing) closed by
  human side-by-side comparisons.

## 2026-10-26 (afternoon session)

- Committed the prior session's uncommitted work as baseline 18f7654.
- Save/Continue: a byte-identical copy of the human's stage-1-cleared GCI loads
  from the file menu into the hub (first evidence of progressed-save restore).
- Frozen water (KI-002): found the first Greenhorn river/waterfall by walking
  (probe private/probes/explore_forward.json, ~36 s); a checkpoint there shows
  the water animating every second. Not reproduced.
- Slowdown (KI-001): built tools/sample_profile.cpp (read-only thread sampler)
  and a symbol-enabled runtime copy (build/moderngekko-prof, RelWithDebInfo with
  /O2 /Ob2). Findings: the emulation thread is single-core "CPU-GPU"; gameplay
  spends ~53% of it in generated game code, ~23% idle. Dual-core gave no gain on
  the boot dip. GPU (RTX 5090) idle.
- Root cause candidate: MSVC compiles DolRecomp's giant per-chunk switch
  functions poorly (333 MB .text). The upstream template targets Clang.
  A clang-cl build of the identical generated sources and flags (/O2 /fp:strict)
  is 133 MB and cuts game-code time to ~30% (idle 43%) in the same checkpoint,
  same native instruction counts (108.05M vs 108.17M over the run).
  Lockstep validation of a clang-built instrumented twin: Greenhorn walk
  12,539 checks / 0 reports (7,881 PCs; MSVC twin 12,597 / 0), title -> save
  load -> hub 14,258 / 0. Launcher now prefers the clang module.
- Runtime dispatch overhead (boot dip ~15 s, title REL): generated code calls
  ctx->host_call on every dolrecomp_call, routed into ModManager even with
  --no-mods. Fix (scripts/tool_fix_mod_dispatch.py): wire host_call only when
  mods are loaded, plus empty-map early-outs. RefreshRelSections now reuses a
  scratch vector (tool_fix_rel_scratch.py). Boot dip min speed 0.53x -> ~0.88x.
  Lockstep with the new runtime: 12,604/0 and 14,241/0.
- Tried and reverted: hashing the OS module list to skip RefreshRelSections.
  Exact, but the hash cost as much as the work it saved (no measurable gain).
- Engine research: decoded Dolphin's bundled 16:9 Gecko code against original
  code (docs/engine/WIDESCREEN.md); camera defaults fn_80068250 (aspect 4/3,
  FOV 45, 0.125/1024/1008); player pointer 0x801FDA00 with position at +0x14.
- Tooling: smoke_boot --profile-at/--module/--dolphin-setting/repeatable
  --memory-at; scripts contact_sheet, run_summary, profile_timeline, asm_lookup.
- Pitfall: Git Bash rewrites "/O2"-style arguments into paths
  (C:/Program Files/Git/O2). Set MSYS_NO_PATHCONV=1 or use PowerShell/Python.
- Pitfall: Dolphin's shared PCH breaks a Release build with /Zi; use the
  RelWithDebInfo config (embedded /Z7) with /O2 /Ob2 overrides instead.
