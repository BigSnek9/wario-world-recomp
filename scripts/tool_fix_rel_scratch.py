"""RefreshRelSections allocation-free discovery (2026-10-26).

In runtime-REL-PC mode ResolveNativeAddress calls RefreshRelSections() after
every successful REL resolve. Each call built a new std::vector of discovered
sections, growing it with push_back (allocation + element moves). The sampling
profiler showed this (std::_Uninitialized_move<ActiveRelSection>) plus
ResolveNativeAddress saturating the emulation thread for ~0.5 s during the
title sequence, the boot-time speed dip.

The discovery logic is unchanged; it now fills a member scratch vector that
keeps its capacity, and swaps it in when the set changed. Same results, no
per-dispatch heap traffic.
"""

HEADER_OLD = "  std::vector<ActiveRelSection> m_active_rel_sections;\n"
HEADER_NEW = ("  std::vector<ActiveRelSection> m_active_rel_sections;\n"
              "  std::vector<ActiveRelSection> m_rel_discovery_scratch;  // reused by RefreshRelSections\n")

# The declaration change (discovered = m_rel_discovery_scratch) lives in
# apply_tool_fixes.py, whose earlier REL fix owns that block.

ASSIGN_OLD = "  m_active_rel_sections = std::move(discovered);"
ASSIGN_NEW = "  m_active_rel_sections.swap(discovered);"


def apply(replace, core_dir):
    replace(core_dir / "StaticRecompCore.h", HEADER_OLD, HEADER_NEW)
    replace(core_dir / "StaticRecompCore_SMC.cpp", ASSIGN_OLD, ASSIGN_NEW)
