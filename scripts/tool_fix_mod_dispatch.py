"""ModManager no-interception fast path (2026-10-26).

StaticRecompCore calls ModManager::HostCall (Dispatch) and HostCallContains
(HandlesAddress) on native dispatches. With no mods loaded (--no-mods, and every
automated test) each call still performs several unordered_map lookups. The
sampling profiler showed these near the top of the emulation thread during the
dispatch-heavy title sequence (boot speed dip ~15 s after launch).

The early returns below are taken only when there are no patches, hooks or
pending returns, in which case the original code's lookups all miss and it
returns false - behaviour is identical. Dispatch still fires the one-time
runtime_start event first.
"""

DISPATCH_OLD = """  if (!m_impl->runtime_started) {
    m_impl->runtime_started = true;
    TriggerEvent("*", "runtime_start", state);
  }
  if (!m_impl->pending_returns.empty() &&"""

DISPATCH_NEW = """  if (!m_impl->runtime_started) {
    m_impl->runtime_started = true;
    TriggerEvent("*", "runtime_start", state);
  }
  // No interceptions: every lookup below would miss (identical result).
  if (m_impl->patches.empty() && m_impl->hooks.empty() &&
      m_impl->pending_returns.empty())
    return false;
  if (!m_impl->pending_returns.empty() &&"""

HANDLES_OLD = """bool ModManager::HandlesAddress(std::uint32_t address) const {
  if (m_impl->patches.contains(address) || m_impl->hooks.contains(address))"""

HANDLES_NEW = """bool ModManager::HandlesAddress(std::uint32_t address) const {
  if (m_impl->patches.empty() && m_impl->hooks.empty() &&
      m_impl->pending_returns.empty())
    return false;
  if (m_impl->patches.contains(address) || m_impl->hooks.contains(address))"""


# Generated code calls ctx->host_call on every dolrecomp_call (cross-chunk,
# indirect and REL-bridge calls) and the core checks host_call_contains on
# every dispatch. Mods are only loaded once, before this wiring
# (LoadDirectories is the sole loader), so with none loaded no hook, patch or
# event callback can ever exist. Leave host_call null in that case.
WIRING_OLD = """  recomp_source.host_call = &ModManager::HostCall;
  recomp_source.host_call_contains = &ModManager::HostCallContains;
  recomp_source.host_call_range_contains =
      &ModManager::HostCallRangeContains;
  recomp_source.host_call_user = impl->mods.get();"""

WIRING_NEW = """  if (!impl->mods->Empty())
  {
    // No mods loaded => no interception can exist; skip the per-call hook.
    recomp_source.host_call = &ModManager::HostCall;
    recomp_source.host_call_contains = &ModManager::HostCallContains;
    recomp_source.host_call_range_contains =
        &ModManager::HostCallRangeContains;
    recomp_source.host_call_user = impl->mods.get();
  }"""


def apply(replace, runtime):
    source = runtime / "src/runtime/mod_loader.cpp"
    replace(source, DISPATCH_OLD, DISPATCH_NEW)
    replace(source, HANDLES_OLD, HANDLES_NEW)
    replace(runtime / "src/runtime/dolphin_runtime.cpp", WIRING_OLD, WIRING_NEW)
