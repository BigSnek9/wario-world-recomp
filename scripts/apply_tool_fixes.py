"""Apply narrowly scoped, idempotent fixes to pinned upstream tool sources."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace(path, old, new):
    text = path.read_text(encoding="utf-8")
    if new in text:
        return
    if text.count(old) != 1:
        raise RuntimeError(f"Unexpected source revision in {path}: preimage not unique")
    path.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


def fix_rel(repo):
    # Empty sections retain address zero in OSLink; relocation addends still apply.
    replace(repo / "src/frontend/container/rel.c",
            "    const RELSection* section = &rel->sections[section_index];\n    if (section->size == 0 || offset > section->size) {",
            "    const RELSection* section = &rel->sections[section_index];\n"
            "    if (section->size == 0 && section->offset == 0) {\n"
            "        *out = offset; /* OSLink leaves empty section addresses at zero. */\n"
            "        return 1;\n    }\n"
            "    if (section->size == 0 || offset > section->size) {")
    test = '''static int test_empty_section_addend(void) {
    const char* path = "test_empty_section.rel";
    CHECK(write_sample_rel(path, 1, R_PPC_ADDR32, 0, 0x1B78u, 8),
          "failed to write empty-section sample");
    RELFile rel;
    CHECK(rel_load(&rel, path, 0x80500000u), "empty-section addend rejected");
    CHECK(read_be32(rel.sections[1].data) == 0x1B78u,
          "empty section must contribute zero to the relocation");
    rel_free(&rel);
    remove(path);
    return 1;
}

'''
    tests = repo / "tests/test_rel.c"
    replace(tests, "static int test_dol_rel24_relocation(void) {", test + "static int test_dol_rel24_relocation(void) {")
    replace(tests, "    ok &= test_self_relocation();", "    ok &= test_self_relocation();\n    ok &= test_empty_section_addend();")


def fix_windows_test(repo):
    tests = repo / "tests/test_disc_extract.c"
    helper = '''#ifdef _WIN32
static char* quote_spawn_arg(const char* arg) {
    size_t len = strlen(arg), w = 0, slashes = 0;
    char* out = (char*)malloc(len * 2 + 3);
    if (!out) return NULL;
    out[w++] = '"';
    for (size_t i = 0; ; ++i) {
        char c = arg[i];
        if (c == '\\\\') { ++slashes; continue; }
        size_t n = (c == '"' || c == '\\0') ? slashes * 2 : slashes;
        while (n--) out[w++] = '\\\\';
        slashes = 0;
        if (c == '\\0') break;
        if (c == '"') out[w++] = '\\\\';
        out[w++] = c;
    }
    out[w++] = '"';
    out[w] = '\\0';
    return out;
}
#endif

'''
    replace(tests, "static int run_extract_native(const char* extractor, const char* image,", helper + "static int run_extract_native(const char* extractor, const char* image,")
    replace(tests, '''    const char* args[] = {
        extractor, "extract", "--native-only", image, out_dir, NULL
    };
    return _spawnv(_P_WAIT, extractor, args) == 0;''', '''    char* qexe = quote_spawn_arg(extractor);
    char* qimage = quote_spawn_arg(image);
    char* qout = quote_spawn_arg(out_dir);
    if (!qexe || !qimage || !qout) {
        free(qexe); free(qimage); free(qout);
        return 0;
    }
    const char* args[] = {qexe, "extract", "--native-only", qimage, qout, NULL};
    int ok = _spawnv(_P_WAIT, extractor, args) == 0;
    free(qexe); free(qimage); free(qout);
    return ok;''')
    replace(tests, '''    const char* args[] = {
        extractor, "extract", "--info", image, NULL
    };
    return _spawnv(_P_WAIT, extractor, args) == 0;''', '''    char* qexe = quote_spawn_arg(extractor);
    char* qimage = quote_spawn_arg(image);
    if (!qexe || !qimage) {
        free(qexe); free(qimage);
        return 0;
    }
    const char* args[] = {qexe, "extract", "--info", qimage, NULL};
    int ok = _spawnv(_P_WAIT, extractor, args) == 0;
    free(qexe); free(qimage);
    return ok;''')


def fix_silent_headless(runtime):
    # Invisible native surface preserves real GPU rendering for silent diagnostics.
    replace(runtime / 'vendor/dolphin/Source/Core/DolphinNoGUI/Platform.h',
            '  static std::unique_ptr<Platform> CreateWin32Platform();',
            '  static std::unique_ptr<Platform> CreateWin32Platform(bool hidden = false);')
    replace(runtime / 'vendor/dolphin/Source/Core/DolphinNoGUI/PlatformWin32.cpp',
            'public:\n  ~PlatformWin32() override;',
            'public:\n  explicit PlatformWin32(bool hidden) : m_hidden(hidden) {}\n  ~PlatformWin32() override;')
    replace(runtime / 'vendor/dolphin/Source/Core/DolphinNoGUI/PlatformWin32.cpp',
            '  static bool RegisterRenderWindowClass();',
            '  static bool RegisterRenderWindowClass(bool hidden);')
    replace(runtime / 'vendor/dolphin/Source/Core/DolphinNoGUI/PlatformWin32.cpp',
            '  HWND m_hwnd{};',
            '  const bool m_hidden;\n  HWND m_hwnd{};')
    replace(runtime / 'vendor/dolphin/Source/Core/DolphinNoGUI/PlatformWin32.cpp',
            'bool PlatformWin32::RegisterRenderWindowClass()',
            'bool PlatformWin32::RegisterRenderWindowClass(bool hidden)')
    replace(runtime / 'vendor/dolphin/Source/Core/DolphinNoGUI/PlatformWin32.cpp',
            '    MessageBox(nullptr, _T("Window registration failed."), _T("Error"), MB_ICONERROR | MB_OK);',
            '    if (!hidden)\n      MessageBox(nullptr, _T("Window registration failed."), _T("Error"), MB_ICONERROR | MB_OK);')
    replace(runtime / 'vendor/dolphin/Source/Core/DolphinNoGUI/PlatformWin32.cpp',
            '  m_hwnd = CreateWindowEx(WS_EX_CLIENTEDGE, WINDOW_CLASS_NAME, _T("Dolphin"), WS_OVERLAPPEDWINDOW,',
            '  m_hwnd = CreateWindowEx(WS_EX_CLIENTEDGE | (m_hidden ? WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE : 0), WINDOW_CLASS_NAME, _T("Dolphin"), WS_OVERLAPPEDWINDOW,')
    replace(runtime / 'vendor/dolphin/Source/Core/DolphinNoGUI/PlatformWin32.cpp',
            '    MessageBox(nullptr, _T("CreateWindowEx failed."), _T("Error"), MB_ICONERROR | MB_OK);',
            '    if (!m_hidden)\n      MessageBox(nullptr, _T("CreateWindowEx failed."), _T("Error"), MB_ICONERROR | MB_OK);')
    replace(runtime / 'vendor/dolphin/Source/Core/DolphinNoGUI/PlatformWin32.cpp',
            '  ShowWindow(m_hwnd, SW_SHOW);\n  UpdateWindow(m_hwnd);',
            '  if (!m_hidden)\n  {\n    ShowWindow(m_hwnd, SW_SHOW);\n    UpdateWindow(m_hwnd);\n  }')
    replace(runtime / 'vendor/dolphin/Source/Core/DolphinNoGUI/PlatformWin32.cpp',
            '  if (!RegisterRenderWindowClass() || !CreateRenderWindow() || !CreateMenus())',
            '  if (!RegisterRenderWindowClass(m_hidden) || !CreateRenderWindow() || (!m_hidden && !CreateMenus()))')
    replace(runtime / 'vendor/dolphin/Source/Core/DolphinNoGUI/PlatformWin32.cpp',
            '  if (Config::Get(Config::MAIN_FULLSCREEN))',
            '  if (!m_hidden && Config::Get(Config::MAIN_FULLSCREEN))')
    replace(runtime / 'vendor/dolphin/Source/Core/DolphinNoGUI/PlatformWin32.cpp',
            '  if (Config::Get(Config::MAIN_DISABLE_SCREENSAVER))',
            '  if (!m_hidden && Config::Get(Config::MAIN_DISABLE_SCREENSAVER))')
    replace(runtime / 'vendor/dolphin/Source/Core/DolphinNoGUI/PlatformWin32.cpp',
            'std::unique_ptr<Platform> Platform::CreateWin32Platform()\n{\n  return std::make_unique<PlatformWin32>();',
            'std::unique_ptr<Platform> Platform::CreateWin32Platform(bool hidden)\n{\n  return std::make_unique<PlatformWin32>(hidden);')
    replace(runtime / 'src/runtime/dolphin_runtime.cpp',
            '#include "Common/HookableEvent.h"',
            '#include "Common/HookableEvent.h"\n#include "Common/MsgHandler.h"')
    replace(runtime / 'src/runtime/dolphin_runtime.cpp',
            '  if (impl->config.headless)\n    impl->platform = Platform::CreateHeadlessPlatform();',
            '  if (impl->config.headless)\n  {\n    // Windows OpenGL needs an HWND even when no window is shown.\n#ifdef _WIN32\n    if (!impl->config.graphics.backend.empty() && impl->config.graphics.backend != "Null")\n      impl->platform = Platform::CreateWin32Platform(true);\n    else\n#endif\n      impl->platform = Platform::CreateHeadlessPlatform();\n    Common::RegisterMsgAlertHandler([](const char* caption, const char* text, bool, Common::MsgType style) {\n      std::fprintf(stderr, "[headless-alert] %s: %s\\n", caption, text);\n      std::fflush(stderr);\n      if (style == Common::MsgType::Warning || style == Common::MsgType::Critical)\n        std::_Exit(EXIT_FAILURE);\n      return false;\n    });\n  }')


def fix_diagnostic_coverage(runtime):
    core = runtime / "vendor/dolphin/Source/Core/Core/PowerPC/StaticRecomp"
    replace(core / 'StaticRecompLockstep.h',
            '  std::unordered_set<u32> m_ls_checked;    // entry PCs already checked (dedupe)',
            '  std::unordered_map<u32, u64> m_ls_checked;  // PC -> code-mapping generation\n  u64 m_ls_entry_generation = 0;')
    replace(core / 'StaticRecompLockstep.cpp',
            '  return m_ls_nodedup || address == m_ls_repeat_pc ||\n         m_ls_checked.find(address) == m_ls_checked.end();',
            '  const auto checked = m_ls_checked.find(address);\n  return m_ls_nodedup || address == m_ls_repeat_pc ||\n         checked == m_ls_checked.end() || checked->second != m_core.m_rel_mapping_generation;')
    replace(core / 'StaticRecompLockstep.cpp',
            '  m_ls_entry = guest.pc;',
            '  m_ls_entry = guest.pc;\n  m_ls_entry_generation = m_core.m_rel_mapping_generation;')
    replace(core / 'StaticRecompLockstep.cpp',
            '  m_ls_checked.insert(m_ls_entry);',
            '  m_ls_checked[m_ls_entry] = m_ls_entry_generation;')
    replace(core / 'StaticRecompCore.cpp',
            '  std::fill(m_chunk_state.begin(), m_chunk_state.end(), u8{CHUNK_UNVERIFIED});',
            '  ++m_rel_mapping_generation;  // State/cache restoration requires fresh differential coverage.\n  std::fill(m_chunk_state.begin(), m_chunk_state.end(), u8{CHUNK_UNVERIFIED});')
    replace(core / 'StaticRecompCore.h',
            '  u64 m_hook_fallback_instructions = 0;',
            '  u64 m_hook_fallback_instructions = 0;\n  u64 m_hook_cache_fastpath_instructions = 0;\n  u64 m_hook_interpreter_instructions = 0;')
    replace(core / 'StaticRecompCore_Hooks.cpp',
            "      // These bypass SingleStepInner, so charge Dolphin's PPCTables cost",
            "      ++core->m_hook_cache_fastpath_instructions;\n      // These bypass SingleStepInner, so charge Dolphin's PPCTables cost")
    replace(core / 'StaticRecompCore_Hooks.cpp',
            '  ppc.downcount -= system.GetInterpreter().SingleStepInner();',
            '  ++core->m_hook_interpreter_instructions;\n  ppc.downcount -= system.GetInterpreter().SingleStepInner();')
    replace(core / 'StaticRecompCore.cpp',
            '"[staticrecomp] shutdown: native=%llu fallback=%llu native_exc=%llu hook_fb=%llu "',
            '"[staticrecomp] shutdown: native=%llu fallback=%llu native_exc=%llu hook_fb=%llu hook_cache=%llu hook_interp=%llu "')
    replace(core / 'StaticRecompCore.cpp',
            '               (unsigned long long)m_hook_fallback_instructions, m_failed_chunks,',
            '               (unsigned long long)m_hook_fallback_instructions,\n               (unsigned long long)m_hook_cache_fastpath_instructions,\n               (unsigned long long)m_hook_interpreter_instructions, m_failed_chunks,')


def main():
    fix_rel(ROOT / "third_party/DolRecomp")
    fix_windows_test(ROOT / "third_party/DolRecomp")
    runtime = ROOT / "third_party/ModernGekko"
    fix_silent_headless(runtime)
    fix_diagnostic_coverage(runtime)
    import tool_fix_mod_dispatch
    tool_fix_mod_dispatch.apply(replace, runtime)
    import tool_fix_texture_dump
    tool_fix_texture_dump.apply(replace, runtime)
    import tool_fix_volume_command
    tool_fix_volume_command.apply(replace, runtime)
    # Its bundled compiler is a separate pin; only fix code with a matching preimage.
    nested = runtime / "vendor/dolphin/DolRecomp"
    if "section->size == 0 || offset > section->size" in (nested / "src/frontend/container/rel.c").read_text():
        fix_rel(nested)
    replace(runtime / "CMakeLists.txt",
            "    add_custom_target(moderngekko-port-recompiler ALL\n        COMMAND ${CMAKE_COMMAND} -E copy_if_different",
            "    add_custom_target(moderngekko-port-recompiler ALL\n"
            "        COMMAND ${CMAKE_COMMAND} -E make_directory\n"
            "                \"$<TARGET_FILE_DIR:moderngekko-port>\"\n"
            "        COMMAND ${CMAKE_COMMAND} -E copy_if_different")
    replace(runtime / "vendor/dolphin/Externals/libspng/CMakeLists.txt",
            "add_library(spng::spng ALIAS spng_static)",
            "add_library(spng::spng ALIAS spng_static)\n"
            "if(MSVC)\n  target_compile_options(spng_static PRIVATE /wd4706)\nendif()")
    assembler = runtime / "vendor/dolphin/Source/Core/Common/Assembler/GekkoIRGen.cpp"
    for capture in (
        "[this, sym, absolute, source_address, err_on_fail = std::move(err_on_fail)]",
        "[this, num, source_address, search_start_idx, err_on_fail = std::move(err_on_fail)]",
    ):
        replace(assembler, capture + " mutable {", capture + "() mutable {")
    replace(runtime / "vendor/dolphin/Source/Core/Common/FileSearch.cpp",
            "#elifdef ANDROID", "#elif defined(ANDROID)")
    sockets = runtime / "vendor/dolphin/Source/Core/Core/HW/DVD/AMMediaboardSocket.cpp"
    replace(sockets, "  u32 count = std::size(s_sockets);",
            "  u32 count = static_cast<u32>(std::size(s_sockets));")
    replace(sockets, "  nfds = std::min<u32>(nfds, std::size(s_sockets));",
            "  nfds = std::min<u32>(nfds, static_cast<u32>(std::size(s_sockets)));")
    lockstep = runtime / "vendor/dolphin/Source/Core/Core/PowerPC/StaticRecomp/StaticRecompLockstep_Check.cpp"
    # A native rfi/mtmsr can change translation mode. Restore the cached MSR
    # from canonical post-native state after the interpreter shadow, not entry.
    replace(lockstep, "  ppc.msr.Hex = saved_msr;\n  power_pc.MSRUpdated();",
            "  StaticRecompCore::SetPPCStateFromGuestState(m_core.m_guest, ppc);\n"
            "  ppc.msr.Hex = m_core.m_guest.msr;\n  power_pc.MSRUpdated();")
    saved_declaration = "  const u64 saved_msr = ppc.msr.Hex;\n"
    lockstep_text = lockstep.read_text(encoding="utf-8")
    if saved_declaration in lockstep_text:
        if lockstep_text.count(saved_declaration) != 1:
            raise RuntimeError("Unexpected saved-MSR declaration count")
        lockstep.write_text(lockstep_text.replace(saved_declaration, ""), encoding="utf-8", newline="\n")
    replace(lockstep, "bool LsIsLoopHeader(const u8* ram, u32 ram_size, u32 end_pc)",
            "bool LsEndCanRepeat(const u8* ram, u32 ram_size, u32 entry_pc, u32 end_pc)")
    replace(lockstep, "  const u32 start_off = end_pc - kBase;",
            "  const u32 start_off = end_pc - kBase;\n"
            "  const u32 loop_floor = entry_pc < end_pc ? entry_pc : end_pc;")
    replace(lockstep, "    if (addr <= end_pc)\n      continue;",
            "    if (addr <= end_pc || (insn & 1u) != 0u)\n      continue;")
    for displacement in ("bd", "li"):
        replace(lockstep, "      if (addr + static_cast<u32>(" + displacement + ") == end_pc)",
                "      const u32 target = addr + static_cast<u32>(" + displacement + ");\n"
                "      if (target >= loop_floor && target <= end_pc)")
    replace(lockstep, "LsIsLoopHeader(ram, ram_size, end_pc)",
            "LsEndCanRepeat(ram, ram_size, entry_pc, end_pc)")
    runtime_source = runtime / "src/runtime/dolphin_runtime.cpp"
    if "Core::QueueHostJob([] { Host_UpdateTitle({}); });" in runtime_source.read_text():
        replace(runtime_source, "Core::QueueHostJob([] { Host_UpdateTitle({}); });",
                "Core::QueueHostJob([](Core::System&) { Host_UpdateTitle({}); });")
    replace(runtime_source,
            "        Host_UpdateTitle({});",
            "        Core::QueueHostJob([](Core::System&) { Host_UpdateTitle({}); });")
    hooks = runtime / "vendor/dolphin/Source/Core/Core/PowerPC/StaticRecomp/StaticRecompCore_Hooks.cpp"
    replace(hooks, "#include <cstdio>", "#include <cstdio>\n#include <cstdlib>\n#include <unordered_set>")
    replace(hooks, "  ++core->m_hook_fallback_instructions;",
            "  ++core->m_hook_fallback_instructions;\n"
            "  static const bool trace_helpers = std::getenv(\"WARIO_RECOMP_TRACE_HOOK_FALLBACK\") != nullptr;\n"
            "  if (trace_helpers) {\n"
            "    static std::unordered_set<u64> seen;\n"
            "    const u64 key = (static_cast<u64>(cia) << 32) | raw;\n"
            "    if (seen.insert(key).second)\n"
            "      std::fprintf(stderr, \"[wario-helper] pc=%08x raw=%08x\\n\", cia, raw);\n"
            "  }")
    core_dir = runtime / "vendor/dolphin/Source/Core/Core/PowerPC/StaticRecomp"
    core_header = core_dir / "StaticRecompCore.h"
    header_text = core_header.read_text(encoding="utf-8")
    jit_fields = "  u64 m_jit_fallback_entries = 0;\n  std::unordered_map<u32, u64> m_jit_fallback_sites;"
    # Later REL fields split the original insertion. Detect the declaration,
    # rather than relying on that insertion remaining one contiguous string.
    if header_text.count("  u64 m_jit_fallback_entries = 0;") == 2 and jit_fields in header_text:
        header_text = header_text.replace(jit_fields + "\n", "", 1)
        core_header.write_text(header_text, encoding="utf-8", newline="\n")
    if "  u64 m_jit_fallback_entries = 0;" not in header_text:
        replace(core_header, "  u64 m_fallback_steps = 0;",
                "  u64 m_fallback_steps = 0;\n" + jit_fields)
    replace(core_dir / "StaticRecompCore_Run.cpp", "          m_fallback_jit->Run();",
            "          ++m_jit_fallback_entries;\n"
            "          if (m_collect_dispatch_samples)\n"
            "            ++m_jit_fallback_sites[ppc.pc];\n"
            "          m_fallback_jit->Run();")
    replace(core_dir / "StaticRecompCore.cpp", "  m_lockstep_verifier.reset();",
            "  std::fprintf(stderr, \"[wario-jit] fallback_entries=%llu distinct_entry_pcs=%zu\\n\",\n"
            "               static_cast<unsigned long long>(m_jit_fallback_entries),\n"
            "               m_jit_fallback_sites.size());\n"
            "  for (const auto& [pc, count] : m_jit_fallback_sites)\n"
            "    std::fprintf(stderr, \"[wario-jit] pc=%08x entries=%llu\\n\", pc,\n"
            "                 static_cast<unsigned long long>(count));\n"
            "  m_lockstep_verifier.reset();")
    compare = runtime / "vendor/dolphin/Source/Core/Core/PowerPC/Interpreter/Interpreter_FloatCompare.cpp"
    text = compare.read_text(encoding="utf-8")
    old = "ppc_state.fpscr.FPRF & ~FPCC_MASK"
    new = "ppc_state.fpscr.FPRF & ~(FPCC_MASK >> FPRF_SHIFT)"
    if new not in text:
        if text.count(old) != 2:
            raise RuntimeError("Expected exactly two reference compare helpers")
        compare.write_text(text.replace(old, new), encoding="utf-8", newline="\n")
    replace(core_dir / "StaticRecompLockstep.h", "  u32 m_ls_entry = 0;",
            "  using InstructionJournalFn = u64 (*)(int);\n"
            "  InstructionJournalFn m_instruction_journal = nullptr;\n"
            "  u64 m_native_instruction_count = 0;\n"
            "  u32 m_ls_entry = 0;")
    replace(core_dir / "StaticRecompLockstep.cpp", "  m_lockstep = true;",
            "  m_instruction_journal = reinterpret_cast<InstructionJournalFn>(\n"
            "      m_core.m_library.GetSymbolAddress(\"wario_instruction_journal\"));\n"
            "  std::fprintf(stderr, \"[lockstep] exact_instruction_count=%d\\n\", m_instruction_journal != nullptr);\n"
            "  m_lockstep = true;")
    replace(core_dir / "StaticRecompLockstep.cpp", "  m_ls_entry = guest.pc;",
            "  if (m_instruction_journal) m_instruction_journal(1);\n"
            "  m_ls_entry = guest.pc;")
    replace(core_dir / "StaticRecompLockstep.cpp", "  m_ls_journaling = false;",
            "  m_native_instruction_count = m_instruction_journal ? m_instruction_journal(0) : 0;\n"
            "  m_ls_journaling = false;")
    replace(lockstep, "    if (ppc.pc == end_pc)\n    {",
            "    if (m_instruction_journal)\n"
            "    {\n"
            "      if (static_cast<u64>(steps) >= m_native_instruction_count) break;\n"
            "      if (ppc.Exceptions != 0) break;\n"
            "      continue;\n"
            "    }\n"
            "    if (ppc.pc == end_pc)\n    {")
    replace(lockstep, "  const bool reached = (ppc.pc == end_pc && ppc.Exceptions == 0);",
            "  const bool reached = (ppc.pc == end_pc && ppc.Exceptions == 0 &&\n"
            "      (!m_instruction_journal || static_cast<u64>(steps) == m_native_instruction_count));")
    floating = runtime / "vendor/dolphin/GXRuntime/src/core/cpu_interpreter_float.c"
    text = floating.read_text(encoding="utf-8")
    begin = text.index("bool ppc_fma(CPUState* cpu,")
    end = text.index("\nf64 make_quiet(", begin)
    old = text[begin:end]
    if "FPRes product = ni_madd_msub" not in old:
        if "result = fma(a, c, addend);" not in old or "result = (f64)(f32)result;" not in old:
            raise RuntimeError("Unexpected legacy FMA helper preimage")
        new = '''bool ppc_fma(CPUState* cpu, f64 a, f64 c, f64 b, bool single,
             bool subtract, bool negative, f64* output) {
    /* Match the opcode helper: preserve pre-rounding information and NI mode. */
    FPRes product = ni_madd_msub(cpu, a, c, b, subtract, single);
    if (fp_invalid_gated(cpu, &product))
        return false;
    if (single) {
        f32 rounded = force_single(cpu, product.value);
        f32 result = (negative && !isnan(rounded)) ? -rounded : rounded;
        if (!subtract && !negative) {
            cpu->fpscr = (cpu->fpscr & ~(FPSCR_FI_BIT | FPSCR_FR_BIT)) |
                         ((product.value != (f64)rounded) ? FPSCR_FI_BIT : 0u);
        }
        set_fprf(cpu, classify_f32(result));
        *output = (f64)result;
    } else {
        f64 rounded = force_double(cpu, product.value);
        f64 result = (negative && !isnan(rounded)) ? -rounded : rounded;
        set_fprf(cpu, classify_f64(result));
        *output = result;
    }
    return true;
}
'''
        floating.write_text(text[:begin] + new + text[end:], encoding="utf-8", newline="\n")
    replace(core_dir / "StaticRecompCore.h", "  u64 m_jit_fallback_entries = 0;",
            "  using RelSymbolFn = u32 (*)(CPUState*, u32, u32, u32);\n"
            "  using RelExpectedHashFn = u64 (*)(CPUState*, u32, u32);\n"
            "  RelSymbolFn m_rel_symbol = nullptr;\n"
            "  RelExpectedHashFn m_rel_expected_hash = nullptr;\n"
            "  bool m_runtime_rel_pc = false;\n"
            "  u64 m_jit_fallback_entries = 0;")
    replace(core_dir / "StaticRecompCore.cpp", "  m_has_rel_modules = desc->num_rel_modules != 0;",
            "  m_has_rel_modules = desc->num_rel_modules != 0;\n"
            "  m_runtime_rel_pc = m_library.GetSymbolAddress(\"wario_runtime_pc_module\") != nullptr;\n"
            "  if (m_runtime_rel_pc) {\n"
            "    m_rel_symbol = reinterpret_cast<RelSymbolFn>(m_library.GetSymbolAddress(\"wario_rel_symbol\"));\n"
            "    m_rel_expected_hash = reinterpret_cast<RelExpectedHashFn>(m_library.GetSymbolAddress(\"wario_expected_chunk_hash\"));\n"
            "    if (!m_rel_symbol || !m_rel_expected_hash) { m_module_active = false; return reject(\"incomplete Wario REL hooks\"); }\n"
            "    std::fprintf(stderr, \"[wario-rel] runtime PCs and independent relocation hashes enabled\\n\");\n"
            "  }")
    smc = core_dir / "StaticRecompCore_SMC.cpp"
    # Discovery reuses a member scratch vector (see tool_fix_rel_scratch.py):
    # this runs after every REL dispatch in runtime-PC mode.
    replace(smc, "  std::vector<ActiveRelSection> discovered;\n  for (u32 module_index",
            "  std::vector<ActiveRelSection>& discovered = m_rel_discovery_scratch;\n"
            "  discovered.clear();\n"
            "  if (m_runtime_rel_pc) {\n"
            "    for (u32 mi=0; mi<m_module->num_rel_modules; ++mi) {\n"
            "      const auto& module = m_module->rel_modules[mi];\n"
            "      for (u32 si=0; si<module.num_sections; ++si) {\n"
            "        const auto& section = module.sections[si];\n"
            "        const u32 runtime = m_rel_symbol(&m_guest, module.module_id, section.section_index, 0);\n"
            "        if (runtime) discovered.push_back({module.module_id, section.section_index, section.linked_start, runtime, section.size});\n"
            "      }\n"
            "    }\n"
            "  } else\n"
            "  for (u32 module_index")
    replace(smc, "  if (resolve_active())\n    return true;",
            "  if (resolve_active()) {\n"
            "    if (m_runtime_rel_pc) { RefreshRelSections(); return resolve_active(); }\n"
            "    return true;\n"
            "  }")
    replace(smc, "u32 StaticRecompCore::TranslateRelAddress(u32 linked_address)\n{",
            "u32 StaticRecompCore::TranslateRelAddress(u32 linked_address)\n{\n"
            "  if (m_runtime_rel_pc) return linked_address; // Actual architectural addresses already.")
    replace(smc, "  if (m_effective_chunk_hashes[index] == 0)\n    m_effective_chunk_hashes[index] = hash;",
            "  if (m_runtime_rel_pc && m_chunk_rel_sections[index] >= 0) {\n"
            "    m_effective_chunk_hashes[index] = m_rel_expected_hash(&m_guest, chunk.start, chunk.end);\n"
            "    if (!m_effective_chunk_hashes[index]) {\n"
            "      m_chunk_state[index] = CHUNK_FAILED; ++m_failed_chunks;\n"
            "      std::fprintf(stderr, \"[wario-rel] independent expected hash unavailable for %08x\\n\", chunk.start);\n"
            "      return;\n"
            "    }\n"
            "  }\n"
            "  if (m_effective_chunk_hashes[index] == 0)\n    m_effective_chunk_hashes[index] = hash;")
    replace(core_dir / "StaticRecompCore_Run.cpp", "          m_guest.pc = linked_dispatch_address;",
            "          if (!m_runtime_rel_pc) m_guest.pc = linked_dispatch_address;")
    replace(smc, "int StaticRecompCore::GetAddressLookupIndex(u32 address) const\n{",
            "int StaticRecompCore::GetAddressLookupIndex(u32 address) const\n{\n"
            "  if (m_runtime_rel_pc && address < m_lookup_ram_size) return static_cast<int>(address >> 2);")
    replace(smc, "  const int direct_index = GetAddressLookupIndex(runtime_address);",
            "  if (m_runtime_rel_pc && runtime_address < 0x80000000u) {\n"
            "    bool covered = false;\n"
            "    for (u32 i=0; i<m_module->num_code_ranges; ++i) {\n"
            "      const auto& range=m_module->code_ranges[i];\n"
            "      if (runtime_address >= range.start && runtime_address < range.end) { covered=true; break; }\n"
            "    }\n"
            "    if (!covered) return false;\n"
            "  }\n"
            "  const int direct_index = GetAddressLookupIndex(runtime_address);")
    replace(smc, "  *runtime_address = linked_address;\n  return true;",
            "  *runtime_address = m_runtime_rel_pc && linked_address < m_guest.ram_size ?\n"
            "      linked_address | 0x80000000u : linked_address;\n  return true;")
    replace(lockstep, "  ++m_ls_checks;",
            "  ++m_ls_checks;\n"
            "  if (m_ls_trace_pc != 0 && entry_pc == m_ls_trace_pc)\n"
            "    std::fprintf(stderr, \"[ls-trace] BEGIN entry=%08x end=%08x instructions=%llu entry_msr=%08x native_msr=%08x\\n\",\n"
            "                 entry_pc, end_pc, static_cast<unsigned long long>(m_native_instruction_count), entry_state.msr, m_core.m_guest.msr);")
    replace(core_dir / "StaticRecompLockstep.cpp", "  LockstepCheck(m_ls_entry, guest.pc, m_ls_snapshot);",
            "  static const bool trace_checks = std::getenv(\"WARIO_LS_CHECK_TRACE\") != nullptr;\n"
            "  if (trace_checks) { std::fprintf(stderr, \"[wario-check] BEGIN entry=%08x end=%08x instructions=%llu helper=%d\\n\", m_ls_entry, guest.pc, static_cast<unsigned long long>(m_native_instruction_count), m_ls_fallback_seen); std::fflush(stderr); }\n"
            "  LockstepCheck(m_ls_entry, guest.pc, m_ls_snapshot);\n"
            "  if (trace_checks) { std::fprintf(stderr, \"[wario-check] END entry=%08x\\n\", m_ls_entry); std::fflush(stderr); }")
    # Query foreground ownership at the point of use, including CPU-thread input polls.
    # GetFocus() is thread-local; the old cached flag was never updated on Win32.
    platform_dir = ROOT / "third_party/ModernGekko/vendor/dolphin/Source/Core/DolphinNoGUI"
    replace(platform_dir / "Platform.h",
            "  bool IsWindowFocused() const { return m_window_focus; }",
            "  virtual bool IsWindowFocused() const { return m_window_focus; }")
    replace(platform_dir / "PlatformWin32.cpp",
            "  bool Init() override;",
            "  bool IsWindowFocused() const override\n"
            "  {\n"
            "    return !m_hidden && m_hwnd != nullptr && GetForegroundWindow() == m_hwnd && !IsIconic(m_hwnd);\n"
            "  }\n\n"
            "  bool Init() override;")
    import tool_fix_rel_scratch
    tool_fix_rel_scratch.apply(replace, core_dir)
    print("Tool fixes applied. Original game bytes were not changed.")


if __name__ == "__main__":
    main()
