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
    "  // Wario World frame interpolation: queue an in-between frame (no frame count change).\n"
    "  // Returns its planned delay after the last real present in ms, or -1 when skipped.\n"
    "  double PresentInterpolated(RcTcacheEntry entry, u32 fb_width, u32 fb_height,\n"
    "                             double delay_seconds);\n"
    "  // Shows queued in-between / held-back real frames once due (or now, when forced).\n"
    "  void WarioFlushPendingPresent(bool force);\n"
    "  // Earliest due time of a queued frame, if any.\n"
    "  bool WarioNextPresentDue(TimePoint* due) const;\n"
    "  RcTcacheEntry m_wario_pending_mid;\n"
    "  u32 m_wario_pending_mid_width = 0, m_wario_pending_mid_height = 0;\n"
    "  TimePoint m_wario_pending_mid_due{};\n")

PRESENT_EXTERN_OLD = '#include "VideoCommon/Widescreen.h"\n'
PRESENT_EXTERN_NEW = PRESENT_EXTERN_OLD + (
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
                                      double delay_seconds)
{
  WarioFlushPendingPresent(true);
  if (!entry || fb_width == 0 || fb_height == 0 || (WarioFpsDebug() & 2))
    return -1.0;
  auto& system = Core::System::GetInstance();
  if (!system.IsDualCoreMode() && !g_wario_throttle_present_due)
  {
    g_wario_throttle_present_due = WarioThrottlePresentDue;
    g_wario_throttle_present_flush = WarioThrottlePresentFlush;
  }
  const auto half = std::chrono::duration_cast<DT>(std::chrono::duration<double>(delay_seconds));
  const auto target = s_wario_last_real_present + half;
  const auto now = Clock::now();
  // Skip when the next real frame is already due.
  if (now > target + half)
    return -1.0;
  m_wario_pending_mid = std::move(entry);
  m_wario_pending_mid_width = fb_width;
  m_wario_pending_mid_height = fb_height;
  m_wario_pending_mid_due = (WarioFpsDebug() & 1) ? now : target;
  const double offset_ms = std::chrono::duration<double, std::milli>(
                               std::max(now, m_wario_pending_mid_due) - s_wario_last_real_present)
                               .count();
  WarioFlushPendingPresent(false);
  return offset_ms;
}

bool Presenter::WarioNextPresentDue(TimePoint* due) const
{
  if (m_wario_pending_mid)
  {
    *due = m_wario_pending_mid_due;
    return true;
  }
  if (s_wario_pending_present)
  {
    *due = s_wario_pending_due;
    return true;
  }
  return false;
}

void Presenter::WarioFlushPendingPresent(bool force)
{
  const auto now = Clock::now();
  if (m_wario_pending_mid)
  {
    if (!force && now < m_wario_pending_mid_due)
      return;
    ReleaseXFBContentLock();
    m_xfb_entry = std::move(m_wario_pending_mid);
    m_wario_pending_mid.reset();
    m_xfb_rect = MathUtil::Rectangle<int>(
        0, 0,
        static_cast<int>(m_wario_pending_mid_width * m_xfb_entry->GetWidth() /
                         m_xfb_entry->native_width),
        static_cast<int>(m_wario_pending_mid_height * m_xfb_entry->GetHeight() /
                         m_xfb_entry->native_height));
    m_xfb_entry->AcquireContentLock();
    Present(nullptr);
    s_wario_last_mid_present = Clock::now();
    WarioNotePresent();
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
  Present(&s_wario_pending_info);
  s_wario_last_real_present = Clock::now();
  WarioNotePresent();
  ProcessFrameDumping(s_wario_pending_ticks);
  GetVideoEvents().after_present_event.Trigger(s_wario_pending_info);
}

void Presenter::SetNextSwapEstimatedTime(u64 ticks, TimePoint host_time)
"""

PRESENT_STATIC_OLD = "bool Presenter::FetchXFB(u32 xfb_addr,"
PRESENT_STATIC_NEW = """// Wario World frame interpolation pacing. The game issues its XFB copy late in each 16.7 ms
// frame, so the in-between frame can only be built just before the next VI. The real frame is
// then held back to half a frame after it (about 8 ms of extra latency, as in Ship of
// Harkinian's interpolation). It is not slept for: the video thread keeps decoding and shows
// the held frame from the command loop once it is due.
// MODERNGEKKO_WARIO_FPS_DEBUG bits (diagnostics only): 1 = no in-between sleep,
// 2 = build but do not show in-between frames, 4 = do not hold real frames.
static int WarioFpsDebug()
{
  static const int bits = [] {
    const char* value = std::getenv("MODERNGEKKO_WARIO_FPS_DEBUG");
    return value ? std::atoi(value) : 0;
  }();
  return bits;
}

static TimePoint s_wario_last_real_present{};
static TimePoint s_wario_last_mid_present{};
static bool s_wario_pending_present = false;
static TimePoint s_wario_pending_due{};
static u64 s_wario_pending_ticks = 0;
static PresentInfo s_wario_pending_info{};
double g_wario_pending_late_sum = 0.0, g_wario_pending_late_max = 0.0;
u64 g_wario_pending_count = 0, g_wario_pending_forced = 0;
// Gaps between consecutive presents while interpolating, in ms buckets:
// <4, 4-6.5, 6.5-10 (on pace), 10-12.5, 12.5-15, >=15.
u64 g_wario_present_gaps[6] = {};
static TimePoint s_wario_last_any_present{};

static void WarioNotePresent()
{
  const auto now = Clock::now();
  const double gap = std::chrono::duration<double, std::milli>(now - s_wario_last_any_present).count();
  s_wario_last_any_present = now;
  if (s_wario_last_mid_present == TimePoint{} || gap > 40.0)
    return;
  const int bucket = gap < 4.0 ? 0 : gap < 6.5 ? 1 : gap < 10.0 ? 2 : gap < 12.5 ? 3 : gap < 15.0 ? 4 : 5;
  g_wario_present_gaps[bucket]++;
}

""" + PRESENT_STATIC_OLD

PRESENT_VI_OLD = """    Present(&present_info);
    ProcessFrameDumping(ticks);
"""
PRESENT_VI_NEW = """    if (s_wario_last_mid_present > s_wario_last_real_present && !(WarioFpsDebug() & 4))
    {
      const auto half = std::chrono::duration_cast<DT>(std::chrono::duration<double>(0.5 / 59.94));
      const auto due = s_wario_last_mid_present + half;
      const auto now = Clock::now();
      if (due > now && due - now <= half)
      {
        s_wario_pending_present = true;
        s_wario_pending_due = due;
        s_wario_pending_ticks = ticks;
        s_wario_pending_info = present_info;
        return;
      }
    }
    Present(&present_info);
    s_wario_last_real_present = Clock::now();
    WarioNotePresent();
    ProcessFrameDumping(ticks);
"""

PRESENT_VI_FLUSH_OLD = "  bool is_duplicate = FetchXFB(xfb_addr, fb_width, fb_stride, fb_height, ticks);\n"
PRESENT_VI_FLUSH_NEW = "  WarioFlushPendingPresent(true);\n" + PRESENT_VI_FLUSH_OLD

PRESENT_INCLUDE_OLD = '#include "VideoCommon/Present.h"\n\n#include "Common/ChunkFile.h"\n'
PRESENT_INCLUDE_NEW = ('#include "VideoCommon/Present.h"\n\n#include <algorithm>\n#include <chrono>\n\n'
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
// Wanted state, switched live by the in-game menu (VideoCommon/OnScreenUI.cpp).
std::atomic<bool> g_wario_fps_enabled{WarioFpsEnabled()};
bool g_wario_fps_replaying = false;

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
  bool main_projection;  // main camera projection was active when it was loaded
};

struct WarioFrameMatrices
{
  std::vector<WarioMatrixLoad> loads;
  std::vector<u32> values;
  std::unordered_map<u64, u32> by_key;       // (address, count, occurrence) -> load index
  std::unordered_map<u32, u32> occurrences;  // (address, count) -> loads so far
  void Clear()
  {
    loads.clear();
    values.clear();
    by_key.clear();
    occurrences.clear();
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
    float max_rot = 0.0f, rot_diff = 0.0f, dt2 = 0.0f;
    for (int r = 0; r < 3; ++r)
    {
      for (int c = 0; c < 4; ++c)
      {
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
        }
        else
        {
          max_rot = std::max(max_rot, std::abs(actual));
          rot_diff = std::max(rot_diff, std::abs(actual - predicted));
        }
      }
    }
    if (rot_diff > 0.3f * std::max(max_rot, 1e-3f) || dt2 > 40.0f * 40.0f)
      return false;
    worst = std::max(worst, std::sqrt(dt2) + rot_diff * 10.0f);
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

// Frame N's commands with every matched matrix load replaced by an immediate XF write of the
// halfway matrix. Position matrices (GX PNMTX slots, XF 0x00-0x77) drawn with the main camera are
// pre-multiplied by C^-1 so that the projection's camera correction C cancels out for them.
void WarioBuildReplay()
{
  auto& out = s_wfps.replay;
  out.clear();
  const auto& now = s_wfps.matrices;
  const auto& before = s_wfps.previous_matrices;
  const Common::Matrix44 inverse = WarioRigidInverse(g_wario_view_correction);
  const u8* commands = s_wfps.commands.data();
  u32 cursor = 0;
  float lerped[16];
  for (const WarioMatrixLoad& load : now.loads)
  {
    out.insert(out.end(), commands + cursor, commands + load.offset);
    cursor = load.offset + load.size;
    // Draw order can shift by a load or two (culling, spawns): try nearby occurrences and keep
    // the candidate with the smallest own motion. Wrong pairings (another object) are rejected,
    // which is what caused objects to jump away and back for one in-between frame.
    const bool position = load.main_projection && load.address < 0x78 && load.address % 4 == 0 &&
                          load.count % 12 == 0;
    const u64 occurrence = load.key >> 20;
    const u64 base = load.key & 0xFFFFF;
    const u32* best = nullptr;
    float best_score = 0.0f;
    for (s64 delta : {0, -1, 1, -2, 2})
    {
      const s64 candidate = static_cast<s64>(occurrence) + delta;
      if (candidate < 0)
        continue;
      const auto found = before.by_key.find(base | (u64(candidate) << 20));
      if (found == before.by_key.end())
        continue;
      const u32* values = &before.values[before.loads[found->second].values_at];
      float score;
      if (WarioMatchScore(values, &now.values[load.values_at], load.count, position, &score) &&
          (!best || score < best_score))
      {
        best = values;
        best_score = score;
      }
    }
    if (!best || !WarioLerpMatrix(best, &now.values[load.values_at], load.count, lerped))
    {
      s_wfps.matrices_unmatched++;
      out.insert(out.end(), commands + load.offset, commands + load.offset + load.size);
      continue;
    }
    s_wfps.matrices_matched++;
    if (position)
    {
      for (u32 block = 0; block < load.count; block += 12)
      {
        float m[12];
        std::copy(lerped + block, lerped + block + 12, m);
        for (int r = 0; r < 3; ++r)
        {
          for (int c = 0; c < 4; ++c)
          {
            float value = inverse.data[r * 4 + 0] * m[0 * 4 + c] +
                          inverse.data[r * 4 + 1] * m[1 * 4 + c] +
                          inverse.data[r * 4 + 2] * m[2 * 4 + c];
            if (c == 3)
              value += inverse.data[r * 4 + 3];
            lerped[block + r * 4 + c] = value;
          }
        }
      }
    }
    PutU8(out, 0x10);
    PutU32(out, ((load.count - 1) << 16) | load.address);
    for (u32 i = 0; i < load.count; ++i)
      PutU32(out, WarioFloatToBits(lerped[i]));
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
  WarioMatrixLoad load{};
  load.offset = offset;
  load.size = size;
  load.address = address;
  load.count = count;
  load.values_at = static_cast<u32>(frame.values.size());
  load.key = u64(base_key) | (u64(occurrence) << 20);
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
    std::fprintf(file, "matrices_matched=%llu\nmatrices_unmatched=%llu\n",
                 static_cast<unsigned long long>(s_wfps.matrices_matched),
                 static_cast<unsigned long long>(s_wfps.matrices_unmatched));
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
  // Live on/off from the in-game menu, switched at a frame boundary.
  if (const bool wanted = g_wario_fps_enabled.load(std::memory_order_relaxed);
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

  const Common::Vec3 eye = (current.eye + previous.eye) * 0.5f;
  const Common::Vec3 target = (current.target + previous.target) * 0.5f;
  const Common::Vec3 up = (current.up + previous.up) * 0.5f;
  if (!((eye - target).LengthSquared() > 1e-6f) || !(up.LengthSquared() > 1e-6f))
    return;
  const Common::Matrix44 view_now = WarioLookAt(current.eye, current.up, current.target);
  g_wario_view_correction = WarioLookAt(eye, up, target) * WarioRigidInverse(view_now);
  s_wfps.camera_delta =
      view_now * WarioRigidInverse(WarioLookAt(previous.eye, previous.up, previous.target));

  // Diagnostics: MODERNGEKKO_WARIO_FPS_DUMP=<dir> saves two consecutive real/in-between pairs every 120 frames;
  // MODERNGEKKO_WARIO_FPS_IDENTITY=1 replays without the camera change (must match the real frame).
  static const char* dump_dir = std::getenv("MODERNGEKKO_WARIO_FPS_DUMP");
  static const bool identity = std::getenv("MODERNGEKKO_WARIO_FPS_IDENTITY") != nullptr;
  if (identity)
    g_wario_view_correction = Common::Matrix44::Identity();
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

  auto& system = Core::System::GetInstance();
  auto& xf_state_manager = system.GetXFStateManager();
  g_vertex_manager->Flush();
  if (dump)
  {
    if (RcTcacheEntry real = private_copy())
    {
      real->texture->Save(
          fmt::format("{}/real_{:08}.png", dump_dir, static_cast<unsigned long long>(s_wfps.frames)),
          0);
    }
  }
  // The real path clears after copying; the replayed frame expects that cleared EFB.
  if (clear)
  {
    ClearScreen(g_framebuffer_manager.get(), src_rect, bpmem.blendmode.color_update != 0,
                bpmem.blendmode.alpha_update != 0, bpmem.zmode.update_enable != 0,
                bpmem.zcontrol.pixel_format, bpmem.clearcolorAR, bpmem.clearcolorGB,
                bpmem.clearZValue);
  }

  g_wario_fps_replaying = true;
  std::vector<u8> tmem_end(s_tex_mem.begin(), s_tex_mem.end());
  std::copy(s_wfps.tmem.begin(), s_wfps.tmem.end(), s_tex_mem.begin());
  g_texture_cache->WarioSwapFrameCopies(true);
  WarioRun(s_wfps.prologue);
  g_wario_view_correction_active = true;
  xf_state_manager.SetProjectionChanged();
  // MODERNGEKKO_WARIO_FPS_OBJECTS=0 interpolates the camera only.
  static const bool objects = [] {
    const char* value = std::getenv("MODERNGEKKO_WARIO_FPS_OBJECTS");
    return !(value && std::strcmp(value, "0") == 0);
  }();
  if (objects && !identity)
  {
    WarioBuildReplay();
    WarioRun(s_wfps.replay);
  }
  else
  {
    WarioRun(s_wfps.commands);
  }
  g_vertex_manager->Flush();
  g_texture_cache->WarioSwapFrameCopies(false);
  g_wario_view_correction_active = false;
  xf_state_manager.SetProjectionChanged();
  std::copy(tmem_end.begin(), tmem_end.end(), s_tex_mem.begin());

  RcTcacheEntry entry = private_copy();
  g_wario_fps_replaying = false;

  BPFunctions::SetScissorAndViewport(g_framebuffer_manager.get(), bpmem.scissorTL, bpmem.scissorBR,
                                     bpmem.scissorOffset, xfmem.viewport);
  if (entry)
  {
    s_wfps.interpolated++;
    if (dump)
    {
      entry->texture->Save(
          fmt::format("{}/mid_{:08}.png", dump_dir, static_cast<unsigned long long>(s_wfps.frames)),
          0);
    }
    const double offset =
        g_presenter->PresentInterpolated(std::move(entry), dest_stride / 2, height, 0.5 / 59.94);
    if (offset < 0.0)
    {
      s_wfps.skipped_late++;
    }
    else
    {
      s_wfps.offset_sum += offset;
      s_wfps.offset_count++;
      s_wfps.offset_min = std::min(s_wfps.offset_min, offset);
      s_wfps.offset_max = std::max(s_wfps.offset_max, offset);
    }
  }
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
  if ((data[0] == 0x10 || data[0] == 0x20 || data[0] == 0x30) && size >= 5)
    WarioRecordMatrixLoad(data, size, static_cast<u32>(s_wfps.commands.size() - size));
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
    replace(video / "BPStructs.cpp", BP_INCLUDE2_OLD, BP_INCLUDE2_NEW)
    replace(video / "BPStructs.cpp", BP_FUNC_OLD, BP_FUNC_NEW)
    replace(video / "BPStructs.cpp", BP_SUPPRESS_OLD, BP_SUPPRESS_NEW)
    replace(video / "BPStructs.cpp", BP_XFB_OLD, BP_XFB_NEW)
    replace(video / "BPStructs.cpp", BP_HOOK_OLD, BP_HOOK_NEW)
