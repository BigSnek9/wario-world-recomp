"""Optional display enhancements: auto render resolution and any-aspect (2026-10-26).

Both are off unless the playtest launcher asks for them; the accuracy baseline
(native 1x, 4:3, unmodified guest) is unchanged.

1. config.ini `resolution=auto` -> no forced EFB scale; GFX.ini
   InternalResolution=0 then selects Dolphin's automatic (window-size) scale.
2. MODERNGEKKO_WARIO_ASPECT=auto | <w>:<h> | <number>: after every presented
   frame the runtime writes the target aspect into Wario World's camera aspect
   default (0x801FE5B0, HC-0001), the 2D half-width (0x801FE6CC = 320*a/(4/3),
   HC-0007) and the live camera block ([0x801FDA50]+0x44, CAM-002) when that
   block looks like a camera (aspect and FOV fields in range). The per-frame
   camera update rebuilds projection and culling planes from +0x44 (CAM-004),
   so resizing the window re-adapts immediately. "auto" follows the
   presentation backbuffer (use with AspectRatio=Stretch); fixed ratios pair
   with AspectRatio=Custom.
"""

INCLUDE_OLD = '#include "VideoCommon/FrameDumper.h"\n'
INCLUDE_NEW = '#include "VideoCommon/FrameDumper.h"\n#include "VideoCommon/Present.h"\n'

FUNC_ANCHOR = "std::optional<RuntimeError> WriteAutomationMemory(u32 address,"
FUNC_NEW = '''// Optional Wario World any-aspect enhancement (scripts/tool_fix_wario_aspect.py).
void UpdateWarioAspect()
{
  static const std::string mode = [] {
    const char *value = std::getenv("MODERNGEKKO_WARIO_ASPECT");
    return std::string(value ? value : "");
  }();
  if (mode.empty() || mode == "off")
    return;
  static const float fixed_aspect = [] {
    const std::string text = mode;
    const auto colon = text.find(':');
    if (colon != std::string::npos)
    {
      const float width = std::strtof(text.substr(0, colon).c_str(), nullptr);
      const float height = std::strtof(text.substr(colon + 1).c_str(), nullptr);
      return height > 0.0f ? width / height : 0.0f;
    }
    return std::strtof(text.c_str(), nullptr);
  }();
  float aspect = fixed_aspect;
  if (mode == "auto")
  {
    if (!g_presenter)
      return;
    const int width = g_presenter->GetBackbufferWidth();
    const int height = g_presenter->GetBackbufferHeight();
    if (width <= 0 || height <= 0)
      return;
    aspect = static_cast<float>(width) / static_cast<float>(height);
  }
  if (!(aspect > 0.5f && aspect < 8.0f))
    return;
  auto &memory = Core::System::GetInstance().GetMemory();
  const auto as_float = [](u32 bits) {
    float value;
    std::memcpy(&value, &bits, sizeof(value));
    return value;
  };
  const auto write_float = [&memory](u32 address, float value) {
    u32 bits;
    std::memcpy(&bits, &value, sizeof(bits));
    if (memory.Read_U32(address) != bits)
      memory.Write_U32(bits, address);
  };
  write_float(0x801FE5B0u, aspect);                          // HC-0001 camera aspect default
  write_float(0x801FE6CCu, 320.0f * aspect / (4.0f / 3.0f));  // HC-0007 2D half-width
  const u32 camera = memory.Read_U32(0x801FDA50u);            // active camera block
  if (camera >= 0x80000000u && camera < 0x81800000u - 0x100u)
  {
    const float current = as_float(memory.Read_U32(camera + 0x44u));
    const float fov = as_float(memory.Read_U32(camera + 0x48u));
    if (current > 0.5f && current < 8.0f && fov > 1.0f && fov < 170.0f)
      write_float(camera + 0x44u, aspect);
  }
}

''' + FUNC_ANCHOR

HOOK_OLD = """        m_impl->automation_state.present_count.store(info.present_count,
                                                     std::memory_order_relaxed);
      });"""
HOOK_NEW = """        m_impl->automation_state.present_count.store(info.present_count,
                                                     std::memory_order_relaxed);
        UpdateWarioAspect();
      });"""

RES_PARSE_OLD = """  // Dolphin also accepts exact raw EFB multiples even when they do not have a
  // common display label."""
RES_PARSE_NEW = """  // "auto": no forced scale; GFX.ini InternalResolution=0 follows the window.
  if (config.resolution == "auto") {
    config.dolphin_scale = 0;
    return config;
  }

  // Dolphin also accepts exact raw EFB multiples even when they do not have a
  // common display label."""

RES_USE_OLD = "  config.graphics.internal_resolution_scale = frontend_config.dolphin_scale;\n"
RES_USE_NEW = ("  if (frontend_config.dolphin_scale > 0)\n"
               "    config.graphics.internal_resolution_scale = frontend_config.dolphin_scale;\n")


CSTRING_OLD = "#include <cstdlib>\n"
CSTRING_NEW = "#include <cstdlib>\n#include <cstring>\n"


def apply(replace, runtime):
    source = runtime / "src/runtime/dolphin_runtime.cpp"
    replace(source, INCLUDE_OLD, INCLUDE_NEW)
    replace(source, CSTRING_OLD, CSTRING_NEW)
    replace(source, FUNC_ANCHOR, FUNC_NEW)
    replace(source, HOOK_OLD, HOOK_NEW)
    replace(runtime / "tools/frontend_config.cpp", RES_PARSE_OLD, RES_PARSE_NEW)
    replace(runtime / "tools/moderngekko_run.cpp", RES_USE_OLD, RES_USE_NEW)
