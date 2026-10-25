# Wario World Recomp

Read README.md, docs/HANDOFF.md, docs/PROGRESS.md and docs/TIMING.md before work.
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
game-derived generated code, native game modules, saves or captures.
Keep those under ignored directories. Use scripts/check_public_tree.py before staging.
Never force-add ignored files. Public scripts must accept a user-supplied disc.
Do not silently substitute an interpreter/JIT and call it a complete static recomp.
No subagents are authorized by this file.
