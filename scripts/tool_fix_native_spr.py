"""Native mtspr/mfspr for system registers (2026-10-26, accuracy item A003).

DolRecomp emits only a few SPRs inline (XER, LR, CTR, SRR0/1, EAR, GQRs,
HID2, TBL/TBU); every other mtspr/mfspr calls ppc_fallback_instruction, which
the core ran through Dolphin's interpreter (SyncOut, SingleStepInner, SyncIn).
In Wario World those are SPRG0-3, HID0, L2CR, DEC, WPAR and the BATs (A003).

This adds a native path in HookInstructionFallback for supervisor-mode
mtspr/mfspr of a fixed SPR list whose HookSPRRead/HookSPRWrite semantics equal
Interpreter::mfspr/mtspr (same Dolphin side-effect calls). The surroundings
are kept identical to the interpreter path - full SyncOut before and SyncIn
after - and only SingleStepInner is replaced by the native register operation
plus the PPCTables cost (mfspr 1, mtspr 2). A lighter variant that skipped the
full sync failed in early boot (stale segment/MMU state -> unresolvable fetch
at 0x8019FD9C), so the sync stays; these are ~0.1% of instructions.
Anything else (user mode, other SPRs) keeps the interpreter path.
Verified 2026-10-26: hook_interp=0 on boot->hub and Greenhorn routes; check
mode 0 mismatches over ~400k instructions; full regression suite passes.

WARIO_SPR_CHECK=1 runs both paths per instruction (native on a snapshot, then
the interpreter for real) and logs any difference in GPR result, SPR array,
pending exceptions, downcount or timebase as "[wario-spr] MISMATCH".
New counter hook_spr: hook_fb = hook_cache + hook_spr + hook_interp.
"""

HEADER_OLD = "  u64 m_hook_interpreter_instructions = 0;\n"
HEADER_NEW = ("  u64 m_hook_interpreter_instructions = 0;\n"
              "  u64 m_hook_native_spr_instructions = 0;  // supervisor mtspr/mfspr handled natively\n"
              "  u64 m_spr_check_mismatches = 0;\n")

PRINT_OLD = ('"[staticrecomp] shutdown: native=%llu fallback=%llu native_exc=%llu hook_fb=%llu hook_cache=%llu hook_interp=%llu "\n'
             '               "smc_failed=%u verifications=%llu reverify_events=%llu bursts=%llu cycles=%llu\\n",')
PRINT_NEW = ('"[staticrecomp] shutdown: native=%llu fallback=%llu native_exc=%llu hook_fb=%llu hook_cache=%llu hook_interp=%llu "\n'
             '               "smc_failed=%u verifications=%llu reverify_events=%llu bursts=%llu cycles=%llu hook_spr=%llu spr_check_mismatches=%llu\\n",')

ARGS_OLD = ("               (unsigned long long)m_bursts, (unsigned long long)m_charged_cycles);\n"
            "  std::vector<std::pair<u32, u64>> dispatch_samples(")
ARGS_NEW = ("               (unsigned long long)m_bursts, (unsigned long long)m_charged_cycles,\n"
            "               (unsigned long long)m_hook_native_spr_instructions,\n"
            "               (unsigned long long)m_spr_check_mismatches);\n"
            "  std::vector<std::pair<u32, u64>> dispatch_samples(")

HOOK_OLD = """  // The recompiled segment resumes via the dispatcher at the PC this leaves
  // behind, so this must execute exactly the instruction at cia via
  // Dolphin's interpreter and hand the register state back.
  core->SyncOut();"""

HOOK_NEW = """  // Native supervisor mtspr/mfspr (scripts/tool_fix_native_spr.py). Only SPRs
  // whose HookSPRRead/HookSPRWrite match Interpreter::mfspr/mtspr exactly.
  if ((raw >> 26) == 31u && (cpu->msr & 0x4000u) == 0)
  {
    const u32 xo = (raw >> 1) & 0x3FFu;
    const u32 spr = ((raw >> 16) & 0x1Fu) | ((raw >> 6) & 0x3E0u);
    const bool native_spr =
        spr == SPR_DEC || spr == SPR_SDR || (spr >= SPR_SPRG0 && spr <= SPR_SPRG3) ||
        (spr >= SPR_IBAT0U && spr <= SPR_DBAT3L) || (spr >= SPR_IBAT4U && spr <= SPR_DBAT7L) ||
        spr == SPR_WPAR || spr == SPR_DMAU || spr == SPR_DMAL || (spr >= 952u && spr <= 959u) ||
        spr == SPR_HID0 || spr == SPR_HID1 || spr == SPR_HID4 || spr == SPR_IABR ||
        spr == SPR_L2CR || spr == SPR_ICTC || (spr >= SPR_THRM1 && spr <= SPR_THRM3);
    if ((xo == 339u || xo == 467u) && native_spr)
    {
      const u32 reg = (raw >> 21) & 31u;
      // Same surroundings as the interpreter path (full SyncOut/SyncIn keep MSR,
      // segment registers, timebase and MMU state exactly as before); only the
      // SingleStepInner step is replaced by the native register operation.
      const auto run_native = [&] {
        core->SyncOut();
        if (xo == 339u)
          ppc.gpr[reg] = HookSPRRead(cpu, static_cast<u16>(spr), cia);
        else
          HookSPRWrite(cpu, static_cast<u16>(spr), ppc.gpr[reg], cia);
        ppc.downcount -= (xo == 339u) ? 1 : 2;  // PPCTables: mfspr 1, mtspr 2
        ppc.pc = cia + 4u;
        ppc.npc = cia + 4u;
        core->SyncIn();
      };
      static const bool check = std::getenv("WARIO_SPR_CHECK") != nullptr;
      if (!check)
      {
        run_native();
        ++core->m_hook_native_spr_instructions;
        return;
      }
      // Differential check: native on a snapshot, then the interpreter for real.
      const CPUState guest_before = *cpu;
      u32 spr_before[1024];
      std::memcpy(spr_before, ppc.spr, sizeof(spr_before));
      const int downcount_before = ppc.downcount;
      const u32 exceptions_before = ppc.Exceptions;
      const u64 remainder_before = core->m_timebase_cycle_remainder;
      run_native();
      const CPUState guest_native = *cpu;
      u32 spr_native[1024];
      std::memcpy(spr_native, ppc.spr, sizeof(spr_native));
      const int downcount_native = ppc.downcount;
      const u32 exceptions_native = ppc.Exceptions;
      *cpu = guest_before;
      std::memcpy(ppc.spr, spr_before, sizeof(spr_before));
      ppc.downcount = downcount_before;
      ppc.Exceptions = exceptions_before;
      core->m_timebase_cycle_remainder = remainder_before;
      core->SyncOut();
      ppc.pc = cia;
      ppc.npc = cia + 4;
      ++core->m_hook_interpreter_instructions;
      ppc.downcount -= system.GetInterpreter().SingleStepInner();
      core->SyncIn();
      // SyncOut re-mirrors registers that native code owns in CPUState (LR, CTR,
      // XER, SRR0/1, DAR, DSISR, EAR, HID2, GQRs) into ppc.spr; those slots are
      // stale caches on the native path and are not compared.
      const auto mirrored = [](u32 index) {
        return index == SPR_XER || index == SPR_LR || index == SPR_CTR || index == SPR_SRR0 ||
               index == SPR_SRR1 || index == SPR_DAR || index == SPR_DSISR || index == SPR_EAR ||
               index == SPR_HID2 || (index >= SPR_GQR0 && index < SPR_GQR0 + 8);
      };
      u32 first_diff = 0xFFFFFFFFu;
      for (u32 index = 0; index < 1024 && first_diff == 0xFFFFFFFFu; ++index)
        if (!mirrored(index) && ppc.spr[index] != spr_native[index])
          first_diff = index;
      const bool same = cpu->gpr[reg] == guest_native.gpr[reg] && cpu->pc == guest_native.pc &&
                        cpu->timebase == guest_native.timebase && first_diff == 0xFFFFFFFFu &&
                        ppc.downcount == downcount_native && ppc.Exceptions == exceptions_native;
      if (!same)
      {
        ++core->m_spr_check_mismatches;
        std::fprintf(stderr,
                     "[wario-spr] MISMATCH pc=%08x raw=%08x spr=%u gpr %08x/%08x pc %08x/%08x "
                     "tb %llx/%llx dc %d/%d exc %x/%x spr_diff=%u\\n",
                     cia, raw, spr, cpu->gpr[reg], guest_native.gpr[reg], cpu->pc, guest_native.pc,
                     (unsigned long long)cpu->timebase, (unsigned long long)guest_native.timebase,
                     ppc.downcount, downcount_native, ppc.Exceptions, exceptions_native, first_diff);
      }
      return;
    }
  }

  // The recompiled segment resumes via the dispatcher at the PC this leaves
  // behind, so this must execute exactly the instruction at cia via
  // Dolphin's interpreter and hand the register state back.
  core->SyncOut();"""


INCLUDE_OLD = "#include <cstdio>\n#include <cstdlib>\n"
INCLUDE_NEW = "#include <cstdio>\n#include <cstdlib>\n#include <cstring>\n#include \"Core/CoreTiming.h\"\n"


def apply(replace, core_dir):
    replace(core_dir / "StaticRecompCore_Hooks.cpp", INCLUDE_OLD, INCLUDE_NEW)
    replace(core_dir / "StaticRecompCore.h", HEADER_OLD, HEADER_NEW)
    replace(core_dir / "StaticRecompCore.cpp", PRINT_OLD, PRINT_NEW)
    replace(core_dir / "StaticRecompCore.cpp", ARGS_OLD, ARGS_NEW)
    replace(core_dir / "StaticRecompCore_Hooks.cpp", HOOK_OLD, HOOK_NEW)
