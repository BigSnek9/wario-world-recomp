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


def apply(replace, runtime):
    path = runtime / "vendor/dolphin/Source/Core/VideoCommon/TextureCacheBase.cpp"
    replace(path, BUDGET_OLD, BUDGET_NEW)
    replace(path, DEFER_OLD, DEFER_NEW)
