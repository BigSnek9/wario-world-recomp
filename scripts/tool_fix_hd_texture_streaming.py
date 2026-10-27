"""Stream HD texture uploads across frames (2026-10-27).

Dolphin decodes HD (custom) textures on its asset loader threads, but creates the GPU texture and
uploads every level on the emulation thread the first time the game draws it. The player's pack
has 150 textures of 4096x4096 (64 MB each before mipmaps, 9.7 GB decoded in total), so a scene
that shows many new textures at once (the hub, a charge dash) stalled the game: hidden hub run at
4K with the pack, min speed 0.838 and 14 slow samples, against 1.0 and none without it.

Now each frame uploads at most MODERNGEKKO_HD_UPLOAD_MB (default 32) of HD texture data, and
always at least one texture. A texture over the budget is drawn with its original texture for now
and its entry keeps an old load time, so TextureCacheBase::Load's DidLinkedAssetsChange check
recreates it with the HD data on a later frame. Without HD textures nothing changes.
"""

BUDGET_OLD = "void TextureCacheBase::OnFrameEnd()\n{\n"
BUDGET_NEW = """// HD texture upload budget (scripts/tool_fix_hd_texture_streaming.py): bytes and textures uploaded
// in the current frame, reset at the end of each frame.
static u64 s_wario_hd_upload_bytes = 0;
static u32 s_wario_hd_uploads = 0;
u64 g_wario_hd_deferred = 0;

static u64 WarioHdUploadBudget()
{
  static const u64 budget = [] {
    const char* value = std::getenv("MODERNGEKKO_HD_UPLOAD_MB");
    const long long mb = value ? std::strtoll(value, nullptr, 10) : 32;
    return static_cast<u64>(std::max(1LL, mb)) << 20;
  }();
  return budget;
}

void TextureCacheBase::OnFrameEnd()
{
  s_wario_hd_upload_bytes = 0;
  s_wario_hd_uploads = 0;
"""

DEFER_OLD = "      skip_texture_dump = true;\n"
DEFER_NEW = """      skip_texture_dump = true;
      // Upload budget: past it, keep the original texture this frame and stay "out of date" so
      // the HD version is created on a later frame instead of stalling this one.
      if (custom_texture_data)
      {
        u64 bytes = 0;
        for (const auto& level : custom_texture_data->m_slices[0].m_levels)
          bytes += level.data.size();
        if (s_wario_hd_uploads > 0 && s_wario_hd_upload_bytes + bytes > WarioHdUploadBudget())
        {
          custom_texture_data = nullptr;
          load_time = {};
          g_wario_hd_deferred++;
        }
        else
        {
          s_wario_hd_uploads++;
          s_wario_hd_upload_bytes += bytes;
        }
      }
"""


# Size cap (2026-10-27): even one 4096x4096 upload per frame (64 MB + copy) stalled the hub for ~15
# s after entering it (player's play-tracker log: speed 0.6-0.8). Single-image PNG textures larger
# than the cap are halved (2x2 box filter) on the asset loader threads, right after decoding, so
# the emulation thread only ever uploads the smaller image. Textures that ship their own mip chain
# (_mip files) are left alone. MODERNGEKKO_HD_MAX_SIZE (pixels; 0 = full size, the default: a hidden
# fresh-hub test at 4K with the full pack showed no slowdown either way) sets the start value,
# the in-game menu sets VideoCommon::g_wario_hd_max_size (applies to textures loaded afterwards).
CAP_INCLUDE_OLD = "#include <algorithm>\n\n#include \"Common/FileUtil.h\"\n"
CAP_INCLUDE_NEW = "#include <algorithm>\n#include <atomic>\n#include <cstdlib>\n\n#include \"Common/FileUtil.h\"\n"

CAP_HELPER_OLD = "namespace VideoCommon\n{\nnamespace\n{\n"
CAP_HELPER_NEW = """namespace VideoCommon
{
// Largest HD texture side in pixels; 0 = full size (scripts/tool_fix_hd_texture_streaming.py).
std::atomic<int> g_wario_hd_max_size{[] {
  const char* value = std::getenv("MODERNGEKKO_HD_MAX_SIZE");
  return value ? std::atoi(value) : 0;
}()};
namespace
{
void WarioCapTextureSize(CustomTextureData::ArraySlice::Level* level)
{
  const int cap = g_wario_hd_max_size.load(std::memory_order_relaxed);
  if (cap <= 0 || level->format != AbstractTextureFormat::RGBA8 || level->row_length != level->width)
    return;
  while ((level->width > static_cast<u32>(cap) || level->height > static_cast<u32>(cap)) &&
         level->width % 2 == 0 && level->height % 2 == 0)
  {
    const u32 width = level->width / 2;
    const u32 height = level->height / 2;
    Common::UniqueBuffer<u8> half(static_cast<size_t>(width) * height * 4);
    const u8* source = level->data.data();
    const size_t stride = static_cast<size_t>(level->width) * 4;
    for (u32 y = 0; y < height; ++y)
    {
      const u8* row0 = source + stride * (y * 2);
      const u8* row1 = row0 + stride;
      u8* out = half.data() + static_cast<size_t>(y) * width * 4;
      for (u32 x = 0; x < width; ++x)
      {
        for (int c = 0; c < 4; ++c)
        {
          const u32 sum = row0[x * 8 + c] + row0[x * 8 + 4 + c] + row1[x * 8 + c] + row1[x * 8 + 4 + c];
          out[x * 4 + c] = static_cast<u8>((sum + 2) / 4);
        }
      }
    }
    level->data = std::move(half);
    level->width = width;
    level->height = height;
    level->row_length = width;
  }
}

"""

CAP_APPLY_OLD = "    if (!LoadMips(asset_path, &slice))\n      return false;\n"
CAP_APPLY_NEW = (CAP_APPLY_OLD +
                 "\n    // HD texture size cap, on this asset loader thread (not on the emulation thread).\n"
                 "    if (slice.m_levels.size() == 1)\n"
                 "      WarioCapTextureSize(&slice.m_levels[0]);\n")


def apply(replace, runtime):
    path = runtime / "vendor/dolphin/Source/Core/VideoCommon/TextureCacheBase.cpp"
    replace(path, BUDGET_OLD, BUDGET_NEW)
    replace(path, DEFER_OLD, DEFER_NEW)
    utils = runtime / "vendor/dolphin/Source/Core/VideoCommon/Assets/TextureAssetUtils.cpp"
    replace(utils, CAP_INCLUDE_OLD, CAP_INCLUDE_NEW)
    replace(utils, CAP_HELPER_OLD, CAP_HELPER_NEW)
    replace(utils, CAP_APPLY_OLD, CAP_APPLY_NEW)
