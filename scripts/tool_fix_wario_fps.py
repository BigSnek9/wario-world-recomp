"""Optional Wario World frame interpolation, "120 FPS" (2026-10-26).

Off unless MODERNGEKKO_WARIO_FPS is set (launcher option, default off). The
guest still runs its fixed 59.94 Hz loop; only presentation changes, so game
logic, input and audio are untouched (docs/modding/FPS_UNLOCK.md).

How it works (video thread):
1. Every GPU command of a frame is recorded (same rule as Dolphin's FIFO
   recorder: display-list contents inline, CALL_DL itself skipped). At each
   XFB copy the GPU register state (BP/CP/XF, TMEM) is snapshotted as the
   start state of the next frame.
2. When the frame's main 3D projection is uploaded, the camera block
   ([0x801FDA50]: eye +0x14, up +0x20, target +0x2C, projection +0x54) is
   read and kept for that frame (CAM-001..004).
3. At the XFB copy of frame N, if frames N-1 and N both had the main camera
   and no cut happened, the start state is restored and frame N's commands
   are replayed with the main-camera perspective projection multiplied by
   C = LookAt(lerp(N-1, N, 0.5)) * LookAt(N)^-1 (orthographic/HUD draws and
   other projections untouched). PE finish/token interrupts and XFB copies
   are suppressed during the replay; the result is copied into a private
   texture (no guest RAM writes, nothing registered in the texture cache) and
   presented half a frame after the previous real present. The real frame N
   is then shown by the normal VI swap.
"""

OPCODE_DECL_OLD = "namespace OpcodeDecoder\n{\nbool g_record_fifo_data = false;\n"
OPCODE_DECL_NEW = ("extern bool g_wario_fps_record;\n"
                   "void WarioFpsRecordCommand(const u8* data, u32 size);\n\n"
                   "namespace OpcodeDecoder\n{\nbool g_record_fifo_data = false;\n")

OPCODE_HOOK_OLD = """        Core::System::GetInstance().GetFifoRecorder().WriteGPCommand(data, size);
      }
"""
OPCODE_HOOK_NEW = """        Core::System::GetInstance().GetFifoRecorder().WriteGPCommand(data, size);
      }
      if (g_wario_fps_record)
        WarioFpsRecordCommand(data, size);
"""

VSM_GLOBALS_OLD = "void VertexShaderManager::Init()\n{"
VSM_GLOBALS_NEW = """// Wario World frame interpolation (scripts/tool_fix_wario_fps.py).
bool g_wario_view_correction_active = false;
Common::Matrix44 g_wario_view_correction = Common::Matrix44::Identity();
float g_wario_main_projection[2] = {0.0f, 0.0f};

void VertexShaderManager::Init()
{"""

VSM_APPLY_OLD = """    corrected_matrix *= g_freelook_camera.GetView();

  g_freelook_camera.GetController()->SetClean();"""
VSM_APPLY_NEW = """    corrected_matrix *= g_freelook_camera.GetView();

  if (g_wario_view_correction_active && xfmem.projection.type == ProjectionType::Perspective &&
      std::abs(rawProjection[0] - g_wario_main_projection[0]) <=
          1e-4f * std::abs(g_wario_main_projection[0]) + 1e-6f &&
      std::abs(rawProjection[2] - g_wario_main_projection[1]) <=
          1e-4f * std::abs(g_wario_main_projection[1]) + 1e-6f)
  {
    corrected_matrix *= g_wario_view_correction;
  }

  g_freelook_camera.GetController()->SetClean();"""

TC_HEADER_OLD = "  void FlushStaleBinds();\n"
TC_HEADER_NEW = TC_HEADER_OLD + (
    "\n  // Wario World frame interpolation: the game's EFB-to-texture copies (screen feedback effects)\n"
    "  // as they were at the start of the frame and after the real frame. The replay runs with the\n"
    "  // start-of-frame textures and the real ones are put back afterwards, so the in-between frame\n"
    "  // never feeds into the next real frame.\n"
    "  void WarioSwapFrameCopies(bool to_frame_start);\n"
    "  void WarioResetFrameCopies() { m_wario_frame_copies.clear(); }\n"
    "  struct WarioCopyRecord\n"
    "  {\n"
    "    u32 address;\n"
    "    RcTcacheEntry before, after;\n"
    "  };\n"
    "  std::vector<WarioCopyRecord> m_wario_frame_copies;\n")

TC_RECORD_OLD = "  const bool is_xfb_copy = !is_depth_copy && !isIntensity && dstFormat == EFBCopyFormat::XFB;\n"
TC_RECORD_NEW = TC_RECORD_OLD + """  const bool wario_track = !is_xfb_copy && g_wario_fps_record && !g_wario_fps_replaying;
  if (wario_track && std::ranges::find(m_wario_frame_copies, dstAddr, &WarioCopyRecord::address) ==
                         m_wario_frame_copies.end())
  {
    RcTcacheEntry before;
    const auto range = m_textures_by_address.equal_range(dstAddr);
    for (auto it = range.first; it != range.second; ++it)
    {
      if (it->second->IsEfbCopy() && it->second->addr == dstAddr)
      {
        before = it->second;
        break;
      }
    }
    m_wario_frame_copies.push_back({dstAddr, std::move(before), {}});
  }
"""

TC_AFTER_OLD = """    entry->SetHashes(hash, hash);
    m_textures_by_address.emplace(dstAddr, std::move(entry));"""
TC_AFTER_NEW = """    entry->SetHashes(hash, hash);
    if (wario_track)
    {
      for (auto& record : m_wario_frame_copies)
        if (record.address == dstAddr)
          record.after = entry;
    }
    m_textures_by_address.emplace(dstAddr, std::move(entry));"""

# The frame-copy records hold cache entries; release them while the cache still exists (the
# vector member would otherwise outlive g_texture_cache and trip "Texture cache destroyed before
# TCacheEntry was destroyed" on quit).
TC_SHUTDOWN_OLD = "  // Clear pending EFB copies first, so we don't try to flush them.\n  m_pending_efb_copies.clear();\n"
TC_SHUTDOWN_NEW = TC_SHUTDOWN_OLD + "  m_wario_frame_copies.clear();\n"

TC_SWAP_OLD = "void TextureCacheBase::FlushStaleBinds()\n"
TC_SWAP_NEW = """void TextureCacheBase::WarioSwapFrameCopies(bool to_frame_start)
{
  for (auto& record : m_wario_frame_copies)
  {
    const auto range = m_textures_by_address.equal_range(record.address);
    for (auto it = range.first; it != range.second;)
    {
      if (it->second->IsEfbCopy() && it->second->addr == record.address)
        it = InvalidateTexture(it, true);
      else
        ++it;
    }
    const RcTcacheEntry& entry = to_frame_start ? record.before : record.after;
    if (entry)
    {
      entry->invalidated = false;
      m_textures_by_address.emplace(record.address, entry);
    }
  }
  for (auto& bound : m_bound_textures)
    bound.reset();
  TMEM::InvalidateAll();
}

""" + TC_SWAP_OLD

TC_EXTERN_OLD = '#include "VideoCommon/VideoConfig.h"\n'
TC_EXTERN_NEW = TC_EXTERN_OLD + "\nextern bool g_wario_fps_record;     // VideoCommon/BPStructs.cpp\nextern bool g_wario_fps_replaying;\n"

TC_GLOBALS_OLD = "void TextureCacheBase::CopyRenderTargetToTexture("
TC_GLOBALS_NEW = """// Wario World frame interpolation: copy into a private entry (no RAM, no cache registration).
bool g_wario_private_xfb_copy = false;
RcTcacheEntry g_wario_private_xfb_entry;

void TextureCacheBase::CopyRenderTargetToTexture("""

TC_CAPTURE_OLD = """      CopyEFBToCacheEntry(entry, is_depth_copy, srcRect, scaleByHalf, linear_filter, dstFormat,
                          isIntensity, gamma, clamp_top, clamp_bottom,
                          GetVRAMCopyFilterCoefficients(filter_coefficients));
"""
TC_CAPTURE_NEW = TC_CAPTURE_OLD + """      if (g_wario_private_xfb_copy)
      {
        g_wario_private_xfb_entry = std::move(entry);
        return;
      }
"""
TC_GUARD_OLD = """  RcTcacheEntry entry;
  if (copy_to_vram)
  {
    // create the texture"""
TC_GUARD_NEW = """  RcTcacheEntry entry;
  if (g_wario_private_xfb_copy && !copy_to_vram)
    return;
  if (copy_to_vram)
  {
    // create the texture"""

PRESENT_DECL_OLD = "  void ImmediateSwap(u32 xfb_addr, u32 fb_width, u32 fb_stride, u32 fb_height);\n"
PRESENT_DECL_NEW = PRESENT_DECL_OLD + (
    "  // Wario World frame interpolation: queue an in-between frame `delay_seconds` after the\n"
    "  // previous real frame (no frame count change). Returns the planned delay in ms, or -1.\n"
    "  double PresentInterpolated(RcTcacheEntry entry, u32 fb_width, u32 fb_height,\n"
    "                             double delay_seconds, double interval_seconds);\n"
    "  // Shows queued in-between / held-back real frames once due (or all now, when forced).\n"
    "  void WarioFlushPendingPresent(bool force);\n"
    "  // Earliest due time of a queued frame, if any.\n"
    "  bool WarioNextPresentDue(TimePoint* due) const;\n"
    "  struct WarioQueuedFrame\n"
    "  {\n"
    "    RcTcacheEntry entry;\n"
    "    u32 width, height;\n"
    "    TimePoint due;\n"
    "  };\n"
    "  std::vector<WarioQueuedFrame> m_wario_pending_mids;\n"
    "  RcTcacheEntry m_wario_real_entry;\n"
    "  // Frame N copied at its own XFB copy (the VI that follows still shows frame N-1).\n"
    "  void WarioSetRealCopy(RcTcacheEntry entry, u32 fb_width, u32 fb_height);\n"
    "  RcTcacheEntry m_wario_next_real;\n"
    "  MathUtil::Rectangle<int> m_wario_next_real_rect;\n"
    "  MathUtil::Rectangle<int> m_wario_real_rect;\n")

PRESENT_EXTERN_OLD = '#include "VideoCommon/Widescreen.h"\n'
PRESENT_EXTERN_NEW = PRESENT_EXTERN_OLD + (
    "\n#ifdef _WIN32\n#ifndef NOMINMAX\n#define NOMINMAX\n#endif\n#include <windows.h>\n#endif\n"
    "extern void* g_wario_hwnd;                         // DolphinNoGUI (in-game menu fix)\n"
    "extern std::atomic<int> g_wario_fps_multiplier;    // VideoCommon/BPStructs.cpp (1 = off)\n"
    "\n// Wario World frame interpolation: throttle-sleep present hooks (Core/CoreTiming.cpp).\n"
    "extern bool (*g_wario_throttle_present_due)(TimePoint* due);\n"
    "extern void (*g_wario_throttle_present_flush)();\n")

CT_GLOBALS_OLD = '#include "VideoCommon/VideoEvents.h"\n'
CT_GLOBALS_NEW = CT_GLOBALS_OLD + (
    "\n// Wario World frame interpolation (scripts/tool_fix_wario_fps.py): set by the video side in\n"
    "// single-thread mode so queued frames are shown during throttle sleeps instead of stalling.\n"
    "bool (*g_wario_throttle_present_due)(TimePoint* due) = nullptr;\n"
    "void (*g_wario_throttle_present_flush)() = nullptr;\n")

CT_SLEEP_OLD = "  UpdateVISkip(time, target_time);\n\n  SleepUntil(target_time);\n}"
CT_SLEEP_NEW = ("  UpdateVISkip(time, target_time);\n\n"
                "  TimePoint due;\n"
                "  while (g_wario_throttle_present_due && g_wario_throttle_present_due(&due) &&\n"
                "         due < target_time)\n"
                "  {\n"
                "    SleepUntil(due);\n"
                "    g_wario_throttle_present_flush();\n"
                "  }\n"
                "  SleepUntil(target_time);\n}")

PRESENT_FUNC_OLD = "void Presenter::SetNextSwapEstimatedTime(u64 ticks, TimePoint host_time)\n"
PRESENT_FUNC_NEW = """// Single-thread mode: Dolphin's speed limiter shows queued frames during its own sleep
// (Core/CoreTiming.cpp), so pacing never stalls emulation.
static bool WarioThrottlePresentDue(TimePoint* due)
{
  return g_presenter && g_presenter->WarioNextPresentDue(due);
}

static void WarioThrottlePresentFlush()
{
  if (g_presenter)
    g_presenter->WarioFlushPendingPresent(false);
}

double Presenter::PresentInterpolated(RcTcacheEntry entry, u32 fb_width, u32 fb_height,
                                      double delay_seconds, double interval_seconds)
{
  if (!entry || fb_width == 0 || fb_height == 0 || (WarioFpsDebug() & 2))
    return -1.0;
  auto& system = Core::System::GetInstance();
  if (!system.IsDualCoreMode() && !g_wario_throttle_present_due)
  {
    g_wario_throttle_present_due = WarioThrottlePresentDue;
    g_wario_throttle_present_flush = WarioThrottlePresentFlush;
  }
  s_wario_interval = std::chrono::duration_cast<DT>(std::chrono::duration<double>(interval_seconds));
  // Counted from the previous real frame (still held, or already shown), so frames the game
  // finishes early in the 16.7 ms still land evenly between two real frames. Never earlier than
  // now, and never closer than one interval to the previous in-between frame, queued or already
  // shown: in rooms where the game finishes its frame late (underground levels, ~11 ms after the
  // previous real frame) the in-between frames then start at the copy and stay evenly spaced
  // instead of the overdue ones going out back to back.
  const auto now = Clock::now();
  const TimePoint base = s_wario_pending_present ? s_wario_pending_due : s_wario_last_real_present;
  TimePoint due = base + std::chrono::duration_cast<DT>(std::chrono::duration<double>(delay_seconds));
  due = std::max(due, s_wario_last_mid_due + s_wario_interval);
  due = std::max(due, now);
  s_wario_last_mid_due = due;
  m_wario_pending_mids.push_back(
      {std::move(entry), fb_width, fb_height, (WarioFpsDebug() & 1) ? now : due});
  const double offset_ms =
      std::chrono::duration<double, std::milli>(std::max(now, due) - base).count();
  WarioFlushPendingPresent(false);
  return offset_ms;
}

void Presenter::WarioSetRealCopy(RcTcacheEntry entry, u32 fb_width, u32 fb_height)
{
  m_wario_next_real = std::move(entry);
  if (m_wario_next_real)
  {
    m_wario_next_real_rect = MathUtil::Rectangle<int>(
        0, 0,
        static_cast<int>(fb_width * m_wario_next_real->GetWidth() / m_wario_next_real->native_width),
        static_cast<int>(fb_height * m_wario_next_real->GetHeight() / m_wario_next_real->native_height));
  }
}

bool Presenter::WarioNextPresentDue(TimePoint* due) const
{
  bool any = false;
  if (!m_wario_pending_mids.empty())
  {
    *due = m_wario_pending_mids.front().due;
    any = true;
  }
  if (s_wario_pending_present && (!any || s_wario_pending_due < *due))
  {
    *due = s_wario_pending_due;
    any = true;
  }
  return any;
}

void Presenter::WarioFlushPendingPresent(bool force)
{
  if (m_wario_pending_mids.empty() && !s_wario_pending_present)
    return;  // called every 16 GPU commands: no clock read when nothing is queued
  for (;;)
  {
    const auto now = Clock::now();
    const bool mid_first =
        !m_wario_pending_mids.empty() &&
        (!s_wario_pending_present || m_wario_pending_mids.front().due < s_wario_pending_due);
    if (mid_first)
    {
      if (!force && now < m_wario_pending_mids.front().due)
        return;
      WarioQueuedFrame frame = std::move(m_wario_pending_mids.front());
      m_wario_pending_mids.erase(m_wario_pending_mids.begin());
      ReleaseXFBContentLock();
      m_xfb_entry = std::move(frame.entry);
      m_xfb_rect = MathUtil::Rectangle<int>(
          0, 0, static_cast<int>(frame.width * m_xfb_entry->GetWidth() / m_xfb_entry->native_width),
          static_cast<int>(frame.height * m_xfb_entry->GetHeight() / m_xfb_entry->native_height));
      m_xfb_entry->AcquireContentLock();
      WarioDumpPresented(m_xfb_entry, 'M');
      Present(nullptr);
      WarioTrace('M');
      s_wario_last_mid_present = Clock::now();
      WarioNotePresent();
      continue;
    }
    if (!s_wario_pending_present)
      return;
    if (!force && now < s_wario_pending_due)
      return;
    s_wario_pending_present = false;
    if (force)
      g_wario_pending_forced++;
    const double late_ms =
        std::chrono::duration<double, std::milli>(now - s_wario_pending_due).count();
    g_wario_pending_late_sum += late_ms;
    g_wario_pending_late_max = std::max(g_wario_pending_late_max, late_ms);
    g_wario_pending_count++;
    if (m_wario_real_entry)
    {
      ReleaseXFBContentLock();
      m_xfb_entry = std::move(m_wario_real_entry);
      m_wario_real_entry.reset();
      m_xfb_rect = m_wario_real_rect;
      m_xfb_entry->AcquireContentLock();
    }
    WarioDumpPresented(m_xfb_entry, 'R');
    Present(&s_wario_pending_info);
    WarioTrace('R');
    s_wario_last_real_present = Clock::now();
    WarioNotePresent();
    ProcessFrameDumping(s_wario_pending_ticks);
    GetVideoEvents().after_present_event.Trigger(s_wario_pending_info);
  }
}

void Presenter::SetNextSwapEstimatedTime(u64 ticks, TimePoint host_time)
"""

PRESENT_STATIC_OLD = "bool Presenter::FetchXFB(u32 xfb_addr,"
PRESENT_STATIC_NEW = """// Wario World frame interpolation pacing. The game issues its XFB copy late in each 16.7 ms
// frame, so in-between frames can only be built just before the next VI. They are queued at
// equal intervals after the previous real frame (never earlier than when they are ready), and
// the real frame is held back one interval after the last of them (2x: ~8 ms extra latency, 4x: ~12.5 ms, as in Ship of Harkinian's
// interpolation). Nothing sleeps: queued frames are shown from the command loop or from the
// speed limiter's own sleep once due.
// MODERNGEKKO_WARIO_FPS_DEBUG bits (diagnostics only): 1 = show in-between frames at once,
// 2 = build but do not show in-between frames, 4 = do not hold real frames, 8 = no forced VSync.
static int WarioFpsDebug()
{
  static const int bits = [] {
    const char* value = std::getenv("MODERNGEKKO_WARIO_FPS_DEBUG");
    return value ? std::atoi(value) : 0;
  }();
  return bits;
}

// MODERNGEKKO_WARIO_FPS_TRACE=<file> (diagnostics): one line per pacing event, "<kind> <ms>":
// C copy (frame end), Q in-between queued, M/R in-between/held real shown, V VI swap, H real held,
// r real shown directly at the VI.
void WarioTrace(char kind)
{
  static FILE* const file = [] {
    const char* path = std::getenv("MODERNGEKKO_WARIO_FPS_TRACE");
    return path && *path ? std::fopen(path, "w") : nullptr;
  }();
  if (!file)
    return;
  static const TimePoint start = Clock::now();
  std::fprintf(file, "%c %.3f\\n", kind,
               std::chrono::duration<double, std::milli>(Clock::now() - start).count());
}

static TimePoint s_wario_last_real_present{};
static TimePoint s_wario_last_mid_present{};
static TimePoint s_wario_last_mid_due{};  // planned time of the latest in-between frame
static DT s_wario_interval = std::chrono::duration_cast<DT>(std::chrono::duration<double>(0.5 / 59.94));
static bool s_wario_pending_present = false;
static TimePoint s_wario_pending_due{};
static u64 s_wario_pending_ticks = 0;
static PresentInfo s_wario_pending_info{};
double g_wario_pending_late_sum = 0.0, g_wario_pending_late_max = 0.0;
u64 g_wario_pending_count = 0, g_wario_pending_forced = 0;
// Gaps between consecutive presents while interpolating, relative to the target interval:
// <0.5, 0.5-0.8, 0.8-1.2 (on pace), 1.2-1.5, 1.5-1.8, >=1.8.
u64 g_wario_present_gaps[6] = {};
static TimePoint s_wario_last_any_present{};

// VSync while interpolating: with it off, frames paced by the clock drift against the display's
// refresh, so some refreshes take two new frames (one is never seen) and others none (one is shown
// twice); on moving geometry that reads as afterimages (human report on a 240 Hz screen). When
// the frame rate fits the screen (multiplier x 59.94 <= refresh + 1 Hz) VSync gives every frame
// its own refresh; otherwise, and with interpolation off, the player's own setting is kept.
// In-game menu "VSync": 0 = auto (on while interpolating within the refresh rate), 1 = off.
std::atomic<int> g_wario_vsync_mode{0};

static void WarioSyncVSync()
{
  static int refresh_hz = 0;
  static TimePoint next_check{};
  static bool forced = false;
  static bool user_vsync = false;
  const auto now = Clock::now();
  if (now >= next_check)
  {
    next_check = now + std::chrono::seconds(2);
#ifdef _WIN32
    if (g_wario_hwnd)
    {
      MONITORINFOEXW info{};
      info.cbSize = sizeof(info);
      DEVMODEW mode{};
      mode.dmSize = sizeof(mode);
      if (GetMonitorInfoW(MonitorFromWindow(static_cast<HWND>(g_wario_hwnd), MONITOR_DEFAULTTONEAREST),
                          &info) &&
          EnumDisplaySettingsW(info.szDevice, ENUM_CURRENT_SETTINGS, &mode) && mode.dmDisplayFrequency > 1)
      {
        refresh_hz = static_cast<int>(mode.dmDisplayFrequency);
      }
    }
#endif
  }
  const int multiplier = g_wario_fps_multiplier.load(std::memory_order_relaxed);
  const bool want = multiplier > 1 && refresh_hz > 0 && multiplier * 59.94 <= refresh_hz + 1.0 &&
                    !(WarioFpsDebug() & 8) && g_wario_vsync_mode.load(std::memory_order_relaxed) == 0;
  if (want && !forced)
  {
    user_vsync = Config::Get(Config::GFX_VSYNC);
    forced = true;
    if (!user_vsync)
      Config::SetCurrent(Config::GFX_VSYNC, true);
  }
  else if (!want && forced)
  {
    forced = false;
    if (!user_vsync)
      Config::SetCurrent(Config::GFX_VSYNC, false);
  }
}

// MODERNGEKKO_WARIO_FPS_PRESENT_DUMP=<dir> (diagnostics): saves the frames actually presented,
// in order, for 48 presents from present number MODERNGEKKO_WARIO_FPS_PRESENT_DUMP_AT (default
// 2400): <dir>/p_<n>_<kind>.png plus times.csv (n, kind, ms). Kinds as in WarioTrace.
static void WarioDumpPresented(const RcTcacheEntry& entry, char kind)
{
  static const char* const dir = std::getenv("MODERNGEKKO_WARIO_FPS_PRESENT_DUMP");
  if (!dir || !*dir || !entry)
    return;
  static const long long first = [] {
    const char* value = std::getenv("MODERNGEKKO_WARIO_FPS_PRESENT_DUMP_AT");
    return value ? std::strtoll(value, nullptr, 10) : 2400LL;
  }();
  static long long count = 0;
  static FILE* times = nullptr;
  static const TimePoint start = Clock::now();
  const long long n = count++;
  if (n < first || n >= first + 48)
    return;
  if (!times)
    times = std::fopen(fmt::format("{}/times.csv", dir).c_str(), "w");
  entry->texture->Save(fmt::format("{}/p_{:06}_{}.png", dir, n, kind), 0);
  if (times)
  {
    std::fprintf(times, "%lld,%c,%.3f\\n", n, kind,
                 std::chrono::duration<double, std::milli>(Clock::now() - start).count());
    std::fflush(times);
  }
}

static void WarioNotePresent()
{
  const auto now = Clock::now();
  const double gap = std::chrono::duration<double>(now - s_wario_last_any_present).count() /
                     std::chrono::duration<double>(s_wario_interval).count();
  s_wario_last_any_present = now;
  if (s_wario_last_mid_present == TimePoint{} || gap > 4.0)
    return;
  const int bucket = gap < 0.5 ? 0 : gap < 0.8 ? 1 : gap < 1.2 ? 2 : gap < 1.5 ? 3 : gap < 1.8 ? 4 : 5;
  g_wario_present_gaps[bucket]++;
}

""" + PRESENT_STATIC_OLD

PRESENT_VI_OLD = """    Present(&present_info);
    ProcessFrameDumping(ticks);
"""
PRESENT_VI_NEW = """    WarioSyncVSync();
    // The game double-buffers its XFB: this VI shows the frame copied one game frame earlier, while
    // the in-between frames just queued lead up to the frame copied last. Show that copy as the real
    // frame, otherwise every game frame steps back once (afterimages on all moving geometry).
    if (m_wario_next_real)
    {
      ReleaseXFBContentLock();
      m_xfb_entry = std::move(m_wario_next_real);
      m_wario_next_real.reset();
      m_xfb_rect = m_wario_next_real_rect;
      m_xfb_entry->AcquireContentLock();
    }
    if ((s_wario_last_mid_present > s_wario_last_real_present || !m_wario_pending_mids.empty()) &&
        !(WarioFpsDebug() & 4))
    {
      // Hold the real frame one interval after the last in-between frame (queued or shown).
      const TimePoint after = m_wario_pending_mids.empty() ? s_wario_last_mid_present :
                                                             m_wario_pending_mids.back().due;
      const auto due = after + s_wario_interval;
      const auto now = Clock::now();
      if (due > now && due - now <= std::chrono::milliseconds(17))
      {
        s_wario_pending_present = true;
        s_wario_pending_due = due;
        s_wario_pending_ticks = ticks;
        s_wario_pending_info = present_info;
        m_wario_real_entry = m_xfb_entry;
        m_wario_real_rect = m_xfb_rect;
        WarioTrace('H');
        return;
      }
    }
    WarioDumpPresented(m_xfb_entry, 'r');
    Present(&present_info);
    WarioTrace('r');
    s_wario_last_real_present = Clock::now();
    WarioNotePresent();
    ProcessFrameDumping(ticks);
"""

PRESENT_VI_FLUSH_OLD = "  bool is_duplicate = FetchXFB(xfb_addr, fb_width, fb_stride, fb_height, ticks);\n"
PRESENT_VI_FLUSH_NEW = ("  // A real frame still held from the previous VI goes out first.\n"
                        "  WarioTrace('V');\n"
                        "  WarioFlushPendingPresent(s_wario_pending_present);\n" + PRESENT_VI_FLUSH_OLD)

PRESENT_INCLUDE_OLD = '#include "VideoCommon/Present.h"\n\n#include "Common/ChunkFile.h"\n'
PRESENT_INCLUDE_NEW = ('#include "VideoCommon/Present.h"\n\n#include <algorithm>\n#include <chrono>\n#include <cstdio>\n#include <cstdlib>\n\n'
                       '#include "Common/ChunkFile.h"\n')

BP_INCLUDE_OLD = '#include "VideoCommon/BPStructs.h"\n\n#include <algorithm>\n#include <cstring>\n#include <string>\n'
BP_INCLUDE_NEW = ('#include "VideoCommon/BPStructs.h"\n\n#include <algorithm>\n#include <array>\n#include <atomic>\n#include <cmath>\n'
                  '#include <cstdio>\n#include <cstdlib>\n#include <cstring>\n#include <string>\n#include <unordered_map>\n'
                  '#include <utility>\n#include <vector>\n')

BP_INCLUDE2_OLD = '#include "VideoCommon/BPMemory.h"\n#include "VideoCommon/BoundingBox.h"\n'
BP_INCLUDE2_NEW = ('#include "Common/Matrix.h"\n#include "Common/Swap.h"\n'
                   '#include "VideoCommon/BPMemory.h"\n#include "VideoCommon/BoundingBox.h"\n'
                   '#include "VideoCommon/CPMemory.h"\n#include "VideoCommon/DataReader.h"\n'
                   '#include "VideoCommon/VertexManagerBase.h"\n#include "VideoCommon/XFMemory.h"\n')

BP_FUNC_OLD = "void BPInit()\n{"
BP_FUNC_NEW = r"""// ---------------------------------------------------------------------------
// Optional Wario World frame interpolation (scripts/tool_fix_wario_fps.py).
extern bool g_wario_view_correction_active;
extern Common::Matrix44 g_wario_view_correction;
extern float g_wario_main_projection[2];
extern bool g_wario_private_xfb_copy;
extern RcTcacheEntry g_wario_private_xfb_entry;
namespace VideoCommon
{
extern u64 g_wario_present_gaps[6];
void WarioTrace(char kind);
extern double g_wario_pending_late_sum, g_wario_pending_late_max;
extern u64 g_wario_pending_count, g_wario_pending_forced;
}  // namespace VideoCommon
using VideoCommon::g_wario_pending_count;
using VideoCommon::g_wario_present_gaps;
using VideoCommon::g_wario_pending_forced;
using VideoCommon::g_wario_pending_late_max;
using VideoCommon::g_wario_pending_late_sum;

static bool WarioFpsEnabled()
{
  static const bool enabled = [] {
    const char* value = std::getenv("MODERNGEKKO_WARIO_FPS");
    return value && *value && std::strcmp(value, "0") != 0 && std::strcmp(value, "off") != 0;
  }();
  return enabled;
}

bool g_wario_fps_record = WarioFpsEnabled();
// Frames per game frame (1 = off, 2-4), switched live by the in-game menu
// (VideoCommon/OnScreenUI.cpp). MODERNGEKKO_WARIO_FPS=1/on means 2, or give 2-4.
// Object interpolation on/off (menu "Motion"); off = camera only. MODERNGEKKO_WARIO_FPS_OBJECTS=0
// turns it off for hidden tests. Only matrices the game tags (MATRIX_STACK_HOOKS) are blended.
std::atomic<bool> g_wario_fps_objects{[] {
  const char* value = std::getenv("MODERNGEKKO_WARIO_FPS_OBJECTS");
  return !(value && std::strcmp(value, "0") == 0);
}()};
std::atomic<int> g_wario_fps_multiplier{[] {
  if (!WarioFpsEnabled())
    return 1;
  const int value = std::atoi(std::getenv("MODERNGEKKO_WARIO_FPS"));
  return value >= 2 && value <= 4 ? value : 2;
}()};
bool g_wario_fps_replaying = false;
bool g_wario_fps_state_loaded = false;  // set by VideoCommon_DoState on load

namespace
{
struct WarioCamera
{
  bool valid = false;
  Common::Vec3 eye, up, target;
};

// One XF matrix-memory load (0x000-0x0FF: position and texture matrices) in a frame's stream.
struct WarioMatrixLoad
{
  u32 offset, size;      // command bytes in WarioFpsState::commands
  u32 address, count;    // XF word address and length
  u32 values_at;         // index into WarioFrameMatrices::values
  u64 key;               // address | count << 12 | occurrence << 20 (match key across frames)
  bool tagged;           // identity from the game's matrix stack (exact pairing)
  bool main_projection;  // main camera projection was active when it was loaded
};

struct WarioFrameMatrices
{
  std::vector<WarioMatrixLoad> loads;
  std::vector<u32> values;
  std::unordered_map<u64, u32> by_key;       // (address, count, occurrence) -> load index
  std::unordered_map<u32, u32> occurrences;  // (address, count) -> loads so far
  std::unordered_map<u64, u32> tag_occurrences;  // tag -> loads so far
  std::unordered_map<u64, u32> tag_first;        // tag -> values_at of its first load
  void Clear()
  {
    loads.clear();
    values.clear();
    by_key.clear();
    occurrences.clear();
    tag_occurrences.clear();
    tag_first.clear();
  }
};

struct WarioFpsState
{
  bool frame_valid = false;     // recording started at a frame boundary
  bool reset_pending = false;   // next OnCommand is the XFB copy: start a new frame
  std::vector<u8> commands;
  std::vector<u8> replay;       // commands with interpolated matrix loads
  WarioFrameMatrices matrices, previous_matrices;
  u64 matrices_matched = 0, matrices_unmatched = 0;
  u64 pending_tag = 0;  // identity marker seen, applies to the next position matrix
  u64 tags_seen = 0, tagged_loads = 0, tag_repeats = 0, tag_repeat_diff = 0, screen_locked = 0, camera_locked = 0;
  Common::Matrix44 camera_delta = Common::Matrix44::Identity();  // V_N * V_N-1^-1
  std::vector<u8> prologue;
  std::vector<u8> tmem;
  WarioCamera current, previous;
  u64 frames = 0, interpolated = 0, skipped_cut = 0, skipped_nocam = 0, skipped_late = 0;
  double offset_sum = 0.0, offset_min = 1e9, offset_max = 0.0;
  u64 offset_count = 0;
};
WarioFpsState s_wfps;

void PutU8(std::vector<u8>& out, u8 value)
{
  out.push_back(value);
}
void PutU32(std::vector<u8>& out, u32 value)
{
  out.push_back(static_cast<u8>(value >> 24));
  out.push_back(static_cast<u8>(value >> 16));
  out.push_back(static_cast<u8>(value >> 8));
  out.push_back(static_cast<u8>(value));
}

bool WarioShouldLoadBP(u32 address)
{
  switch (address)
  {
  case BPMEM_SETDRAWDONE:
  case BPMEM_PE_TOKEN_ID:
  case BPMEM_PE_TOKEN_INT_ID:
  case BPMEM_TRIGGER_EFB_COPY:
  case BPMEM_LOADTLUT1:
  case BPMEM_PRELOAD_MODE:
  case BPMEM_PERF1:
  case BPMEM_TEXINVALIDATE:
  case BPMEM_CLEARBBOX1:
  case BPMEM_CLEARBBOX2:
  case BPMEM_CLEAR_PIXEL_PERF:
  case BPMEM_BP_MASK:
  case 0xFF:
    return false;
  default:
    return true;
  }
}

bool WarioShouldLoadXF(u32 address)
{
  return !(address == XFMEM_UNKNOWN_1007 ||
           (address >= XFMEM_UNKNOWN_GROUP_1_START && address <= XFMEM_UNKNOWN_GROUP_1_END) ||
           (address >= XFMEM_UNKNOWN_GROUP_2_START && address <= XFMEM_UNKNOWN_GROUP_2_END) ||
           (address >= XFMEM_UNKNOWN_GROUP_3_START && address <= XFMEM_UNKNOWN_GROUP_3_END));
}

// Start state of a frame as GPU commands (same register set as Dolphin's FifoPlayer).
void WarioSnapshotFrameStart()
{
  auto& out = s_wfps.prologue;
  out.clear();
  const u32* bp = reinterpret_cast<const u32*>(&bpmem);
  for (u32 i = 0; i < 0xFE; ++i)
  {
    if (!WarioShouldLoadBP(i))
      continue;
    PutU8(out, 0x61);
    PutU32(out, (i << 24) | (bp[i] & 0x00FFFFFF));
  }
  u32 cp[256] = {};
  g_main_cp_state.FillCPMemoryArray(cp);
  const auto put_cp = [&](u32 reg) {
    PutU8(out, 0x08);
    PutU8(out, static_cast<u8>(reg));
    PutU32(out, cp[reg]);
  };
  put_cp(MATINDEX_A);
  put_cp(MATINDEX_B);
  put_cp(VCD_LO);
  put_cp(VCD_HI);
  for (u32 i = 0; i < CP_NUM_VAT_REG; ++i)
  {
    put_cp(CP_VAT_REG_A + i);
    put_cp(CP_VAT_REG_B + i);
    put_cp(CP_VAT_REG_C + i);
  }
  for (u32 i = 0; i < CP_NUM_ARRAYS; ++i)
  {
    put_cp(ARRAY_BASE + i);
    put_cp(ARRAY_STRIDE + i);
  }
  const u32* xf = reinterpret_cast<const u32*>(&xfmem);
  static constexpr std::array<std::pair<u32, u32>, 4> xf_ranges = {
      {{0x000, 0x100}, {0x400, 0x460}, {0x500, 0x600}, {0x600, 0x680}}};
  for (const auto& [begin, end] : xf_ranges)
  {
    for (u32 address = begin; address < end; address += 16)
    {
      PutU8(out, 0x10);
      PutU32(out, 0x000F0000 | address);
      for (u32 i = 0; i < 16; ++i)
        PutU32(out, xf[address + i]);
    }
  }
  for (u32 i = 0; i < sizeof(XFMemory) / 4 - 4096; ++i)
  {
    if (!WarioShouldLoadXF(0x1000 + i))
      continue;
    PutU8(out, 0x10);
    PutU32(out, 0x1000 + i);
    PutU32(out, xf[4096 + i]);
  }
  s_wfps.tmem.assign(s_tex_mem.begin(), s_tex_mem.end());
}

float WarioReadFloat(Memory::MemoryManager& memory, u32 address)
{
  const u32 bits = memory.Read_U32(address);
  float value;
  std::memcpy(&value, &bits, sizeof(value));
  return value;
}

// Called after an XF write that touched the projection: keep this frame's main camera.
void WarioCaptureCamera()
{
  if (s_wfps.current.valid || xfmem.projection.type != ProjectionType::Perspective)
    return;
  auto& memory = Core::System::GetInstance().GetMemory();
  const u32 camera = memory.Read_U32(0x801FDA50u);
  if (camera < 0x80000000u || camera >= 0x81800000u - 0x100u)
    return;
  const float p00 = WarioReadFloat(memory, camera + 0x54u);
  const float p11 = WarioReadFloat(memory, camera + 0x68u);
  const auto& raw = xfmem.projection.rawProjection;
  if (!(std::abs(raw[0] - p00) <= 1e-4f * std::abs(p00) + 1e-6f &&
        std::abs(raw[2] - p11) <= 1e-4f * std::abs(p11) + 1e-6f))
    return;
  WarioCamera& cam = s_wfps.current;
  const auto vec = [&](u32 offset) {
    return Common::Vec3{WarioReadFloat(memory, camera + offset),
                        WarioReadFloat(memory, camera + offset + 4),
                        WarioReadFloat(memory, camera + offset + 8)};
  };
  cam.eye = vec(0x14);
  cam.up = vec(0x20);
  cam.target = vec(0x2C);
  const Common::Vec3 look = cam.eye - cam.target;
  if (!(look.LengthSquared() > 1e-6f) || !(cam.up.LengthSquared() > 1e-6f) ||
      !std::isfinite(look.LengthSquared()))
    return;
  cam.valid = true;
  g_wario_main_projection[0] = raw[0];
  g_wario_main_projection[1] = raw[2];
}

// C_MTXLookAt as a 4x4 (row-major) view matrix.
Common::Matrix44 WarioLookAt(const Common::Vec3& eye, const Common::Vec3& up,
                             const Common::Vec3& target)
{
  const Common::Vec3 look = (eye - target).Normalized();
  const Common::Vec3 right = up.Cross(look).Normalized();
  const Common::Vec3 up2 = look.Cross(right);
  Common::Matrix44 m = Common::Matrix44::Identity();
  const Common::Vec3 rows[3] = {right, up2, look};
  for (int r = 0; r < 3; ++r)
  {
    m.data[r * 4 + 0] = rows[r].x;
    m.data[r * 4 + 1] = rows[r].y;
    m.data[r * 4 + 2] = rows[r].z;
    m.data[r * 4 + 3] = -rows[r].Dot(eye);
  }
  return m;
}

Common::Matrix44 WarioRigidInverse(const Common::Matrix44& m)
{
  Common::Matrix44 inv = Common::Matrix44::Identity();
  for (int r = 0; r < 3; ++r)
    for (int c = 0; c < 3; ++c)
      inv.data[r * 4 + c] = m.data[c * 4 + r];
  for (int r = 0; r < 3; ++r)
  {
    inv.data[r * 4 + 3] = -(inv.data[r * 4 + 0] * m.data[3] + inv.data[r * 4 + 1] * m.data[7] +
                            inv.data[r * 4 + 2] * m.data[11]);
  }
  return inv;
}

void WarioRun(std::vector<u8>& buffer)
{
  if (buffer.empty())
    return;
  OpcodeDecoder::RunFifo<false>(DataReader(buffer.data(), buffer.data() + buffer.size()), nullptr);
}

float WarioBitsToFloat(u32 bits)
{
  float value;
  std::memcpy(&value, &bits, sizeof(value));
  return value;
}

u32 WarioFloatToBits(float value)
{
  u32 bits;
  std::memcpy(&bits, &value, sizeof(bits));
  return bits;
}

// Halfway value of a matrix load matched between frames N-1 and N. Rejects pairs that are
// clearly different objects or wrapped texture scrolls: rows of 4 (3 rotation/scale + 1
// translation); rotation part may change by 35% of its size, translation by 25% + 0.5 units.
// How far a matched load moved by itself between N-1 and N (lower is better); false when it
// cannot be the same object. Position matrices under the main camera are compared after
// applying the camera's own move (camera_delta = V_N * V_N-1^-1), so a static object scores 0
// and only real object motion counts: at most 40 units per frame, rotation within 30%.
bool WarioLerpMatrix(const u32* before, const u32* now, u32 count, float* out);

bool WarioMatchScore(const u32* before, const u32* now, u32 count, bool position, float* score)
{
  if (count == 0 || count % 4 != 0)
    return false;
  if (!position)
  {
    float scratch[16];
    if (!WarioLerpMatrix(before, now, count, scratch))
      return false;
    float dt2 = 0.0f;
    for (u32 i = 3; i < count; i += 4)
    {
      const float d = WarioBitsToFloat(now[i]) - WarioBitsToFloat(before[i]);
      dt2 += d * d;
    }
    *score = std::sqrt(dt2);
    return true;
  }
  const Common::Matrix44& d = s_wfps.camera_delta;
  float worst = 0.0f;
  for (u32 block = 0; block < count; block += 12)
  {
    float max_rot = 0.0f, rot_diff = 0.0f, dt2 = 0.0f, raw_rot = 0.0f, raw2 = 0.0f;
    for (int r = 0; r < 3; ++r)
    {
      for (int c = 0; c < 4; ++c)
      {
        const float previous = WarioBitsToFloat(before[block + r * 4 + c]);
        float predicted = d.data[r * 4 + 0] * WarioBitsToFloat(before[block + 0 * 4 + c]) +
                          d.data[r * 4 + 1] * WarioBitsToFloat(before[block + 1 * 4 + c]) +
                          d.data[r * 4 + 2] * WarioBitsToFloat(before[block + 2 * 4 + c]);
        if (c == 3)
          predicted += d.data[r * 4 + 3];
        const float actual = WarioBitsToFloat(now[block + r * 4 + c]);
        if (!std::isfinite(predicted) || !std::isfinite(actual))
          return false;
        if (c == 3)
        {
          dt2 += (actual - predicted) * (actual - predicted);
          raw2 += (actual - previous) * (actual - previous);
        }
        else
        {
          max_rot = std::max(max_rot, std::abs(actual));
          rot_diff = std::max(rot_diff, std::abs(actual - predicted));
          raw_rot = std::max(raw_rot, std::abs(actual - previous));
        }
      }
    }
    // Plausible as the same object in world space, or (camera-locked effects) in camera space.
    const float limit = 0.3f * std::max(max_rot, 1e-3f);
    const bool world_ok = rot_diff <= limit && dt2 <= 40.0f * 40.0f;
    const bool camera_ok = raw_rot <= limit && raw2 <= 40.0f * 40.0f;
    if (!world_ok && !camera_ok)
      return false;
    const float world_score = std::sqrt(dt2) + rot_diff * 10.0f;
    const float camera_score = std::sqrt(raw2) + raw_rot * 10.0f;
    worst = std::max(worst, world_ok && camera_ok ? std::min(world_score, camera_score) :
                            world_ok              ? world_score :
                                                    camera_score);
  }
  *score = worst;
  return true;
}

bool WarioLerpMatrix(const u32* before, const u32* now, u32 count, float* out)
{
  if (count == 0 || count % 4 != 0)
    return false;
  float max_rot = 0.0f, rot_diff = 0.0f, dt2 = 0.0f, t_now2 = 0.0f, t_before2 = 0.0f;
  for (u32 i = 0; i < count; ++i)
  {
    const float a = WarioBitsToFloat(before[i]);
    const float b = WarioBitsToFloat(now[i]);
    if (!std::isfinite(a) || !std::isfinite(b))
      return false;
    out[i] = 0.5f * (a + b);
    if (i % 4 == 3)
    {
      dt2 += (b - a) * (b - a);
      t_now2 += b * b;
      t_before2 += a * a;
    }
    else
    {
      max_rot = std::max(max_rot, std::abs(b));
      rot_diff = std::max(rot_diff, std::abs(b - a));
    }
  }
  return rot_diff <= 0.35f * std::max(max_rot, 1e-3f) &&
         std::sqrt(dt2) <= 0.25f * std::sqrt(std::max(t_now2, t_before2)) + 0.5f;
}

// Frame N's commands with matched position-matrix loads replaced by an immediate XF write of the
// interpolated matrix at fraction t between N-1 and N.
// - Main-camera position matrices (GX PNMTX slots, XF 0x00-0x77): the camera is taken out first.
//   With D = V_N * V_N-1^-1, the value loaded is lerp_t(D * MV_N-1, MV_N) = V_N * lerp_t(world);
//   the projection's camera correction then supplies the in-between camera. A static object gets
//   exactly MV_N, the same as an unmatched one, so multi-pass objects and neighbouring geometry
//   always agree (no ghosting or seams).
// - Other position matrices (2D/HUD): plain lerp with the same guard.
// - Texture matrices (0x78-0xFF) are never interpolated: effects often jitter their texture
//   coordinates every frame, and blending those makes them jump.
void WarioBuildReplay(float t)
{
  auto& out = s_wfps.replay;
  out.clear();
  const auto& now = s_wfps.matrices;
  const auto& before = s_wfps.previous_matrices;
  const u8* commands = s_wfps.commands.data();
  u32 cursor = 0;
  float result[16];
  float predicted[16];
  // Screen-locked geometry (heat haze, overlays drawn with the 3D camera): its matrix is identical
  // in N-1 and N although the camera moved; it gets C^-1 * MV so the correction leaves it in place.
  const Common::Matrix44 inverse = WarioRigidInverse(g_wario_view_correction);
  float camera_motion = 0.0f;
  for (int i = 0; i < 12; ++i)
    camera_motion = std::max(camera_motion, std::abs(s_wfps.camera_delta.data[i] - (i % 5 == 0 ? 1.0f : 0.0f)));
  const bool camera_moved = camera_motion > 1e-4f;
  const auto emit = [&](const WarioMatrixLoad& load, const float* values) {
    PutU8(out, 0x10);
    PutU32(out, ((load.count - 1) << 16) | load.address);
    for (u32 i = 0; i < load.count; ++i)
      PutU32(out, WarioFloatToBits(values[i]));
  };
  const auto screen_locked = [&](const WarioMatrixLoad& load, const u32* now_values) -> bool {
    if (!camera_moved)
      return false;
    const auto found = before.by_key.find(load.key);
    if (found == before.by_key.end() || before.loads[found->second].count != load.count)
      return false;
    const u32* old_values = &before.values[before.loads[found->second].values_at];
    if (!std::equal(now_values, now_values + load.count, old_values))
      return false;
    for (u32 block = 0; block < load.count; block += 12)
    {
      for (int r = 0; r < 3; ++r)
      {
        for (int c = 0; c < 4; ++c)
        {
          float value = inverse.data[r * 4 + 0] * WarioBitsToFloat(now_values[block + 0 * 4 + c]) +
                        inverse.data[r * 4 + 1] * WarioBitsToFloat(now_values[block + 1 * 4 + c]) +
                        inverse.data[r * 4 + 2] * WarioBitsToFloat(now_values[block + 2 * 4 + c]);
          if (c == 3)
            value += inverse.data[r * 4 + 3];
          result[block + r * 4 + c] = value;
        }
      }
    }
    emit(load, result);
    s_wfps.screen_locked++;
    return true;
  };
  for (const WarioMatrixLoad& load : now.loads)
  {
    if (load.address >= 0x78 || load.count % 4 != 0)
      continue;  // texture matrices stay as recorded
    out.insert(out.end(), commands + cursor, commands + load.offset);
    cursor = load.offset + load.size;
    const bool camera_space = load.main_projection && load.address % 4 == 0 && load.count % 12 == 0;
    const u32* now_values = &now.values[load.values_at];
    if (camera_space && screen_locked(load, now_values))
      continue;
    // Only matrices the game tagged with an identity are interpolated, paired exactly by that
    // identity (the plausibility check stays as a safety net). Untagged loads keep frame N.
    const u32* best = nullptr;
    if (load.tagged)
    {
      const auto found = before.by_key.find(load.key);
      if (found != before.by_key.end() && before.loads[found->second].tagged)
      {
        const u32* values = &before.values[before.loads[found->second].values_at];
        float score;
        if (WarioMatchScore(values, now_values, load.count, camera_space, &score))
          best = values;
      }
    }
    if (!best)
    {
      s_wfps.matrices_unmatched++;
      out.insert(out.end(), commands + load.offset, commands + load.offset + load.size);
      continue;
    }
    if (camera_space)
    {
      const Common::Matrix44& d = s_wfps.camera_delta;
      for (u32 block = 0; block < load.count; block += 12)
      {
        for (int r = 0; r < 3; ++r)
        {
          for (int c = 0; c < 4; ++c)
          {
            float value = d.data[r * 4 + 0] * WarioBitsToFloat(best[block + 0 * 4 + c]) +
                          d.data[r * 4 + 1] * WarioBitsToFloat(best[block + 1 * 4 + c]) +
                          d.data[r * 4 + 2] * WarioBitsToFloat(best[block + 2 * 4 + c]);
            if (c == 3)
              value += d.data[r * 4 + 3];
            predicted[block + r * 4 + c] = value;
          }
        }
      }
    }
    else
    {
      for (u32 i = 0; i < load.count; ++i)
        predicted[i] = WarioBitsToFloat(best[i]);
    }
    // Interpolate in the frame of reference the object moves less in: world space (static and
    // world-moving objects) or camera space (effects that follow the camera, e.g. heat haze, which
    // would otherwise be dragged along by the camera correction and ghost).
    bool camera_locked = false;
    if (camera_space)
    {
      float world2 = 0.0f, raw2 = 0.0f;
      for (u32 i = 3; i < load.count; i += 4)
      {
        const float now_t = WarioBitsToFloat(now_values[i]);
        world2 += (now_t - predicted[i]) * (now_t - predicted[i]);
        raw2 += (now_t - WarioBitsToFloat(best[i])) * (now_t - WarioBitsToFloat(best[i]));
      }
      camera_locked = raw2 < 0.25f * world2;
    }
    if (camera_locked)
    {
      float blended[16];
      for (u32 i = 0; i < load.count; ++i)
      {
        const float a = WarioBitsToFloat(best[i]);
        blended[i] = a + t * (WarioBitsToFloat(now_values[i]) - a);
      }
      for (u32 block = 0; block < load.count; block += 12)
      {
        for (int r = 0; r < 3; ++r)
        {
          for (int c = 0; c < 4; ++c)
          {
            float value = inverse.data[r * 4 + 0] * blended[block + 0 * 4 + c] +
                          inverse.data[r * 4 + 1] * blended[block + 1 * 4 + c] +
                          inverse.data[r * 4 + 2] * blended[block + 2 * 4 + c];
            if (c == 3)
              value += inverse.data[r * 4 + 3];
            result[block + r * 4 + c] = value;
          }
        }
      }
      s_wfps.camera_locked++;
    }
    else
    {
      for (u32 i = 0; i < load.count; ++i)
      {
        const float b = WarioBitsToFloat(now_values[i]);
        result[i] = predicted[i] + t * (b - predicted[i]);
      }
    }
    s_wfps.matrices_matched++;
    emit(load, result);
  }
  out.insert(out.end(), commands + cursor, commands + s_wfps.commands.size());
}

// Remember a matrix-memory load of the real frame (called after it executed).
void WarioRecordMatrixLoad(const u8* data, u32 size, u32 offset)
{
  u32 address = 0, count = 0;
  const u32 word = (u32(data[1]) << 24) | (u32(data[2]) << 16) | (u32(data[3]) << 8) | data[4];
  if (data[0] == 0x10)
  {
    address = word & 0xFFFF;
    count = (word >> 16) + 1;
  }
  else if (data[0] == 0x20 || data[0] == 0x30)  // indexed loads: position (A) / texture (C)
  {
    address = word & 0xFFF;
    count = ((word >> 12) & 0xF) + 1;
  }
  if (count == 0 || count > 16 || address + count > 0x100)
    return;
  auto& frame = s_wfps.matrices;
  const u32 base_key = address | (count << 12);
  const u32 occurrence = frame.occurrences[base_key]++;
  const bool tagged = s_wfps.pending_tag != 0 && data[0] == 0x10 && address < 0x78 && count == 12;
  const u64 tag = s_wfps.pending_tag;
  if (address < 0x78)
    s_wfps.pending_tag = 0;  // a marker belongs to the position matrix right after it
  WarioMatrixLoad load{};
  load.offset = offset;
  load.size = size;
  load.address = address;
  load.count = count;
  load.values_at = static_cast<u32>(frame.values.size());
  load.key = u64(base_key) | (u64(occurrence) << 20);
  load.tagged = tagged;
  if (tagged)
  {
    // Same identity drawn twice in a frame (e.g. multi-pass): pair by its own repeat count.
    const u32 repeat = frame.tag_occurrences[tag]++;
    const u32* xf_values = reinterpret_cast<const u32*>(&xfmem) + address;
    if (repeat == 0)
    {
      frame.tag_first[tag] = static_cast<u32>(frame.values.size());
    }
    else
    {
      s_wfps.tag_repeats++;
      const u32 first = frame.tag_first[tag];
      if (!std::equal(xf_values, xf_values + count, frame.values.begin() + first))
        s_wfps.tag_repeat_diff++;
    }
    load.key = (tag ^ (u64(repeat) * 0x9E3779B97F4A7C15ull)) | (1ull << 63);
    s_wfps.tagged_loads++;
  }
  const auto& raw = xfmem.projection.rawProjection;
  load.main_projection =
      xfmem.projection.type == ProjectionType::Perspective &&
      std::abs(raw[0] - g_wario_main_projection[0]) <=
          1e-4f * std::abs(g_wario_main_projection[0]) + 1e-6f &&
      std::abs(raw[2] - g_wario_main_projection[1]) <=
          1e-4f * std::abs(g_wario_main_projection[1]) + 1e-6f;
  const u32* xf = reinterpret_cast<const u32*>(&xfmem);
  frame.values.insert(frame.values.end(), xf + address, xf + address + count);
  frame.by_key.emplace(load.key, static_cast<u32>(frame.loads.size()));
  frame.loads.push_back(load);
}

void WarioWriteStats()
{
  static const char* path = std::getenv("MODERNGEKKO_WARIO_FPS_STATS");
  if (!path || !*path || s_wfps.frames % 300 != 0)
    return;
  if (FILE* file = std::fopen(path, "w"))
  {
    std::fprintf(file,
                 "frames=%llu\ninterpolated=%llu\nskipped_cut=%llu\nskipped_no_camera=%llu\n"
                 "skipped_late=%llu\noffset_ms_avg=%.2f\noffset_ms_min=%.2f\noffset_ms_max=%.2f\n"
                 "last_commands=%zu\n",
                 static_cast<unsigned long long>(s_wfps.frames),
                 static_cast<unsigned long long>(s_wfps.interpolated),
                 static_cast<unsigned long long>(s_wfps.skipped_cut),
                 static_cast<unsigned long long>(s_wfps.skipped_nocam),
                 static_cast<unsigned long long>(s_wfps.skipped_late),
                 s_wfps.offset_count ? s_wfps.offset_sum / s_wfps.offset_count : 0.0,
                 s_wfps.offset_count ? s_wfps.offset_min : 0.0, s_wfps.offset_max,
                 s_wfps.commands.size());
    std::fprintf(file, "matrices_matched=%llu\nmatrices_unmatched=%llu\ntags_seen=%llu\ntagged_loads=%llu\ntag_repeats=%llu\ntag_repeat_diff=%llu\nscreen_locked=%llu\ncamera_locked=%llu\n",
                 static_cast<unsigned long long>(s_wfps.matrices_matched),
                 static_cast<unsigned long long>(s_wfps.matrices_unmatched),
                 static_cast<unsigned long long>(s_wfps.tags_seen),
                 static_cast<unsigned long long>(s_wfps.tagged_loads),
                 static_cast<unsigned long long>(s_wfps.tag_repeats),
                 static_cast<unsigned long long>(s_wfps.tag_repeat_diff),
                 static_cast<unsigned long long>(s_wfps.screen_locked),
                 static_cast<unsigned long long>(s_wfps.camera_locked));
    std::fprintf(file, "held_real=%llu\nheld_forced=%llu\nheld_late_ms_avg=%.2f\nheld_late_ms_max=%.2f\n",
                 static_cast<unsigned long long>(g_wario_pending_count),
                 static_cast<unsigned long long>(g_wario_pending_forced),
                 g_wario_pending_count ? g_wario_pending_late_sum / g_wario_pending_count : 0.0,
                 g_wario_pending_late_max);
    std::fprintf(file, "gaps_lt4=%llu\ngaps_4_6=%llu\ngaps_6_10=%llu\ngaps_10_12=%llu\ngaps_12_15=%llu\n"
                 "gaps_ge15=%llu\n",
                 static_cast<unsigned long long>(g_wario_present_gaps[0]),
                 static_cast<unsigned long long>(g_wario_present_gaps[1]),
                 static_cast<unsigned long long>(g_wario_present_gaps[2]),
                 static_cast<unsigned long long>(g_wario_present_gaps[3]),
                 static_cast<unsigned long long>(g_wario_present_gaps[4]),
                 static_cast<unsigned long long>(g_wario_present_gaps[5]));
    std::fclose(file);
  }
}

// At the real XFB copy of frame N (already copied to its XFB entry, EFB not yet cleared).
void WarioFpsOnXfbCopy(u32 dest_addr, u32 copy_width, u32 height, u32 dest_stride,
                       const MathUtil::Rectangle<int>& src_rect, float y_scale, float gamma,
                       bool clear)
{
  if (g_wario_fps_replaying)
    return;
  VideoCommon::WarioTrace('C');
  // Live on/off from the in-game menu, switched at a frame boundary.
  if (const bool wanted = g_wario_fps_multiplier.load(std::memory_order_relaxed) > 1;
      wanted != g_wario_fps_record)
  {
    g_wario_fps_record = wanted;
    s_wfps.frame_valid = false;
    s_wfps.reset_pending = wanted;
    s_wfps.current.valid = false;
    s_wfps.previous.valid = false;
    s_wfps.matrices.Clear();
    s_wfps.previous_matrices.Clear();
    if (!wanted)
      g_presenter->WarioFlushPendingPresent(true);
    return;
  }
  if (!g_wario_fps_record)
    return;
  if (g_wario_fps_state_loaded)
  {
    // Savestate loaded: what was recorded belongs to the old state; start over.
    g_wario_fps_state_loaded = false;
    s_wfps.frame_valid = false;
    s_wfps.reset_pending = true;
    s_wfps.current.valid = false;
    s_wfps.previous.valid = false;
    s_wfps.matrices.Clear();
    s_wfps.previous_matrices.Clear();
    return;
  }
  const bool had_frame = s_wfps.frame_valid;
  s_wfps.reset_pending = true;
  s_wfps.frames++;
  const WarioCamera current = s_wfps.current;
  const WarioCamera previous = s_wfps.previous;
  s_wfps.previous = current;
  s_wfps.current.valid = false;
  WarioWriteStats();
  if (!had_frame || g_ActiveConfig.bImmediateXFB)
    return;
  if (!current.valid || !previous.valid)
  {
    s_wfps.skipped_nocam++;
    return;
  }
  // Camera cuts and teleports: show only the real frames.
  const Common::Vec3 look_now = (current.eye - current.target).Normalized();
  const Common::Vec3 look_before = (previous.eye - previous.target).Normalized();
  if ((current.eye - previous.eye).Length() > 150.0f ||
      (current.target - previous.target).Length() > 150.0f || look_now.Dot(look_before) < 0.9f)
  {
    s_wfps.skipped_cut++;
    return;
  }

  const Common::Matrix44 view_now = WarioLookAt(current.eye, current.up, current.target);
  s_wfps.camera_delta =
      view_now * WarioRigidInverse(WarioLookAt(previous.eye, previous.up, previous.target));
  const int multiplier = std::clamp(g_wario_fps_multiplier.load(std::memory_order_relaxed), 2, 4);
  const double interval = 1.0 / 59.94 / multiplier;

  // Diagnostics: MODERNGEKKO_WARIO_FPS_DUMP=<dir> saves two consecutive real/in-between pairs every
  // 120 frames; MODERNGEKKO_WARIO_FPS_IDENTITY=1 replays without any change (must match the real
  // frame). Object interpolation is g_wario_fps_objects (menu "Motion").
  static const char* dump_dir = std::getenv("MODERNGEKKO_WARIO_FPS_DUMP");
  static const bool identity = std::getenv("MODERNGEKKO_WARIO_FPS_IDENTITY") != nullptr;
  const bool objects = g_wario_fps_objects.load(std::memory_order_relaxed);
  const bool dump = dump_dir && *dump_dir && s_wfps.interpolated % 120 <= 1;
  const auto private_copy = [&] {
    g_wario_private_xfb_copy = true;
    g_texture_cache->CopyRenderTargetToTexture(
        dest_addr, EFBCopyFormat::XFB, copy_width, height, dest_stride, false, src_rect, false,
        false, y_scale, gamma, bpmem.triggerEFBCopy.clamp_top, bpmem.triggerEFBCopy.clamp_bottom,
        bpmem.copyfilter.GetCoefficients());
    g_wario_private_xfb_copy = false;
    RcTcacheEntry copied = std::move(g_wario_private_xfb_entry);
    g_wario_private_xfb_entry.reset();
    return copied;
  };
  const auto clear_efb = [&] {
    // The real path clears after copying; each replayed frame expects that cleared EFB.
    if (clear)
    {
      ClearScreen(g_framebuffer_manager.get(), src_rect, bpmem.blendmode.color_update != 0,
                  bpmem.blendmode.alpha_update != 0, bpmem.zmode.update_enable != 0,
                  bpmem.zcontrol.pixel_format, bpmem.clearcolorAR, bpmem.clearcolorGB,
                  bpmem.clearZValue);
    }
  };

  auto& system = Core::System::GetInstance();
  auto& xf_state_manager = system.GetXFStateManager();
  g_vertex_manager->Flush();
  // Frame N as rendered, before the replays reuse the EFB (shown as the real frame after them).
  RcTcacheEntry real = private_copy();
  if (dump && real)
  {
    real->texture->Save(
        fmt::format("{}/real_{:08}.png", dump_dir, static_cast<unsigned long long>(s_wfps.frames)),
        0);
  }

  // Each in-between frame is queued as soon as it is built, and frames already due (the held real
  // frame, earlier in-between frames) are shown between steps: at 4x in heavy rooms the three
  // replays take long enough that waiting for all of them bunched the presents (stutter that
  // reads as motion blur).
  size_t queued = 0;
  const auto queue = [&](RcTcacheEntry frame) {
    VideoCommon::WarioTrace('Q');
    const size_t i = queued++;
    if (!frame)
      return;
    s_wfps.interpolated++;
    if (dump && i == 0)
    {
      frame->texture->Save(
          fmt::format("{}/mid_{:08}.png", dump_dir, static_cast<unsigned long long>(s_wfps.frames)),
          0);
    }
    const double offset = g_presenter->PresentInterpolated(
        std::move(frame), dest_stride / 2, height, interval * static_cast<double>(i + 1), interval);
    if (offset < 0.0)
    {
      s_wfps.skipped_late++;
    }
    else if (i == 0)
    {
      s_wfps.offset_sum += offset;
      s_wfps.offset_count++;
      s_wfps.offset_min = std::min(s_wfps.offset_min, offset);
      s_wfps.offset_max = std::max(s_wfps.offset_max, offset);
    }
  };
  g_presenter->WarioFlushPendingPresent(false);

  g_wario_fps_replaying = true;
  std::vector<u8> tmem_end(s_tex_mem.begin(), s_tex_mem.end());
  for (int step = 1; step < multiplier; ++step)
  {
    const float t = static_cast<float>(step) / static_cast<float>(multiplier);
    const Common::Vec3 eye = previous.eye + (current.eye - previous.eye) * t;
    const Common::Vec3 target = previous.target + (current.target - previous.target) * t;
    const Common::Vec3 up = previous.up + (current.up - previous.up) * t;
    if (!((eye - target).LengthSquared() > 1e-6f) || !(up.LengthSquared() > 1e-6f))
      break;
    g_wario_view_correction = identity ? Common::Matrix44::Identity() :
                                         WarioLookAt(eye, up, target) * WarioRigidInverse(view_now);
    clear_efb();
    std::copy(s_wfps.tmem.begin(), s_wfps.tmem.end(), s_tex_mem.begin());
    g_texture_cache->WarioSwapFrameCopies(true);
    WarioRun(s_wfps.prologue);
    g_wario_view_correction_active = true;
    xf_state_manager.SetProjectionChanged();
    if (objects && !identity)
    {
      WarioBuildReplay(t);
      WarioRun(s_wfps.replay);
    }
    else
    {
      WarioRun(s_wfps.commands);
    }
    g_vertex_manager->Flush();
    g_wario_view_correction_active = false;
    xf_state_manager.SetProjectionChanged();
    queue(private_copy());
  }
  g_texture_cache->WarioSwapFrameCopies(false);
  std::copy(tmem_end.begin(), tmem_end.end(), s_tex_mem.begin());
  g_wario_fps_replaying = false;
  if (queued > 0)
    g_presenter->WarioSetRealCopy(std::move(real), dest_stride / 2, height);

  BPFunctions::SetScissorAndViewport(g_framebuffer_manager.get(), bpmem.scissorTL, bpmem.scissorBR,
                                     bpmem.scissorOffset, xfmem.viewport);
}
}  // namespace

void WarioFpsRecordCommand(const u8* data, u32 size)
{
  if (g_wario_fps_replaying)
    return;
  // A real frame held back for pacing is shown from here once due (the video thread never sleeps).
  static u32 command_counter = 0;
  if ((++command_counter & 15) == 0)
    g_presenter->WarioFlushPendingPresent(false);
  if (s_wfps.reset_pending)
  {
    // This is the XFB copy that ended the previous frame.
    s_wfps.reset_pending = false;
    s_wfps.commands.clear();
    g_texture_cache->WarioResetFrameCopies();
    std::swap(s_wfps.matrices, s_wfps.previous_matrices);
    s_wfps.matrices.Clear();
    WarioSnapshotFrameStart();
    s_wfps.frame_valid = true;
    return;
  }
  if (!s_wfps.frame_valid || static_cast<OpcodeDecoder::Opcode>(data[0]) ==
                                 OpcodeDecoder::Opcode::GX_CMD_CALL_DL)
    return;
  s_wfps.commands.insert(s_wfps.commands.end(), data, data + size);
  // Identity marker from the game's matrix stack (build_rel_bundle.py MATRIX_STACK_HOOKS):
  // XF write of 2 words to the unused XF memory 0x0FFE.
  if (data[0] == 0x10 && size >= 13 && data[1] == 0x00 && data[2] == 0x01 && data[3] == 0x0F &&
      data[4] == 0xFE)
  {
    const u32 high = (u32(data[5]) << 24) | (u32(data[6]) << 16) | (u32(data[7]) << 8) | data[8];
    const u32 low = (u32(data[9]) << 24) | (u32(data[10]) << 16) | (u32(data[11]) << 8) | data[12];
    s_wfps.pending_tag = (u64(high) << 32) | low;
    s_wfps.tags_seen++;
  }
  else if ((data[0] == 0x10 || data[0] == 0x20 || data[0] == 0x30) && size >= 5)
  {
    WarioRecordMatrixLoad(data, size, static_cast<u32>(s_wfps.commands.size() - size));
  }
  if (data[0] == 0x10 && size >= 5 && !s_wfps.current.valid)
  {
    const u32 command = (u32(data[1]) << 24) | (u32(data[2]) << 16) | (u32(data[3]) << 8) | data[4];
    const u32 address = command & 0xFFFF;
    const u32 count = (command >> 16) + 1;
    if (address <= XFMEM_SETPROJECTION + 6 && address + count > XFMEM_SETPROJECTION)
      WarioCaptureCamera();
  }
}
// ---------------------------------------------------------------------------

void BPInit()
{"""

BP_SUPPRESS_OLD = """  FlushPipeline();

  ((u32*)&bpmem)[bp.address] = bp.newvalue;
"""
BP_SUPPRESS_NEW = """  FlushPipeline();

  ((u32*)&bpmem)[bp.address] = bp.newvalue;

  // Frame interpolation replay: no interrupts or tokens towards the guest.
  if (g_wario_fps_replaying &&
      (bp.address == BPMEM_SETDRAWDONE || bp.address == BPMEM_PE_TOKEN_ID ||
       bp.address == BPMEM_PE_TOKEN_INT_ID))
  {
    return;
  }
"""

BP_XFB_OLD = """      else
      {
        // We should be able to get away with deactivating the current bbox tracking"""
BP_XFB_NEW = """      else if (g_wario_fps_replaying)
      {
        // Frame interpolation replay: the in-between XFB copy is made by WarioFpsOnXfbCopy.
      }
      else
      {
        // We should be able to get away with deactivating the current bbox tracking"""

BP_HOOK_OLD = """        system.GetVideoEvents().after_frame_event.Trigger(system);
"""
BP_HOOK_NEW = """        system.GetVideoEvents().after_frame_event.Trigger(system);

        WarioFpsOnXfbCopy(destAddr, copy_width, height, destStride, srcRect, yScale,
                          s_gammaLUT[PE_copy.gamma], PE_copy.clear != 0);
"""


VS_EXTERN_OLD = '#include "VideoCommon/XFStateManager.h"\n'
VS_EXTERN_NEW = (VS_EXTERN_OLD + "\n// Wario World frame interpolation: a loaded state invalidates the recorded frame.\n"
                 "extern bool g_wario_fps_state_loaded;\n")
VS_RESET_OLD = """    BPReload();
    VertexLoaderManager::MarkAllDirty();
  }
}"""
VS_RESET_NEW = """    BPReload();
    VertexLoaderManager::MarkAllDirty();
    g_wario_fps_state_loaded = true;
  }
}"""


def apply(replace, runtime):
    video = runtime / "vendor/dolphin/Source/Core/VideoCommon"
    replace(video / "OpcodeDecoding.cpp", OPCODE_DECL_OLD, OPCODE_DECL_NEW)
    replace(video / "OpcodeDecoding.cpp", OPCODE_HOOK_OLD, OPCODE_HOOK_NEW)
    replace(video / "VertexShaderManager.cpp", VSM_GLOBALS_OLD, VSM_GLOBALS_NEW)
    replace(video / "VertexShaderManager.cpp", VSM_APPLY_OLD, VSM_APPLY_NEW)
    replace(video / "TextureCacheBase.h", TC_HEADER_OLD, TC_HEADER_NEW)
    replace(video / "TextureCacheBase.cpp", TC_EXTERN_OLD, TC_EXTERN_NEW)
    replace(video / "TextureCacheBase.cpp", TC_GLOBALS_OLD, TC_GLOBALS_NEW)
    replace(video / "TextureCacheBase.cpp", TC_RECORD_OLD, TC_RECORD_NEW)
    replace(video / "TextureCacheBase.cpp", TC_AFTER_OLD, TC_AFTER_NEW)
    replace(video / "TextureCacheBase.cpp", TC_SWAP_OLD, TC_SWAP_NEW)
    replace(video / "TextureCacheBase.cpp", TC_SHUTDOWN_OLD, TC_SHUTDOWN_NEW)
    replace(video / "TextureCacheBase.cpp", TC_CAPTURE_OLD, TC_CAPTURE_NEW)
    replace(video / "TextureCacheBase.cpp", TC_GUARD_OLD, TC_GUARD_NEW)
    replace(video / "Present.h", PRESENT_DECL_OLD, PRESENT_DECL_NEW)
    replace(video / "Present.cpp", PRESENT_INCLUDE_OLD, PRESENT_INCLUDE_NEW)
    replace(video / "Present.cpp", PRESENT_EXTERN_OLD, PRESENT_EXTERN_NEW)
    core = runtime / "vendor/dolphin/Source/Core/Core"
    replace(core / "CoreTiming.cpp", CT_GLOBALS_OLD, CT_GLOBALS_NEW)
    replace(core / "CoreTiming.cpp", CT_SLEEP_OLD, CT_SLEEP_NEW)
    replace(video / "Present.cpp", PRESENT_STATIC_OLD, PRESENT_STATIC_NEW)
    replace(video / "Present.cpp", PRESENT_FUNC_OLD, PRESENT_FUNC_NEW)
    replace(video / "Present.cpp", PRESENT_VI_OLD, PRESENT_VI_NEW)
    replace(video / "Present.cpp", PRESENT_VI_FLUSH_OLD, PRESENT_VI_FLUSH_NEW)
    replace(video / "BPStructs.cpp", BP_INCLUDE_OLD, BP_INCLUDE_NEW)
    replace(video / "VideoState.cpp", VS_EXTERN_OLD, VS_EXTERN_NEW)
    replace(video / "VideoState.cpp", VS_RESET_OLD, VS_RESET_NEW)
    replace(video / "BPStructs.cpp", BP_INCLUDE2_OLD, BP_INCLUDE2_NEW)
    replace(video / "BPStructs.cpp", BP_FUNC_OLD, BP_FUNC_NEW)
    replace(video / "BPStructs.cpp", BP_SUPPRESS_OLD, BP_SUPPRESS_NEW)
    replace(video / "BPStructs.cpp", BP_XFB_OLD, BP_XFB_NEW)
    replace(video / "BPStructs.cpp", BP_HOOK_OLD, BP_HOOK_NEW)
