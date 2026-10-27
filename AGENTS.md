# Wario World Recomp

Read README.md, docs/START_HERE.md, docs/HANDOFF.md, docs/PROGRESS.md and docs/TIMING.md before work.
The task is a faithful Windows static recompilation of GWWE01 revision 0.
Keep the original game speed and behavior until the user starts the FPS project.
Never describe a successful translation, compile, or boot as bit-accuracy proof.
Track every fallback, unsupported instruction, runtime workaround and changed byte.
Record timing discoveries immediately with module, address/section offset, evidence,
confidence, and a reproduction/test; distinguish candidates from confirmed behavior.
Update handoff and progress after each meaningful milestone or blocker.
Ask before installing new software. Local DolRecomp/ModernGekko dependency downloads
and builds were authorized on 2026-10-24; new system installs need separate consent.
Portable Ghidra 12.1 plus the GameCube loader were approved on 2026-10-25,
including building the supplied connector locally.
Do not publish, push, upload, or distribute game inputs, assets, disassembly,
game-derived generated code (C/assembly sources), saves or captures.
Keep those under ignored directories. Use scripts/check_public_tree.py before staging.
Release builds (user decision, 2026-10-27, "ShadowRecomp style"): GitHub releases may
contain the compiled runtime and the compiled game module (gGWWE01_recomp.dll) so
players can start in seconds; the player's own disc supplies every asset, extracted on
first run. Never include disc data, extracted files, generated sources, saves or
captures in a release, and never commit the module or releases to the repository.
Upload a release only when the user asks for that upload.
README screenshots the user chose (docs/images/, 2026-10-27) are the only captures
allowed in the repository; add more only when the user asks.
Never force-add ignored files. Public scripts must accept a user-supplied disc.
Do not silently substitute an interpreter/JIT and call it a complete static recomp.
Subagents were authorized by the user in chat on 2026-10-26 ("you may use subagents");
the user wants mostly autonomous work and only essential questions.
The master brief is ../READ ME AGENTS.txt; its docs layout lives under docs/progress,
docs/engine, docs/modding and docs/research (start at docs/progress/CURRENT_STATUS.md).

Run all tests hidden and muted; the user explicitly requested no visible or audible testing on 2026-10-26. Do not launch standalone GUI Dolphin for tests; use headless runtime logging/captures saved privately.

The manual launcher uses private/playtest-user. Preserve the user's saves/settings there; automated tests must use fresh private/runs folders.
