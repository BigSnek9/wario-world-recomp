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
    "  // Wario World frame interpolation: show an in-between frame (no frame count change).\n"
    "  // Returns the delay after the last real present in ms, or -1 when skipped.\n"
    "  double PresentInterpolated(RcTcacheEntry entry, u32 fb_width, u32 fb_height,\n"
    "                             double delay_seconds);\n"
    "  // Shows a held-back real frame once it is due (or now, when forced).\n"
    "  void WarioFlushPendingPresent(bool force);\n")

PRESENT_FUNC_OLD = "void Presenter::SetNextSwapEstimatedTime(u64 ticks, TimePoint host_time)\n"
PRESENT_FUNC_NEW = """double Presenter::PresentInterpolated(RcTcacheEntry entry, u32 fb_width, u32 fb_height,
                                      double delay_seconds)
{
  WarioFlushPendingPresent(true);
  if (!entry || fb_width == 0 || fb_height == 0)
    return -1.0;
  const auto half = std::chrono::duration_cast<DT>(std::chrono::duration<double>(delay_seconds));
  const auto target = s_wario_last_real_present + half;
  const auto now = Clock::now();
  // Skip when the next real frame is already due; never wait more than one half frame.
  if (now > target + half)
    return -1.0;
  if (target > now && target - now <= half)
    Core::System::GetInstance().GetCoreTiming().SleepUntil(target);

  ReleaseXFBContentLock();
  m_xfb_entry = std::move(entry);
  m_xfb_rect = MathUtil::Rectangle<int>(
      0, 0, static_cast<int>(fb_width * m_xfb_entry->GetWidth() / m_xfb_entry->native_width),
      static_cast<int>(fb_height * m_xfb_entry->GetHeight() / m_xfb_entry->native_height));
  m_xfb_entry->AcquireContentLock();
  const double offset_ms =
      std::chrono::duration<double, std::milli>(Clock::now() - s_wario_last_real_present).count();
  Present(nullptr);
  s_wario_last_mid_present = Clock::now();
  WarioNotePresent();
  return offset_ms;
}

void Presenter::WarioFlushPendingPresent(bool force)
{
  if (!s_wario_pending_present)
    return;
  const auto now = Clock::now();
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
PRESENT_VI_NEW = """    if (s_wario_last_mid_present > s_wario_last_real_present)
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
BP_INCLUDE_NEW = ('#include "VideoCommon/BPStructs.h"\n\n#include <algorithm>\n#include <array>\n#include <cmath>\n'
                  '#include <cstdio>\n#include <cstdlib>\n#include <cstring>\n#include <string>\n#include <vector>\n')

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
static bool g_wario_fps_replaying = false;

namespace
{
struct WarioCamera
{
  bool valid = false;
  Common::Vec3 eye, up, target;
};

struct WarioFpsState
{
  bool frame_valid = false;     // recording started at a frame boundary
  bool reset_pending = false;   // next OnCommand is the XFB copy: start a new frame
  std::vector<u8> commands;
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
  if (!g_wario_fps_record || g_wario_fps_replaying)
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
  g_wario_view_correction = WarioLookAt(eye, up, target) *
                            WarioRigidInverse(WarioLookAt(current.eye, current.up, current.target));

  // Diagnostics: MODERNGEKKO_WARIO_FPS_DUMP=<dir> saves every 120th real/in-between pair;
  // MODERNGEKKO_WARIO_FPS_IDENTITY=1 replays without the camera change (must match the real frame).
  static const char* dump_dir = std::getenv("MODERNGEKKO_WARIO_FPS_DUMP");
  static const bool identity = std::getenv("MODERNGEKKO_WARIO_FPS_IDENTITY") != nullptr;
  if (identity)
    g_wario_view_correction = Common::Matrix44::Identity();
  const bool dump = dump_dir && *dump_dir && s_wfps.interpolated % 120 == 0;
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
  WarioRun(s_wfps.prologue);
  g_wario_view_correction_active = true;
  xf_state_manager.SetProjectionChanged();
  WarioRun(s_wfps.commands);
  g_vertex_manager->Flush();
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
    WarioSnapshotFrameStart();
    s_wfps.frame_valid = true;
    return;
  }
  if (!s_wfps.frame_valid || static_cast<OpcodeDecoder::Opcode>(data[0]) ==
                                 OpcodeDecoder::Opcode::GX_CMD_CALL_DL)
    return;
  s_wfps.commands.insert(s_wfps.commands.end(), data, data + size);
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
    replace(video / "TextureCacheBase.cpp", TC_GLOBALS_OLD, TC_GLOBALS_NEW)
    replace(video / "TextureCacheBase.cpp", TC_CAPTURE_OLD, TC_CAPTURE_NEW)
    replace(video / "TextureCacheBase.cpp", TC_GUARD_OLD, TC_GUARD_NEW)
    replace(video / "Present.h", PRESENT_DECL_OLD, PRESENT_DECL_NEW)
    replace(video / "Present.cpp", PRESENT_INCLUDE_OLD, PRESENT_INCLUDE_NEW)
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
