"""In-game settings menu for the Wario World playtest build (2026-10-26).

Back on the controller (or Tab on the keyboard) slides a panel in over the left
half of the screen, drawn with Dolphin's ImGui overlay. It is navigated with
the controller (D-pad/stick, A select, B back/close) or the mouse. While it is
open the game sees a neutral controller.

Every option applies live and is saved to <user>/Config/WarioWorld.ini, which
is read on the first frame of the next session:
- resolution (Dolphin EFB scale; 0 = automatic, follows the window)
- aspect ratio (g_wario_aspect_target -> UpdateWarioAspect in the runtime, plus
  the host aspect mode; "Original 4:3" restores the game's own values)
- fullscreen, HD textures
- HDR output (Vulkan only) and HDR tuning: paper white (Dolphin's own setting) plus highlight
  boost / peak brightness, white level, saturation, vibrance, contrast, gamma and black level (WarioHDR.glsl,
  written to Data/Sys/Shaders; loaded only while a value differs from its default, so the
  defaults leave the picture exactly as it was)
- frame rate 60/120/180/240/auto (g_wario_fps_multiplier -> scripts/tool_fix_wario_fps.py)
- controls: GameCube-layout defaults for Xbox / DualShock, rebinding (Dolphin GCPad expressions),
  rumble on/off and strength
- volume: master (Dolphin), music, sound effects and "mute pause menu music" (game module
  exports wario_audio_*, docs/engine/AUDIO.md); cheats: jump height, walk through walls,
  super punches, unlock all stages, mark all collectables (wario_cheat_*, docs/modding/CHEATS.md);
  quit
- System: "Save bug report snapshot" (also F12: savestate + screenshot through the runner's
  automation commands), UI style, menu size, graphics backend (saved for the starter; "Restart now" leaves a
  WarioWorld.restart marker and quits), texture tools and the log (paths from the starter's
  MODERNGEKKO_WARIO_* environment variables), controls help

Config changes are queued while ImGui is locked and applied right after
OnScreenUI::Finalize, from Presenter::Present.
"""

OSUI_INCLUDE_OLD = "#include <imgui.h>\n#include <implot.h>\n"
OSUI_INCLUDE_NEW = OSUI_INCLUDE_OLD + r"""
// ---------------------------------------------------------------------------
// Wario World in-game menu (scripts/tool_fix_wario_menu.py).
#include <algorithm>
#include <atomic>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <ctime>
#include <functional>
#include <initializer_list>
#include <utility>
#include <string>
#include <vector>

#include <fmt/format.h>
#include <imgui_internal.h>

#include "AudioCommon/AudioCommon.h"
#include "Common/Config/Config.h"
#include "Common/Config/Layer.h"
#include "Common/StringUtil.h"
#include "Core/HW/GCPad.h"
#include "Core/HW/GCPadEmu.h"
#include "Core/HW/Memmap.h"
#include "InputCommon/ControllerEmu/Control/Control.h"
#include "InputCommon/ControllerEmu/ControlGroup/ControlGroup.h"
#include "InputCommon/ControllerInterface/ControllerInterface.h"
#include "InputCommon/ControllerInterface/CoreDevice.h"
#include "InputCommon/GCPadStatus.h"
#include "InputCommon/InputConfig.h"
#include "VideoCommon/AbstractFramebuffer.h"
#include "VideoCommon/PostProcessing.h"

#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <windows.h>
#include <shellapi.h>
#pragma comment(lib, "shell32.lib")
#endif

static float WarioAspectFromEnv()
{
  const char* value = std::getenv("MODERNGEKKO_WARIO_ASPECT");
  if (!value || !*value || std::strcmp(value, "off") == 0)
    return 0.0f;
  if (std::strcmp(value, "auto") == 0)
    return -1.0f;
  if (const char* colon = std::strchr(value, ':'))
  {
    const float height = std::strtof(colon + 1, nullptr);
    return height > 0.0f ? std::strtof(value, nullptr) / height : 0.0f;
  }
  return std::strtof(value, nullptr);
}

// Shared with the runtime (UpdateWarioAspect), Core/HW/GCPad.cpp and DolphinNoGUI.
std::atomic<bool> g_wario_menu_open{false};
std::atomic<float> g_wario_aspect_target{WarioAspectFromEnv()};  // 0 = 4:3, < 0 = window
std::atomic<int> g_wario_mouse_wheel{0};                         // 1/120 notches
// HDR brightness of the ImGui overlay. Dolphin draws ImGui in scRGB with 1.0 = 80 nits, so 80 is
// its own look; the menu's "Menu brightness" sets it and DrawImGui rebuilds the pipeline.
std::atomic<float> g_wario_menu_nits{80.0f};
static float s_wario_menu_nits_built = 80.0f;
// Colour format the ImGui pipeline is built for: the framebuffer DrawImGui really draws into.
// Presenter::GetBackbufferFormat() goes stale when Vulkan recreates the swap chain as RGBA16F for
// HDR switched on at runtime (VKGfx::OnSwapChainResized passes only the new size), which left the
// overlay with an SDR pipeline in HDR, so the menu brightness never applied.
static AbstractTextureFormat s_wario_imgui_format = AbstractTextureFormat::Undefined;
static AbstractTextureFormat s_wario_imgui_built_format = AbstractTextureFormat::Undefined;

static AbstractTextureFormat WarioImGuiFormat()
{
  s_wario_imgui_built_format = s_wario_imgui_format != AbstractTextureFormat::Undefined ?
                                   s_wario_imgui_format :
                                   g_presenter->GetBackbufferFormat();
  return s_wario_imgui_built_format;
}

// FramebufferShaderGen's ImGui pixel shader, with the linear (HDR) output scaled to the menu
// brightness. At 80 nits, or if Dolphin's shader text ever changes, it is returned unchanged.
static std::string WarioImGuiPixelShader(bool linear_output)
{
  std::string code = FramebufferShaderGen::GenerateImGuiPixelShader(linear_output);
  const float nits = g_wario_menu_nits.load();
  s_wario_menu_nits_built = nits;
  static const std::string gamma_to_linear = "pow(v_col0, float4(2.2f, 2.2f, 2.2f, 1.0f))";
  const size_t at = code.find(gamma_to_linear);
  if (!linear_output || nits == 80.0f || at == std::string::npos)
    return code;
  const float scale = nits / 80.0f;
  code.replace(at, gamma_to_linear.size(),
               fmt::format("({} * float4({:.4f}f, {:.4f}f, {:.4f}f, 1.0f))", gamma_to_linear, scale, scale,
                           scale));
  return code;
}
// Diagnostics: MODERNGEKKO_WARIO_MENU_TEST=<png> opens the menu after 6 s and saves the
// game picture with the menu on top once (Presenter::Present renders it offscreen).
std::atomic<bool> g_wario_menu_snapshot{false};
void* g_wario_hwnd = nullptr;
extern std::atomic<int> g_wario_fps_multiplier;  // VideoCommon/BPStructs.cpp (1 = off)
extern std::atomic<bool> g_wario_fps_objects;     // false = camera only
namespace VideoCommon
{
extern std::atomic<int> g_wario_vsync_mode;  // VideoCommon/Present.cpp: 0 = auto (on with frame gen), 1 = off
}

namespace WarioMenu
{
struct Settings
{
  int resolution = 0;  // index into kResolutionScales
  int aspect = 0;      // index into kAspects
  bool fullscreen = false;
  bool hd_textures = false;
  bool hdr = false;
  int frame_rate = 0;  // index into kFrameRates
  int motion = 1;      // 0 = camera only, 1 = camera + objects
  int vsync = 0;       // index into kVsyncKeys = VideoCommon::g_wario_vsync_mode
  int volume = 100;            // master (Dolphin)
  int music = 100;             // % loudness, game module (wario_audio_music)
  int sfx = 100;               // % loudness, game module (wario_audio_sfx)
  bool mute_pause_music = false;  // game module (wario_audio_mute_pause_music)
  bool rumble = true;
  int rumble_strength = 100;   // % (GCPad Rumble/Motor range)
  // Cheats (game module exports wario_cheat_*, docs/modding/CHEATS.md); all off = original game.
  bool noclip = false;
  bool super_punch = false;
  int jump_percent = 100;  // 100 = original jump; the game's own launch speed is scaled
  float menu_scale = 1.0f;  // 0.6 .. 1.6, on top of Windows display scaling
  int style = 0;            // index into kThemes
  int backend = 0;          // index into kBackendKeys; used by the starter at the next launch
  bool performance = false;  // dual core (Dolphin [Core] CPUThread), set by the starter at launch
  // HDR tuning (Vulkan HDR output only). Every default is the untouched picture.
  float hdr_paper_white = 203.0f;  // nits; Config::GFX_CC_HDR_PAPER_WHITE_NITS
  float hdr_menu_nits = 80.0f;     // brightness of this menu in HDR (g_wario_menu_nits)
  float hdr_peak = 1000.0f;        // nits; the highlight boost stretches up to this
  int hdr_boost = 0;               // %, 0 = off
  int hdr_saturation = 100;        // %
  int hdr_vibrance = 0;            // -100 .. 100 %: saturation weighted towards muted colours
  int hdr_white_nits = 0;          // 0 = off; 400 .. 4000: highlights roll off below this ceiling
  int hdr_contrast = 100;          // %
  float hdr_gamma = 1.0f;
  int hdr_black = 0;               // -10 (lifted) .. 10 (crushed)
};

constexpr const char* kBackendNames[] = {"OpenGL", "Vulkan"};
constexpr const char* kBackendKeys[] = {"opengl", "vulkan"};
int s_backend_running = 0;  // backend of this session
bool s_performance_running = false;  // dual core in this session

// Grading shader (Data/Sys/Shaders/WarioHDR.glsl) and whatever post shader the session had.
constexpr const char kHdrShader[] = "WarioHDR";
std::string s_saved_post_shader;

// Colour schemes. Classic keeps Dolphin's own ImGui colours (only the panel gradient, header and
// accent come from here); the others recolour every widget from a handful of base colours.
struct Theme
{
  const char* name;
  const char* key;
  bool custom;
  ImVec4 accent, bg_top, bg_bottom, frame, text, text_dim, title, primary, primary_text;
};
const ImVec4 kNoColour{0.0f, 0.0f, 0.0f, 0.0f};
const Theme kThemes[] = {
    {"Classic", "classic", false, {0.26f, 0.59f, 0.98f, 1.0f}, {0.10f, 0.11f, 0.14f, 1.0f},
     {0.04f, 0.04f, 0.05f, 1.0f}, kNoColour, kNoColour, kNoColour, {1.0f, 0.82f, 0.10f, 1.0f},
     kNoColour, kNoColour},
    {"Wario (purple & gold)", "wario", true, {1.0f, 0.80f, 0.10f, 1.0f}, {0.24f, 0.10f, 0.33f, 1.0f},
     {0.09f, 0.03f, 0.13f, 1.0f}, {0.33f, 0.17f, 0.45f, 1.0f}, {1.0f, 0.96f, 0.86f, 1.0f},
     {0.70f, 0.62f, 0.76f, 1.0f}, {1.0f, 0.84f, 0.12f, 1.0f}, {1.0f, 0.80f, 0.10f, 1.0f},
     {0.18f, 0.06f, 0.25f, 1.0f}},
    {"Midnight", "midnight", true, {0.30f, 0.85f, 0.95f, 1.0f}, {0.06f, 0.10f, 0.20f, 1.0f},
     {0.02f, 0.03f, 0.07f, 1.0f}, {0.10f, 0.16f, 0.28f, 1.0f}, {0.90f, 0.95f, 1.0f, 1.0f},
     {0.55f, 0.62f, 0.72f, 1.0f}, {0.55f, 0.92f, 1.0f, 1.0f}, {0.20f, 0.62f, 0.78f, 1.0f},
     {1.0f, 1.0f, 1.0f, 1.0f}},
    {"Garlic green", "garlic", true, {0.55f, 0.88f, 0.30f, 1.0f}, {0.07f, 0.16f, 0.09f, 1.0f},
     {0.02f, 0.06f, 0.03f, 1.0f}, {0.12f, 0.24f, 0.14f, 1.0f}, {0.94f, 0.98f, 0.90f, 1.0f},
     {0.58f, 0.70f, 0.58f, 1.0f}, {1.0f, 0.84f, 0.12f, 1.0f}, {0.48f, 0.80f, 0.26f, 1.0f},
     {0.04f, 0.12f, 0.04f, 1.0f}},
    {"Treasure red", "treasure", true, {1.0f, 0.72f, 0.22f, 1.0f}, {0.22f, 0.06f, 0.06f, 1.0f},
     {0.08f, 0.02f, 0.02f, 1.0f}, {0.34f, 0.11f, 0.10f, 1.0f}, {1.0f, 0.94f, 0.86f, 1.0f},
     {0.74f, 0.60f, 0.56f, 1.0f}, {1.0f, 0.80f, 0.25f, 1.0f}, {0.95f, 0.68f, 0.18f, 1.0f},
     {0.22f, 0.05f, 0.04f, 1.0f}},
    {"Wario yellow (light)", "yellow", true, {0.46f, 0.22f, 0.58f, 1.0f}, {0.99f, 0.93f, 0.68f, 1.0f},
     {0.94f, 0.83f, 0.50f, 1.0f}, {1.0f, 0.98f, 0.90f, 1.0f}, {0.20f, 0.10f, 0.24f, 1.0f},
     {0.50f, 0.40f, 0.42f, 1.0f}, {0.44f, 0.18f, 0.56f, 1.0f}, {0.50f, 0.28f, 0.62f, 1.0f},
     {1.0f, 0.93f, 0.62f, 1.0f}},
};

// Tabs filter the page (LB / RB or a click); All shows every section, as before tabs existed.
// Tab i > 0 shows section i only.
constexpr const char* kTabNames[] = {"All",   "Display",  "HDR",   "Motion",
                                     "Audio", "Controls", "Cheats", "System"};
constexpr int kTabCount = static_cast<int>(std::size(kTabNames));

constexpr const char* kResolutionNames[] = {"Auto (fits window)", "Native 1x (accurate)", "2x",
                                            "3x", "4x", "5x", "6x", "8x"};
constexpr int kResolutionScales[] = {0, 1, 2, 3, 4, 5, 6, 8};
constexpr const char* kFrameRateNames[] = {"Original 60 (accurate)", "120 (2x)", "180 (3x)",
                                           "240 (4x)", "Auto (match screen)"};
constexpr const char* kFrameRateKeys[] = {"60", "120", "180", "240", "auto"};
constexpr const char* kMotionNames[] = {"Camera only", "Camera + objects"};
constexpr const char* kMotionKeys[] = {"camera", "objects"};
constexpr const char* kVsyncNames[] = {"Auto (on with frame gen)", "Off"};
constexpr const char* kVsyncKeys[] = {"auto", "off"};
struct Aspect
{
  const char* name;
  const char* key;
  float ratio;  // 0 = original, < 0 = window
  int width, height;
};
constexpr Aspect kAspects[] = {{"Auto (fits window)", "auto", -1.0f, 0, 0},
                               {"Original 4:3 (accurate)", "original", 0.0f, 4, 3},
                               {"16:9", "16:9", 16.0f / 9.0f, 16, 9},
                               {"16:10", "16:10", 16.0f / 10.0f, 16, 10},
                               {"21:9", "21:9", 64.0f / 27.0f, 64, 27},
                               {"32:9", "32:9", 32.0f / 9.0f, 32, 9}};

Settings s_settings;
std::vector<std::function<void()>> s_pending;  // applied outside the ImGui lock
std::vector<std::string> s_other_lines;  // keys this menu does not know (e.g. the starter's), kept on save
bool s_loaded = false;
bool s_open = false;
float s_anim = 0.0f;  // 0 closed .. 1 open
bool s_focus_next = false;
bool s_focus_resume = false;  // nav cursor starts on Resume each time the menu opens
float s_quit_armed = 0.0f;     // seconds left to confirm Quit with a second press
int s_tab = 0;                 // index into kTabNames; back to All each time the menu opens
int s_jump = -1;               // tab whose first item gets focus on the next frame
bool s_tab_scroll = false;     // scroll to the top after a tab change
float s_pill[2] = {-1.0f, 0.0f};  // selected-tab highlight, slides between tabs
unsigned s_previous_buttons = 0;
bool s_previous_tab = false;

std::string SettingsPath()
{
  return File::GetUserPath(D_CONFIG_IDX) + "WarioWorld.ini";
}

void Save()
{
  if (FILE* file = std::fopen(SettingsPath().c_str(), "w"))
  {
    const Settings& s = s_settings;
    std::fprintf(file,
                 "# Wario World in-game menu settings (Back / Tab in game)\n"
                 "resolution=%d\naspect=%s\nfullscreen=%d\nhd_textures=%d\nhdr=%d\nframe_rate=%s\nmotion=%s\n"
                 "volume=%d\nmusic=%d\nsfx=%d\nmute_pause_music=%d\nrumble=%d\nrumble_strength=%d\n"
                 "cheat_noclip=%d\ncheat_super_punch=%d\ncheat_jump_percent=%d\n"
                 "menu_scale=%.2f\nmenu_style=%s\n"
                 "hdr_paper_white=%.0f\nhdr_peak=%.0f\nhdr_boost=%d\nhdr_saturation=%d\n"
                 "hdr_vibrance=%d\nhdr_white_nits=%d\nhdr_contrast=%d\nhdr_gamma=%.2f\nhdr_black=%d\n"
                 "hdr_menu_nits=%.0f\n"
                 "backend=%s\nvsync=%s\nperformance=%d\n",
                 kResolutionScales[s.resolution], kAspects[s.aspect].key, s.fullscreen,
                 s.hd_textures, s.hdr, kFrameRateKeys[s.frame_rate], kMotionKeys[s.motion], s.volume, s.music, s.sfx, s.mute_pause_music, s.rumble,
                 s.rumble_strength, s.noclip, s.super_punch, s.jump_percent, s.menu_scale, kThemes[s.style].key, s.hdr_paper_white, s.hdr_peak,
                 s.hdr_boost, s.hdr_saturation, s.hdr_vibrance, s.hdr_white_nits, s.hdr_contrast,
                 s.hdr_gamma, s.hdr_black,
                 s.hdr_menu_nits, kBackendKeys[s.backend], kVsyncKeys[s.vsync], s.performance);
    for (const std::string& line : s_other_lines)
      std::fprintf(file, "%s\n", line.c_str());
    std::fclose(file);
  }
}

// Returns the keys found in the settings file.
std::vector<std::string> Load()
{
  Settings& s = s_settings;
  std::vector<std::string> saved;
  // Defaults follow the values this session was started with (shown only; a fixed ratio that is
  // not a preset shows the closest one).
  const float aspect = g_wario_aspect_target.load();
  s.aspect = aspect < 0.0f ? 0 : 1;
  float closest = 1e9f;
  for (int i = 2; i < static_cast<int>(std::size(kAspects)); ++i)
  {
    if (aspect > 0.0f && std::abs(kAspects[i].ratio - aspect) < closest)
    {
      closest = std::abs(kAspects[i].ratio - aspect);
      s.aspect = i;
    }
  }
  s.frame_rate = std::clamp(g_wario_fps_multiplier.load(), 1, 4) - 1;
  s.hd_textures = Config::Get(Config::GFX_HIRES_TEXTURES);
  s.hdr = Config::Get(Config::GFX_ENHANCE_HDR_OUTPUT);
  s.hdr_paper_white = Config::Get(Config::GFX_CC_HDR_PAPER_WHITE_NITS);
  s_backend_running = Config::Get(Config::MAIN_GFX_BACKEND) == "Vulkan" ? 1 : 0;
  s_performance_running = Config::Get(Config::MAIN_CPU_THREAD);
  s.performance = s_performance_running;
  s.backend = s_backend_running;
  s.volume = Config::Get(Config::MAIN_AUDIO_VOLUME);
  const int scale = Config::Get(Config::GFX_EFB_SCALE);
  for (int i = 0; i < static_cast<int>(std::size(kResolutionScales)); ++i)
    if (kResolutionScales[i] == scale)
      s.resolution = i;
  // Diagnostics: style for menu snapshots (hidden test users have no settings file).
  if (const char* style = std::getenv("MODERNGEKKO_WARIO_MENU_STYLE"))
  {
    for (int i = 0; i < static_cast<int>(std::size(kThemes)); ++i)
      if (std::strcmp(style, kThemes[i].key) == 0)
        s.style = i;
  }
  FILE* file = std::fopen(SettingsPath().c_str(), "r");
  if (!file)
    return saved;
  char line[256];
  while (std::fgets(line, sizeof(line), file))
  {
    char* equals = std::strchr(line, '=');
    if (!equals || line[0] == '#')
      continue;
    *equals = '\0';
    std::string key = line, value = equals + 1;
    while (!value.empty() && (value.back() == '\n' || value.back() == '\r' || value.back() == ' '))
      value.pop_back();
    const int number = std::atoi(value.c_str());
    saved.push_back(key);
    if (key == "resolution")
    {
      for (int i = 0; i < static_cast<int>(std::size(kResolutionScales)); ++i)
        if (kResolutionScales[i] == number)
          s.resolution = i;
    }
    else if (key == "aspect")
    {
      for (int i = 0; i < static_cast<int>(std::size(kAspects)); ++i)
        if (value == kAspects[i].key)
          s.aspect = i;
    }
    else if (key == "fullscreen")
      s.fullscreen = number != 0;
    else if (key == "hd_textures")
      s.hd_textures = number != 0;
    else if (key == "hdr")
      s.hdr = number != 0;
    else if (key == "fps")  // before frame_rate existed: on = 120
      s.frame_rate = number != 0 ? 1 : 0;
    else if (key == "frame_rate")
    {
      for (int i = 0; i < static_cast<int>(std::size(kFrameRateKeys)); ++i)
        if (value == kFrameRateKeys[i])
          s.frame_rate = i;
    }
    else if (key == "motion")
      s.motion = value == "camera" ? 0 : 1;
    else if (key == "music")
      s.music = std::clamp(number, 0, 100);
    else if (key == "sfx")
      s.sfx = std::clamp(number, 0, 100);
    else if (key == "mute_pause_music")
      s.mute_pause_music = number != 0;
    else if (key == "rumble")
      s.rumble = number != 0;
    else if (key == "rumble_strength")
      s.rumble_strength = std::clamp(number, 0, 100);
    else if (key == "volume")
      s.volume = std::clamp(number, 0, 100);
    else if (key == "cheat_noclip")
      s.noclip = number != 0;
    else if (key == "cheat_super_punch")
      s.super_punch = number != 0;
    else if (key == "cheat_jump_percent")
      s.jump_percent = std::clamp(number, 100, 500);
    else if (key == "moon_jump" || key == "moon_speed")
    {
      // The old levitation cheat, replaced by the module's real jump height; dropped.
    }
    else if (key == "menu_scale")
      s.menu_scale = std::clamp(static_cast<float>(std::atof(value.c_str())), 0.6f, 1.6f);
    else if (key == "hdr_paper_white")
      s.hdr_paper_white = std::clamp(static_cast<float>(std::atof(value.c_str())), 80.0f, 500.0f);
    else if (key == "hdr_peak")
      s.hdr_peak = std::clamp(static_cast<float>(std::atof(value.c_str())), 400.0f, 4000.0f);
    else if (key == "hdr_boost")
      s.hdr_boost = std::clamp(number, 0, 100);
    else if (key == "hdr_saturation")
      s.hdr_saturation = std::clamp(number, 0, 200);
    else if (key == "hdr_vibrance")
      s.hdr_vibrance = std::clamp(number, -100, 100);
    else if (key == "hdr_white_nits")
      s.hdr_white_nits = number < 400 ? 0 : std::min(number, 4000);
    else if (key == "hdr_warmth")
    {
      // Warmth was removed (2026-10-27); dropped on the next save.
    }
    else if (key == "hdr_contrast")
      s.hdr_contrast = std::clamp(number, 50, 150);
    else if (key == "hdr_gamma")
      s.hdr_gamma = std::clamp(static_cast<float>(std::atof(value.c_str())), 0.7f, 1.3f);
    else if (key == "hdr_black")
      s.hdr_black = std::clamp(number, -10, 10);
    else if (key == "hdr_menu_nits")
      s.hdr_menu_nits = std::clamp(static_cast<float>(std::atof(value.c_str())), 80.0f, 400.0f);
    else if (key == "vsync")
      s.vsync = value == "off" ? 1 : 0;
    else if (key == "performance")
      s.performance = number != 0;
    else if (key == "backend")
      s.backend = value == "vulkan" ? 1 : 0;
    else if (key == "menu_style")
    {
      for (int i = 0; i < static_cast<int>(std::size(kThemes)); ++i)
        if (value == kThemes[i].key)
          s.style = i;
    }
    else if (key != "fps")  // fps: replaced by frame_rate
      s_other_lines.push_back(key + "=" + value);
  }
  std::fclose(file);
  return saved;
}

// Config::SetCurrent for per-frame code (pending changes, HDR grading): while the core shuts down
// the CurrentRun layer is removed and SetCurrent would dereference null (the exit crash in
// Config::Layer::Set). Holding the layer also covers a removal on the host thread mid-write.
template <typename InfoT, typename ValueT>
void SetRunning(const Config::Info<InfoT>& info, const ValueT& value)
{
  if (const std::shared_ptr<Config::Layer> layer = Config::GetLayer(Config::LayerType::CurrentRun))
  {
    if (layer->Set(info, value))
      Config::OnConfigChanged();
  }
}

bool IsVulkan()
{
  return Config::Get(Config::MAIN_GFX_BACKEND) == "Vulkan";
}

void QueueResolution()
{
  const int scale = kResolutionScales[s_settings.resolution];
  s_pending.push_back([scale] { SetRunning(Config::GFX_EFB_SCALE, scale); });
}

void QueueAspect()
{
  const Aspect aspect = kAspects[s_settings.aspect];
  s_pending.push_back([aspect] {
    g_wario_aspect_target.store(aspect.ratio);
    if (aspect.ratio < 0.0f)
    {
      SetRunning(Config::GFX_ASPECT_RATIO, AspectMode::Stretch);
    }
    else if (aspect.ratio == 0.0f)
    {
      SetRunning(Config::GFX_ASPECT_RATIO, AspectMode::ForceStandard);
    }
    else
    {
      SetRunning(Config::GFX_CUSTOM_ASPECT_RATIO_WIDTH, aspect.width);
      SetRunning(Config::GFX_CUSTOM_ASPECT_RATIO_HEIGHT, aspect.height);
      // Absolute ratio: AspectMode::Custom is relative and keeps the VI analog-width correction
      // (a 640-wide XFB is not exactly 4:3), which left thin side bars at 16:9 on a 16:9 screen.
      SetRunning(Config::GFX_ASPECT_RATIO, AspectMode::CustomStretch);
    }
  });
}

void QueueHd()
{
  const bool hd = s_settings.hd_textures;
  s_pending.push_back([hd] { SetRunning(Config::GFX_HIRES_TEXTURES, hd); });
}

void QueueHdr()
{
  const bool hdr = s_settings.hdr && IsVulkan();
  s_pending.push_back([hdr] { SetRunning(Config::GFX_ENHANCE_HDR_OUTPUT, hdr); });
}

void QueuePaperWhite()
{
  const float nits = s_settings.hdr_paper_white;
  s_pending.push_back([nits] { SetRunning(Config::GFX_CC_HDR_PAPER_WHITE_NITS, nits); });
}

void ResetHdr()
{
  const Settings defaults;
  Settings& s = s_settings;
  s.hdr_paper_white = Config::GFX_CC_HDR_PAPER_WHITE_NITS.GetDefaultValue();
  s.hdr_peak = defaults.hdr_peak;
  s.hdr_boost = defaults.hdr_boost;
  s.hdr_saturation = defaults.hdr_saturation;
  s.hdr_vibrance = defaults.hdr_vibrance;
  s.hdr_white_nits = defaults.hdr_white_nits;
  s.hdr_contrast = defaults.hdr_contrast;
  s.hdr_gamma = defaults.hdr_gamma;
  s.hdr_black = defaults.hdr_black;
  s.hdr_menu_nits = defaults.hdr_menu_nits;
  g_wario_menu_nits.store(s.hdr_menu_nits);
  QueuePaperWhite();
}

bool HdrGradingActive()
{
  const Settings& s = s_settings;
  return s.hdr_boost != 0 || s.hdr_saturation != 100 || s.hdr_vibrance != 0 || s.hdr_white_nits != 0 ||
         s.hdr_contrast != 100 || std::abs(s.hdr_gamma - 1.0f) > 0.004f || s.hdr_black != 0;
}

// Every frame, from Presenter::Present: the grading shader is the post shader only while HDR
// output is on and a grading value is not at its default (otherwise the session's own post shader,
// normally none, so the default picture never goes through an extra pass). Its options are pushed
// each frame, which also covers the frame the shader (re)loads with its file defaults.
void ApplyHdrGrading()
{
  const Settings& s = s_settings;
  if (!Config::GetLayer(Config::LayerType::CurrentRun))
    return;  // shutting down
  const bool want = s_loaded && s.hdr && IsVulkan() && HdrGradingActive();
  const std::string current = Config::Get(Config::GFX_ENHANCE_POST_SHADER);
  if (want && current != kHdrShader)
  {
    s_saved_post_shader = current;
    SetRunning(Config::GFX_ENHANCE_POST_SHADER, std::string(kHdrShader));
  }
  else if (!want && current == kHdrShader)
  {
    SetRunning(Config::GFX_ENHANCE_POST_SHADER, s_saved_post_shader);
  }
  if (!want || !g_presenter || !g_presenter->GetPostProcessor())
    return;
  VideoCommon::PostProcessingConfiguration* config = g_presenter->GetPostProcessor()->GetConfig();
  if (config->GetShader() != kHdrShader)
    return;
  const auto set = [config](const char* name, float value) {
    if (config->GetOptions().count(name) != 0)
      config->SetOptionf(name, 0, value);
  };
  set("WW_PEAK_NITS", s.hdr_peak);
  set("WW_HIGHLIGHTS", s.hdr_boost / 100.0f);
  set("WW_SATURATION", s.hdr_saturation / 100.0f);
  set("WW_VIBRANCE", s.hdr_vibrance / 100.0f);
  set("WW_WHITE_NITS", static_cast<float>(s.hdr_white_nits));
  set("WW_CONTRAST", s.hdr_contrast / 100.0f);
  set("WW_GAMMA", s.hdr_gamma);
  set("WW_BLACK", s.hdr_black / 100.0f);
}

void QueueVolume()
{
  const int volume = s_settings.volume;
  s_pending.push_back([volume] {
    SetRunning(Config::MAIN_AUDIO_VOLUME, volume);
    AudioCommon::UpdateSoundStream(Core::System::GetInstance());
  });
}

// Auto: as many frames per game frame as the screen shows (60 Hz -> 1, 120/144 -> 2,
// 180 -> 3, 240+ -> 4), for the monitor the game window is on.
int AutoMultiplier()
{
#ifdef _WIN32
  if (g_wario_hwnd)
  {
    MONITORINFOEXW info{};
    info.cbSize = sizeof(info);
    if (GetMonitorInfoW(MonitorFromWindow(static_cast<HWND>(g_wario_hwnd), MONITOR_DEFAULTTONEAREST),
                        &info))
    {
      DEVMODEW mode{};
      mode.dmSize = sizeof(mode);
      if (EnumDisplaySettingsW(info.szDevice, ENUM_CURRENT_SETTINGS, &mode) &&
          mode.dmDisplayFrequency > 1)
      {
        return std::clamp(static_cast<int>(mode.dmDisplayFrequency / 59.94 + 0.05), 1, 4);
      }
    }
  }
#endif
  return 2;
}

void QueueFps()
{
  const int choice = s_settings.frame_rate;
  g_wario_fps_multiplier.store(choice == 4 ? AutoMultiplier() : choice + 1);
  g_wario_fps_objects.store(s_settings.motion == 1);
}

// The game window's real state. PlatformWin32::ToggleFullscreen (F11, Alt+Enter, its own menu)
// strips WS_OVERLAPPEDWINDOW, so a window without a caption is fullscreen.
bool WindowFullscreen()
{
#ifdef _WIN32
  return g_wario_hwnd &&
         (GetWindowLongW(static_cast<HWND>(g_wario_hwnd), GWL_STYLE) & WS_CAPTION) == 0;
#else
  return false;
#endif
}

float s_fullscreen_wait = 0.0f;  // seconds the checkbox shows the request while the window catches up

// Absolute, not a toggle: F11 only goes out when the window is not already in the wanted state.
// (A toggle let the saved setting and the real window disagree, which inverted the checkbox when
// the starter had already launched fullscreen.)
void SetFullscreen(bool fullscreen)
{
#ifdef _WIN32
  if (g_wario_hwnd && fullscreen != WindowFullscreen())
  {
    PostMessageW(static_cast<HWND>(g_wario_hwnd), WM_KEYDOWN, VK_F11, 0);
    s_fullscreen_wait = 0.5f;
  }
#endif
}

void Quit()
{
#ifdef _WIN32
  if (g_wario_hwnd)
    PostMessageW(static_cast<HWND>(g_wario_hwnd), WM_CLOSE, 0, 0);
#endif
}

// Restart now: the starter relaunches the runner when it finds this marker after the exit.
void Restart()
{
  if (FILE* marker = std::fopen((File::GetUserPath(D_CONFIG_IDX) + "WarioWorld.restart").c_str(), "w"))
    std::fclose(marker);
  Save();
  Quit();
}

// Tools: paths and commands come from the starter's environment; a missing variable hides its
// button.
std::string EnvUtf8(const char* name)
{
#ifdef _WIN32
  const std::wstring wide_name = UTF8ToWString(name);
  const DWORD size = GetEnvironmentVariableW(wide_name.c_str(), nullptr, 0);
  if (size <= 1)
    return {};
  std::wstring value(size, L'\0');
  value.resize(GetEnvironmentVariableW(wide_name.c_str(), value.data(), size));
  return WStringToUTF8(value);
#else
  const char* value = std::getenv(name);
  return value ? value : "";
#endif
}

// Opens a folder (created first) or file with its Windows handler. Explorer comes forward over the
// game, as Windows decides.
void OpenPath(const std::string& path, bool folder)
{
#ifdef _WIN32
  if (folder)
    File::CreateFullPath(path + "/");
  ShellExecuteW(static_cast<HWND>(g_wario_hwnd), L"open", UTF8ToWString(path).c_str(), nullptr,
                nullptr, SW_SHOWNORMAL);
#endif
}

// Texture extraction runs as a hidden child process; the menu polls it every frame.
enum class ExtractState
{
  Idle,
  Running,
  Finished,
  Failed,
};
ExtractState s_extract_state = ExtractState::Idle;
unsigned long s_extract_code = 0;
void* s_extract_process = nullptr;

void StartExtract(const std::string& command)
{
#ifdef _WIN32
  std::wstring line = UTF8ToWString(command);
  STARTUPINFOW startup{};
  startup.cb = sizeof(startup);
  PROCESS_INFORMATION info{};
  if (!CreateProcessW(nullptr, line.data(), nullptr, nullptr, FALSE,
                      CREATE_NO_WINDOW | BELOW_NORMAL_PRIORITY_CLASS, nullptr, nullptr, &startup,
                      &info))
  {
    s_extract_state = ExtractState::Failed;
    s_extract_code = GetLastError();
    return;
  }
  CloseHandle(info.hThread);
  s_extract_process = info.hProcess;
  s_extract_state = ExtractState::Running;
#endif
}

void PollExtract()
{
#ifdef _WIN32
  if (s_extract_state != ExtractState::Running ||
      WaitForSingleObject(static_cast<HANDLE>(s_extract_process), 0) != WAIT_OBJECT_0)
  {
    return;
  }
  DWORD code = 1;
  GetExitCodeProcess(static_cast<HANDLE>(s_extract_process), &code);
  CloseHandle(static_cast<HANDLE>(s_extract_process));
  s_extract_process = nullptr;
  s_extract_code = code;
  s_extract_state = code == 0 ? ExtractState::Finished : ExtractState::Failed;
#endif
}

// XInput without linking it: any of the four pads.
struct PadState
{
  unsigned buttons = 0;
  float lx = 0.0f, ly = 0.0f;
};

PadState ReadPads()
{
  PadState state;
#ifdef _WIN32
  struct XInputGamepad
  {
    WORD buttons;
    BYTE left_trigger, right_trigger;
    SHORT lx, ly, rx, ry;
  };
  struct XInputState
  {
    DWORD packet;
    XInputGamepad gamepad;
  };
  using GetStateFn = DWORD(WINAPI*)(DWORD, XInputState*);
  static const GetStateFn get_state = [] {
    for (const wchar_t* name : {L"xinput1_4.dll", L"xinput1_3.dll", L"xinput9_1_0.dll"})
      if (HMODULE module = LoadLibraryW(name))
        return reinterpret_cast<GetStateFn>(GetProcAddress(module, "XInputGetState"));
    return GetStateFn{};
  }();
  if (!get_state)
    return state;
  for (DWORD pad = 0; pad < 4; ++pad)
  {
    XInputState raw{};
    if (get_state(pad, &raw) != 0)
      continue;
    state.buttons |= raw.gamepad.buttons;
    const float lx = raw.gamepad.lx / 32767.0f, ly = raw.gamepad.ly / 32767.0f;
    if (std::abs(lx) > std::abs(state.lx))
      state.lx = lx;
    if (std::abs(ly) > std::abs(state.ly))
      state.ly = ly;
  }
#endif
  return state;
}

constexpr unsigned PAD_UP = 0x0001, PAD_DOWN = 0x0002, PAD_LEFT = 0x0004, PAD_RIGHT = 0x0008,
                   PAD_BACK = 0x0020, PAD_LB = 0x0100, PAD_RB = 0x0200, PAD_A = 0x1000,
                   PAD_B = 0x2000;

bool WindowFocused()
{
#ifdef _WIN32
  return g_wario_hwnd && GetForegroundWindow() == static_cast<HWND>(g_wario_hwnd);
#else
  return true;
#endif
}

bool KeyDown(int key)
{
#ifdef _WIN32
  return WindowFocused() && (GetAsyncKeyState(key) & 0x8000) != 0;
#else
  return false;
#endif
}

// Like ImGui::SetKeyboardFocusHere(), but only moves the nav cursor to the next item:
// SetKeyboardFocusHere also activates it, which opens a slider's text entry.
void FocusNextItem()
{
  ImGuiContext& g = *GImGui;
  ImGuiWindow* window = g.CurrentWindow;
  if (g.DragDropActive || g.MovingWindow != nullptr)
    return;
  ImGui::SetNavWindow(window);
  const ImGuiScrollFlags scroll =
      window->Appearing ? ImGuiScrollFlags_KeepVisibleEdgeX | ImGuiScrollFlags_AlwaysCenterY :
                          ImGuiScrollFlags_KeepVisibleEdgeX | ImGuiScrollFlags_KeepVisibleEdgeY;
  ImGui::NavMoveRequestSubmit(ImGuiDir_None, ImGuiDir_Down,
                              ImGuiNavMoveFlags_IsTabbing | ImGuiNavMoveFlags_FocusApi |
                                  ImGuiNavMoveFlags_NoSetNavCursorVisible,
                              scroll);
  g.NavTabbingDir = 1;
  g.NavTabbingCounter = 1;
}

#ifdef _WIN32
// An s32 exported by the recompiled game module, or null.
volatile s32* WarioModuleS32(const char* name)
{
  HMODULE module = GetModuleHandleW(L"gGWWE01_recomp.dll");
  return module ? reinterpret_cast<volatile s32*>(GetProcAddress(module, name)) : nullptr;
}
#endif
bool s_audio_exports = false;  // the game module has the wario_audio_* controls
bool s_cheat_exports = false;  // the game module has the wario_cheat_* controls
// One-shot cheats: the menu writes 1, the module sets 2 once applied (with a save loaded).
volatile s32* s_cheat_unlock = nullptr;
volatile s32* s_cheat_collect = nullptr;

// ---- Bug report snapshot: savestate + screenshot of exactly what the player sees ----
// Queued as commands for the runner's automation folder (the same files launcher/play_tracker.py
// writes): written to a temporary file, then renamed into <control>/commands/ with a millisecond
// prefix so they sort after earlier ones. The starter sets MODERNGEKKO_WARIO_CONTROL_DIR and
// MODERNGEKKO_WARIO_REPORT_DIR; without a report folder the button is hidden.
std::string AutomationDir()
{
  std::string dir = EnvUtf8("MODERNGEKKO_WARIO_CONTROL_DIR");
#ifdef _WIN32
  if (dir.empty())
  {
    // Hidden test runs: the runner's own --automation-dir argument.
    int count = 0;
    if (LPWSTR* args = CommandLineToArgvW(GetCommandLineW(), &count))
    {
      for (int i = 0; i + 1 < count; ++i)
      {
        if (std::wcscmp(args[i], L"--automation-dir") == 0)
          dir = WStringToUTF8(args[i + 1]);
      }
      LocalFree(args);
    }
  }
#endif
  return dir;
}

bool QueueAutomation(const std::string& dir, long long stamp, const char* tag, const char* command,
                     const std::string& path)
{
  const std::string commands = dir + "/commands/";
  File::CreateFullPath(commands);
  const std::string pending = dir + "/wario-menu-" + tag + ".tmp";
  return File::WriteStringToFile(pending, fmt::format("command={}\npath={}\n", command, path)) &&
         File::Rename(pending, commands + fmt::format("{:016d}-menu-{}.txt", stamp, tag));
}

std::string s_toast;
float s_toast_time = 0.0f;

void Toast(std::string text)
{
  s_toast = std::move(text);
  s_toast_time = 3.0f;
}

void SaveReportSnapshot()
{
  static const std::string control = AutomationDir();
  static const std::string reports = EnvUtf8("MODERNGEKKO_WARIO_REPORT_DIR");
  if (control.empty() || reports.empty())
    return;
  File::CreateFullPath(reports + "/");
  const auto now = std::chrono::system_clock::now();
  const std::time_t seconds = std::chrono::system_clock::to_time_t(now);
  std::tm local{};
#ifdef _WIN32
  localtime_s(&local, &seconds);
#else
  localtime_r(&seconds, &local);
#endif
  char name[32];
  std::strftime(name, sizeof(name), "report-%H%M%S", &local);
  const std::string base = reports + "/" + name;
  const long long stamp =
      std::chrono::duration_cast<std::chrono::milliseconds>(now.time_since_epoch()).count();
  const bool ok = QueueAutomation(control, stamp, "report-state", "save_state", base + ".sav") &&
                  QueueAutomation(control, stamp + 1, "report-shot", "screenshot", base + ".png");
  Toast(ok ? fmt::format("Snapshot saved: {}", name) : "Snapshot failed (automation folder)");
}

bool ReportSnapshotAvailable()
{
  static const bool available =
      !AutomationDir().empty() && !EnvUtf8("MODERNGEKKO_WARIO_REPORT_DIR").empty();
  return available;
}

// ---- Controls: GameCube pad 1 in Dolphin's GCPad config (Config/GCPadNew.ini) ----
// The menu writes simple bindings: one or more pad controls on every XInput slot and on every
// connected SDL gamepad (DualShock / DualSense / others, by position), plus one keyboard key.
// Expressions it did not write (anything beyond backtick terms, "|", parentheses and "> 0.9")
// are never rewritten. Defaults follow the GameCube's physical layout (docs/CONTROLS.md,
// scripts/configure_controls.py builds the same text).
constexpr char kKeyboardDevice[] = "DInput/0/Keyboard Mouse";

struct PadControl
{
  PadGroup group;
  const char* name;   // Dolphin control name inside the group
  const char* label;  // rebindable from the menu; nullptr = sticks, analog triggers, rumble
  const char* pads;   // default XInput controls, ';'-separated
  const char* key;    // default keyboard key
};
const PadControl kPadControls[] = {
    {PadGroup::Buttons, "A", "A  jump", "Button A", "X"},
    {PadGroup::Buttons, "B", "B  punch", "Button X", "Z"},
    {PadGroup::Buttons, "X", "X", "Button B", "C"},
    {PadGroup::Buttons, "Y", "Y", "Button Y", "S"},
    {PadGroup::Buttons, "Z", "Z  coins", "Shoulder R", "D"},
    {PadGroup::Buttons, "Start", "Start", "Start", "RETURN"},
    {PadGroup::Triggers, "L", "L  coins", "Shoulder L;Trigger L", "Q"},
    {PadGroup::Triggers, "R", "R  dash", "Trigger R", "W"},
    {PadGroup::DPad, "Up", "D-pad up", "Pad N", "T"},
    {PadGroup::DPad, "Down", "D-pad down", "Pad S", "G"},
    {PadGroup::DPad, "Left", "D-pad left", "Pad W", "F"},
    {PadGroup::DPad, "Right", "D-pad right", "Pad E", "H"},
    {PadGroup::Triggers, "L-Analog", nullptr, "Trigger L", "Q"},
    {PadGroup::Triggers, "R-Analog", nullptr, "Trigger R", "W"},
    {PadGroup::MainStick, "Up", nullptr, "Left Y+", "UP"},
    {PadGroup::MainStick, "Down", nullptr, "Left Y-", "DOWN"},
    {PadGroup::MainStick, "Left", nullptr, "Left X-", "LEFT"},
    {PadGroup::MainStick, "Right", nullptr, "Left X+", "RIGHT"},
    {PadGroup::CStick, "Up", nullptr, "Right Y+", "I"},
    {PadGroup::CStick, "Down", nullptr, "Right Y-", "K"},
    {PadGroup::CStick, "Left", nullptr, "Right X-", "J"},
    {PadGroup::CStick, "Right", nullptr, "Right X+", "L"},
    {PadGroup::Rumble, "Motor", nullptr, "Motor L;Motor R", ""},
};

// Digital GameCube inputs take a trigger only when it is pressed nearly fully (like the GC's
// L / R click); sticks, analog triggers and the motor use the value as is.
bool IsDigital(const PadControl& control)
{
  return control.group == PadGroup::Buttons || control.group == PadGroup::DPad ||
         (control.group == PadGroup::Triggers && std::strchr(control.name, '-') == nullptr);
}

// SDL names face buttons by position; XInput by Xbox label (same position).
std::string ToSdl(const std::string& name)
{
  if (name == "Button A")
    return "Button S";
  if (name == "Button B")
    return "Button E";
  if (name == "Button X")
    return "Button W";
  if (name == "Button Y")
    return "Button N";
  return name;
}

std::string FromSdl(const std::string& name)
{
  if (name == "Button S")
    return "Button A";
  if (name == "Button E")
    return "Button B";
  if (name == "Button W")
    return "Button X";
  if (name == "Button N")
    return "Button Y";
  return name;
}

struct Binding
{
  std::vector<std::string> pads;  // XInput control names
  std::string key;
};

// Reads an expression the menu could have written; false for anything else.
bool ParseBinding(const std::string& expression, Binding* binding)
{
  *binding = {};
  for (size_t at = 0; at < expression.size();)
  {
    const char c = expression[at];
    if (c != '`')
    {
      if (std::strchr(" |()>0.9", c) == nullptr)
        return false;
      ++at;
      continue;
    }
    const size_t end = expression.find('`', at + 1);
    if (end == std::string::npos)
      return false;
    const std::string term = expression.substr(at + 1, end - at - 1);
    at = end + 1;
    const size_t colon = term.find(':');
    if (colon == std::string::npos)
      return false;
    const std::string device = term.substr(0, colon), control = term.substr(colon + 1);
    std::string pad;
    if (device == kKeyboardDevice)
      binding->key = control;
    else if (device.rfind("XInput/", 0) == 0)
      pad = control;
    else if (device.rfind("SDL/", 0) == 0)
      pad = FromSdl(control);
    else
      return false;
    if (!pad.empty() &&
        std::find(binding->pads.begin(), binding->pads.end(), pad) == binding->pads.end())
    {
      binding->pads.push_back(pad);
    }
  }
  return true;
}

std::string BuildBinding(const Binding& binding, bool digital, const std::vector<std::string>& sdl)
{
  const auto join = [](const std::vector<std::string>& terms) {
    std::string text;
    for (const std::string& term : terms)
      text += (text.empty() ? "" : " | ") + term;
    return text;
  };
  std::vector<std::string> plain, click;
  for (const std::string& pad : binding.pads)
  {
    std::vector<std::string>& terms = digital && pad.rfind("Trigger ", 0) == 0 ? click : plain;
    for (int slot = 0; slot < 4; ++slot)
      terms.push_back(fmt::format("`XInput/{}/Gamepad:{}`", slot, pad));
    for (const std::string& device : sdl)
      terms.push_back(fmt::format("`{}:{}`", device, ToSdl(pad)));
  }
  std::string expression = join(plain);
  if (!click.empty())
    expression += (expression.empty() ? "" : " | ") + ("((" + join(click) + ") > 0.9)");
  if (!binding.key.empty())
    expression += (expression.empty() ? "" : " | ") + fmt::format("`{}:{}`", kKeyboardDevice, binding.key);
  return expression;
}

Binding DefaultBinding(const PadControl& control)
{
  Binding binding;
  for (const char* at = control.pads; *at;)
  {
    const char* end = std::strchr(at, ';');
    binding.pads.emplace_back(at, end ? end : at + std::strlen(at));
    at = end ? end + 1 : at + std::strlen(at);
  }
  binding.key = control.key;
  return binding;
}

ControlReference* PadReference(const PadControl& control)
{
  ControllerEmu::ControlGroup* group = Pad::GetGroup(0, control.group);
  if (!group)
    return nullptr;
  for (const auto& item : group->controls)
  {
    if (item->name == control.name)
      return item->control_ref.get();
  }
  return nullptr;
}

std::vector<std::string> s_sdl_pads;  // SDL gamepads the bindings currently include
bool s_pad_ready = false;

std::vector<std::string> ConnectedSdlPads()
{
  std::vector<std::string> pads;
  for (const std::string& device : g_controller_interface.GetAllDeviceStrings())
  {
    // Xbox pads also show up through SDL; XInput already binds them (and drives their motors).
    if (device.rfind("SDL/", 0) == 0 && device.find("Xbox") == std::string::npos &&
        device.find("XInput") == std::string::npos)
    {
      pads.push_back(device);
    }
  }
  return pads;
}

// Re-resolves the bindings and, for menu edits, writes GCPadNew.ini.
void CommitPad(bool save)
{
  if (InputConfig* config = Pad::GetConfig())
  {
    if (ControllerEmu::EmulatedController* pad = config->GetController(0))
      pad->UpdateReferences(g_controller_interface);
    if (save)
      config->SaveConfig();
  }
}

void ApplyRumble()
{
  for (const PadControl& control : kPadControls)
  {
    if (control.group != PadGroup::Rumble)
      continue;
    if (ControlReference* reference = PadReference(control))
    {
      const auto lock = ControllerEmu::EmulatedController::GetStateLock();
      reference->range = s_settings.rumble ? s_settings.rumble_strength / 100.0 : 0.0;
    }
  }
}

// Keeps every simple binding in step with the connected SDL gamepads, so a DualShock plugged in
// mid-game works with the same layout. Checked about once a second; not saved (rebuilt each run).
void SyncPadDevices(float dt)
{
  static float timer = 0.0f;
  if (s_pad_ready && (timer += dt) < 1.0f)
    return;
  timer = 0.0f;
  if (!Pad::GetConfig() || !Pad::GetConfig()->GetController(0))
    return;
  if (!s_pad_ready)
  {
    s_pad_ready = true;
    ApplyRumble();
  }
  const std::vector<std::string> sdl = ConnectedSdlPads();
  if (sdl == s_sdl_pads)
    return;
  s_sdl_pads = sdl;
  {
    const auto lock = ControllerEmu::EmulatedController::GetStateLock();
    for (const PadControl& control : kPadControls)
    {
      ControlReference* reference = PadReference(control);
      Binding binding;
      if (!reference || !ParseBinding(reference->GetExpression(), &binding))
        continue;
      const std::string expression = BuildBinding(binding, IsDigital(control), sdl);
      if (expression != reference->GetExpression())
        reference->SetExpression(expression);
    }
  }
  CommitPad(false);
}

void ResetPadDefaults()
{
  {
    const auto lock = ControllerEmu::EmulatedController::GetStateLock();
    for (const PadControl& control : kPadControls)
    {
      if (ControlReference* reference = PadReference(control))
        reference->SetExpression(BuildBinding(DefaultBinding(control), IsDigital(control), s_sdl_pads));
    }
  }
  s_settings.rumble = true;
  s_settings.rumble_strength = 100;
  ApplyRumble();
  CommitPad(true);
}

// Rebinding: Dolphin's InputDetector watches every device until one control is pressed and
// released (or 6 s pass). The menu ignores the pad while it waits.
std::unique_ptr<ciface::Core::InputDetector> s_detector;
int s_binding = -1;        // index into kPadControls being rebound
float s_binding_time = 0.0f;
std::string s_binding_note;  // result of the last attempt

void StartBinding(int index)
{
  s_binding = index;
  s_binding_time = 0.0f;
  s_binding_note.clear();
  s_detector = std::make_unique<ciface::Core::InputDetector>();
  const auto lock = ControllerEmu::EmulatedController::GetStateLock();
  s_detector->Start(g_controller_interface, g_controller_interface.GetAllDeviceStrings());
}

void PollBinding(float dt)
{
  if (!s_detector)
    return;
  s_binding_time += dt;
  using namespace std::chrono_literals;
  s_detector->Update(6000ms, 0ms, 6000ms);
  if (!s_detector->IsComplete())
    return;
  const auto results = s_detector->TakeResults();
  s_detector.reset();
  const PadControl& control = kPadControls[s_binding];
  s_binding = -1;
  for (const auto& detection : results)
  {
    if (!detection.device || !detection.input)
      continue;
    const std::string source = detection.device->GetSource();
    const std::string name = detection.input->GetName();
    // Back / Guide / Tab stay reserved for this menu; mouse input is never a game control.
    if (name == "Back" || name == "Guide" || name == "TAB" || name.rfind("Click", 0) == 0 ||
        name.rfind("Cursor", 0) == 0 || name.rfind("Axis", 0) == 0)
    {
      continue;
    }
    const bool keyboard = detection.device->GetQualifiedName() == kKeyboardDevice;
    if (!keyboard && source != "XInput" && source != "SDL")
      continue;
    ControlReference* reference = PadReference(control);
    if (!reference)
      return;
    Binding binding;
    if (!ParseBinding(reference->GetExpression(), &binding))
      binding = {};
    if (keyboard)
      binding.key = name;
    else
      binding.pads = {source == "SDL" ? FromSdl(name) : name};
    {
      const auto lock = ControllerEmu::EmulatedController::GetStateLock();
      reference->SetExpression(BuildBinding(binding, IsDigital(control), s_sdl_pads));
    }
    CommitPad(true);
    s_binding_note.clear();
    return;
  }
  s_binding_note = "Nothing new was pressed; the binding is unchanged.";
}

// Pad control name as printed on Xbox / PlayStation pads.
std::string PadLabel(const std::string& name)
{
  static const std::pair<const char*, const char*> labels[] = {
      {"Button A", "A / Cross"},     {"Button B", "B / Circle"},   {"Button X", "X / Square"},
      {"Button Y", "Y / Triangle"},  {"Shoulder L", "LB / L1"},    {"Shoulder R", "RB / R1"},
      {"Trigger L", "LT / L2"},      {"Trigger R", "RT / R2"},     {"Start", "Menu / Options"},
      {"Thumb L", "L3"},             {"Thumb R", "R3"},            {"Pad N", "D-pad up"},
      {"Pad S", "D-pad down"},       {"Pad W", "D-pad left"},      {"Pad E", "D-pad right"},
      {"Left X-", "L stick left"},   {"Left X+", "L stick right"}, {"Left Y+", "L stick up"},
      {"Left Y-", "L stick down"},   {"Right X-", "R stick left"}, {"Right X+", "R stick right"},
      {"Right Y+", "R stick up"},    {"Right Y-", "R stick down"},
  };
  for (const auto& [from, to] : labels)
  {
    if (name == from)
      return to;
  }
  return name;
}

std::string BindingSummary(const PadControl& control)
{
  ControlReference* reference = PadReference(control);
  Binding binding;
  if (!reference || !ParseBinding(reference->GetExpression(), &binding))
    return reference ? "Custom" : "-";
  std::string text;
  for (const std::string& pad : binding.pads)
    text += (text.empty() ? "" : ", ") + PadLabel(pad);
  if (!binding.key.empty())
    text += (text.empty() ? "" : "   ") + ("key " + (binding.key == "RETURN" ? "Enter" : binding.key));
  return text.empty() ? "Unbound" : text;
}

void SetOpen(bool open)
{
  if (open == s_open)
    return;
  s_open = open;
  s_quit_armed = 0.0f;
  s_jump = -1;
  if (open)
  {
    s_focus_next = s_focus_resume = true;
    s_tab = 0;
    s_pill[0] = -1.0f;
    ImGui::SetNavCursorVisible(true);  // show which item A will press
  }
  else
    Save();
}

void FeedNavigation(const PadState& pad, bool enabled)
{
  ImGuiIO& io = ImGui::GetIO();
  io.ConfigFlags |= ImGuiConfigFlags_NavEnableGamepad;
  io.BackendFlags |= ImGuiBackendFlags_HasGamepad;
  const auto key = [&](ImGuiKey imgui_key, bool down) { io.AddKeyEvent(imgui_key, enabled && down); };
  key(ImGuiKey_GamepadDpadUp, (pad.buttons & PAD_UP) != 0);
  key(ImGuiKey_GamepadDpadDown, (pad.buttons & PAD_DOWN) != 0);
  key(ImGuiKey_GamepadDpadLeft, (pad.buttons & PAD_LEFT) != 0);
  key(ImGuiKey_GamepadDpadRight, (pad.buttons & PAD_RIGHT) != 0);
  key(ImGuiKey_GamepadFaceDown, (pad.buttons & PAD_A) != 0);
  key(ImGuiKey_GamepadFaceRight, (pad.buttons & PAD_B) != 0);
  const auto analog = [&](ImGuiKey imgui_key, float value) {
    const float v = enabled ? std::clamp((value - 0.25f) / 0.65f, 0.0f, 1.0f) : 0.0f;
    io.AddKeyAnalogEvent(imgui_key, v > 0.1f, v);
  };
  analog(ImGuiKey_GamepadLStickUp, pad.ly);
  analog(ImGuiKey_GamepadLStickDown, -pad.ly);
  analog(ImGuiKey_GamepadLStickLeft, -pad.lx);
  analog(ImGuiKey_GamepadLStickRight, pad.lx);
  if (const int wheel = g_wario_mouse_wheel.exchange(0); wheel != 0 && enabled)
    io.AddMouseWheelEvent(0.0f, wheel / 120.0f);
}

// Text size follows Windows display scaling (like other apps: 18 px at 100 %) times the menu-size
// setting; the panel is as wide as its content needs, at most half the screen.
float UiScale()
{
  float dpi = 1.0f;
#ifdef _WIN32
  if (g_wario_hwnd)
  {
    using GetDpiFn = UINT(WINAPI*)(HWND);
    static const GetDpiFn get_dpi = reinterpret_cast<GetDpiFn>(
        GetProcAddress(GetModuleHandleW(L"user32.dll"), "GetDpiForWindow"));
    if (get_dpi)
    {
      const UINT value = get_dpi(static_cast<HWND>(g_wario_hwnd));
      if (value >= 48 && value <= 480)
        dpi = value / 96.0f;
    }
  }
#endif
  return dpi * s_settings.menu_scale;
}

ImVec4 Mix(const ImVec4& a, const ImVec4& b, float t)
{
  return ImVec4(a.x + (b.x - a.x) * t, a.y + (b.y - a.y) * t, a.z + (b.z - a.z) * t,
                a.w + (b.w - a.w) * t);
}

ImVec4 WithAlpha(ImVec4 colour, float alpha)
{
  colour.w *= alpha;
  return colour;
}

// Horizontal rule that fades out towards x1 (colours go through GetColorU32, so the open/close
// animation's alpha applies).
void FadeLine(ImDrawList* draw, float x0, float x1, float y, float thickness, const ImVec4& colour)
{
  const ImU32 solid = ImGui::GetColorU32(colour), clear = ImGui::GetColorU32(WithAlpha(colour, 0.0f));
  draw->AddRectFilledMultiColor(ImVec2(x0, y), ImVec2(x1, y + thickness), solid, clear, clear, solid);
}

void DrawPanel(float width, float height)
{
  Settings& s = s_settings;
  const Theme& theme = kThemes[s.style];
  const bool light = theme.bg_top.x + theme.bg_top.y + theme.bg_top.z > 1.5f;
  const float font = std::clamp(18.0f * UiScale(), 10.0f, 96.0f);
  const float panel = std::min(width * 0.5f, font * 26.0f);
  const float pad = font * 1.2f;
  const float t = std::clamp(s_anim, 0.0f, 1.0f);
  const float ease = 1.0f - (1.0f - t) * (1.0f - t) * (1.0f - t);
  ImGui::SetNextWindowPos(ImVec2(-panel * (1.0f - ease), 0.0f));
  ImGui::SetNextWindowSize(ImVec2(panel, height));
  ImGui::SetNextWindowBgAlpha(0.0f);  // gradient drawn below
  if (s_focus_next)
  {
    ImGui::SetNextWindowFocus();
    s_focus_next = false;
  }
  ImGui::PushStyleVar(ImGuiStyleVar_WindowRounding, 0.0f);
  ImGui::PushStyleVar(ImGuiStyleVar_WindowBorderSize, 0.0f);
  ImGui::PushStyleVar(ImGuiStyleVar_WindowPadding, ImVec2(pad, font * 1.0f));
  ImGui::PushStyleVar(ImGuiStyleVar_ItemSpacing, ImVec2(font * 0.5f, font * 0.42f));
  ImGui::PushStyleVar(ImGuiStyleVar_FramePadding, ImVec2(font * 0.4f, font * 0.25f));
  ImGui::PushStyleVar(ImGuiStyleVar_FrameRounding, font * 0.22f);
  ImGui::PushStyleVar(ImGuiStyleVar_GrabRounding, font * 0.18f);
  ImGui::PushStyleVar(ImGuiStyleVar_GrabMinSize, font * 0.6f);
  ImGui::PushStyleVar(ImGuiStyleVar_PopupRounding, font * 0.25f);
  ImGui::PushStyleVar(ImGuiStyleVar_Alpha, std::max(ease, 0.01f));
  int colours = 0;
  const auto colour = [&](ImGuiCol id, const ImVec4& value) {
    ImGui::PushStyleColor(id, value);
    ++colours;
  };
  if (theme.custom)
  {
    const ImVec4 white(1.0f, 1.0f, 1.0f, 1.0f);
    colour(ImGuiCol_Text, theme.text);
    colour(ImGuiCol_TextDisabled, theme.text_dim);
    colour(ImGuiCol_FrameBg, WithAlpha(theme.frame, 0.85f));
    colour(ImGuiCol_FrameBgHovered, Mix(theme.frame, theme.accent, 0.25f));
    colour(ImGuiCol_FrameBgActive, Mix(theme.frame, theme.accent, 0.4f));
    colour(ImGuiCol_Button, Mix(theme.frame, theme.accent, 0.2f));
    colour(ImGuiCol_ButtonHovered, Mix(theme.frame, theme.accent, 0.4f));
    colour(ImGuiCol_ButtonActive, Mix(theme.frame, theme.accent, 0.6f));
    colour(ImGuiCol_Header, WithAlpha(theme.accent, 0.3f));
    colour(ImGuiCol_HeaderHovered, WithAlpha(theme.accent, 0.45f));
    colour(ImGuiCol_HeaderActive, WithAlpha(theme.accent, 0.6f));
    colour(ImGuiCol_CheckMark, theme.accent);
    colour(ImGuiCol_SliderGrab, theme.accent);
    colour(ImGuiCol_SliderGrabActive, Mix(theme.accent, white, 0.3f));
    colour(ImGuiCol_PopupBg, WithAlpha(theme.bg_bottom, 0.98f));
    colour(ImGuiCol_Border, WithAlpha(theme.accent, 0.35f));
    colour(ImGuiCol_ScrollbarGrab, WithAlpha(theme.accent, 0.35f));
    colour(ImGuiCol_ScrollbarGrabHovered, WithAlpha(theme.accent, 0.55f));
    colour(ImGuiCol_ScrollbarGrabActive, WithAlpha(theme.accent, 0.75f));
    colour(ImGuiCol_NavCursor, light ? theme.text : theme.accent);
  }
  const ImGuiWindowFlags flags = ImGuiWindowFlags_NoTitleBar | ImGuiWindowFlags_NoResize |
                                 ImGuiWindowFlags_NoMove | ImGuiWindowFlags_NoCollapse |
                                 ImGuiWindowFlags_NoSavedSettings;
  if (ImGui::Begin("##wario_menu", nullptr, flags))
  {
    ImDrawList* draw = ImGui::GetWindowDrawList();
    const ImVec2 origin = ImGui::GetWindowPos();
    const float right = origin.x + panel - pad;
    {
      // Panel: vertical gradient, a soft accent glow at the top, an accent edge on the right and a
      // shadow falling onto the game.
      const ImVec2 end(origin.x + panel, origin.y + height);
      ImGui::PushClipRect(origin, end, false);
      const ImU32 top = ImGui::GetColorU32(WithAlpha(theme.bg_top, 0.94f));
      const ImU32 bottom = ImGui::GetColorU32(WithAlpha(theme.bg_bottom, 0.97f));
      draw->AddRectFilledMultiColor(origin, end, top, top, bottom, bottom);
      const ImU32 glow = ImGui::GetColorU32(WithAlpha(theme.accent, 0.14f));
      const ImU32 none = ImGui::GetColorU32(WithAlpha(theme.accent, 0.0f));
      draw->AddRectFilledMultiColor(origin, ImVec2(end.x, origin.y + font * 7.0f), glow, glow, none,
                                    none);
      const float edge = std::max(1.0f, font * 0.12f);
      const ImU32 edge_top = ImGui::GetColorU32(WithAlpha(theme.accent, 0.9f));
      const ImU32 edge_bottom = ImGui::GetColorU32(WithAlpha(theme.accent, 0.2f));
      draw->AddRectFilledMultiColor(ImVec2(end.x - edge, origin.y), end, edge_top, edge_top,
                                    edge_bottom, edge_bottom);
      ImGui::PopClipRect();
      const ImU32 shade = ImGui::GetColorU32(ImVec4(0.0f, 0.0f, 0.0f, 0.45f));
      const ImU32 clear = ImGui::GetColorU32(ImVec4(0.0f, 0.0f, 0.0f, 0.0f));
      ImGui::GetBackgroundDrawList()->AddRectFilledMultiColor(
          ImVec2(end.x, origin.y), ImVec2(end.x + font * 1.6f, end.y), shade, clear, clear, shade);
    }

    // Title with a drop shadow and an accent underline.
    ImGui::PushFont(nullptr, font * 1.7f);
    const ImVec2 title = ImGui::GetCursorScreenPos();
    const float shadow = std::max(1.0f, font * 0.09f);
    draw->AddText(ImGui::GetFont(), ImGui::GetFontSize(), ImVec2(title.x + shadow, title.y + shadow),
                  ImGui::GetColorU32(ImVec4(0.0f, 0.0f, 0.0f, light ? 0.15f : 0.6f)), "WARIO WORLD");
    ImGui::TextColored(theme.title, "WARIO WORLD");
    ImGui::PopFont();
    FadeLine(draw, title.x, right, ImGui::GetItemRectMax().y + font * 0.1f,
             std::max(1.0f, font * 0.1f), WithAlpha(theme.accent, 0.8f));
    ImGui::PushFont(nullptr, font);
    ImGui::Dummy(ImVec2(0.0f, font * 0.35f));
    ImGui::Spacing();
    const float inner = panel - pad * 2.0f;
    const float label = inner * 0.36f;
    const float field = inner - label;
    const auto row = [&](const char* text) {
      ImGui::AlignTextToFramePadding();
      ImGui::TextUnformatted(text);
      ImGui::SameLine(label + pad);
      ImGui::SetNextItemWidth(field);
    };
    // A float setting as whole steps, so one d-pad press is one step. (A float slider moves 1 % of
    // its range per press and is then rounded to the shown precision, so single presses did
    // nothing until key repeat kicked in.)
    const auto stepped = [&](const char* id, float& value, float step, float low, float high,
                             const char* format) {
      int steps = static_cast<int>(std::lround(value / step));
      char text[32];
      std::snprintf(text, sizeof(text), format, steps * step);
      const bool moved = ImGui::SliderInt(id, &steps, static_cast<int>(std::lround(low / step)),
                                          static_cast<int>(std::lround(high / step)), text,
                                          ImGuiSliderFlags_NoInput);
      if (moved)
        value = steps * step;
      return moved;
    };
    // Section header: accent tab, small caps label and a fading rule. A tab change lands on the
    // section's first item.
    const auto header = [&](const char* text, int index) {
      ImGui::Dummy(ImVec2(0.0f, font * 0.12f));
      ImGui::PushFont(nullptr, font * 0.8f);
      const ImVec2 pos = ImGui::GetCursorScreenPos();
      const float line = ImGui::GetTextLineHeight();
      draw->AddRectFilled(ImVec2(pos.x, pos.y + line * 0.1f),
                          ImVec2(pos.x + font * 0.18f, pos.y + line * 0.9f),
                          ImGui::GetColorU32(theme.accent), font * 0.09f);
      ImGui::SetCursorScreenPos(ImVec2(pos.x + font * 0.55f, pos.y));
      ImGui::TextColored(theme.accent, "%s", text);
      ImGui::PopFont();
      FadeLine(draw, ImGui::GetItemRectMax().x + font * 0.5f, right, pos.y + line * 0.5f,
               std::max(1.0f, font * 0.06f), WithAlpha(theme.accent, 0.5f));
      ImGui::Dummy(ImVec2(0.0f, font * 0.05f));
      if (s_jump == index)
      {
        FocusNextItem();
        s_jump = -1;
      }
    };
    if (s_tab_scroll)
    {
      ImGui::SetScrollY(0.0f);
      s_tab_scroll = false;
    }
    {
      // Tab strip: a pill track with the selected tab filled; LB / RB chips at the ends.
      const ImVec2 pos = ImGui::GetCursorScreenPos();
      const float strip = font * 1.45f;
      const float chip = font * 1.45f, gap = font * 0.2f, padding = font * 0.9f;
      // Labels are 0.85 em, smaller when needed so every tab keeps its padding; the LB / RB chips
      // go only if the labels would get too small.
      float em_total = 0.0f;
      for (int i = 0; i < kTabCount; ++i)
        em_total += ImGui::GetFont()->CalcTextSizeA(font, FLT_MAX, 0.0f, kTabNames[i]).x / font;
      const auto label_size = [&](float room) {
        return std::min(font * 0.85f, (room - kTabCount * padding) / em_total);
      };
      bool chips = true;
      float tab_text = label_size(inner - 2.0f * (chip + gap));
      if (tab_text < font * 0.7f)
      {
        chips = false;
        tab_text = label_size(inner);
      }
      ImGui::PushFont(nullptr, std::max(tab_text, font * 0.55f));
      float widths[kTabCount], text_total = 0.0f;
      for (int i = 0; i < kTabCount; ++i)
        text_total += widths[i] = ImGui::CalcTextSize(kTabNames[i]).x;
      const float x0 = chips ? pos.x + chip + gap : pos.x;
      const float x1 = chips ? pos.x + inner - chip - gap : pos.x + inner;
      const float extra = std::max(0.0f, (x1 - x0 - text_total) / kTabCount);
      draw->AddRectFilled(ImVec2(x0, pos.y), ImVec2(x1, pos.y + strip),
                          ImGui::GetColorU32(ImGuiCol_FrameBg), strip * 0.5f);
      const ImVec4 selected =
          theme.custom ? theme.primary : ImGui::GetStyleColorVec4(ImGuiCol_ButtonActive);
      const ImVec4 selected_text =
          theme.custom ? theme.primary_text : ImGui::GetStyleColorVec4(ImGuiCol_Text);
      const float inset = font * 0.14f;
      // The highlight slides towards the selected tab.
      float x = x0, target[2] = {x0, x0};
      for (int i = 0; i < kTabCount; ++i)
      {
        if (i == s_tab)
        {
          target[0] = x + inset;
          target[1] = x + widths[i] + extra - inset;
        }
        x += widths[i] + extra;
      }
      if (s_pill[0] < 0.0f)
      {
        s_pill[0] = target[0];
        s_pill[1] = target[1];
      }
      const float follow = 1.0f - std::exp(-ImGui::GetIO().DeltaTime * 18.0f);
      for (int i = 0; i < 2; ++i)
        s_pill[i] += (target[i] - s_pill[i]) * follow;
      draw->AddRectFilled(ImVec2(s_pill[0], pos.y + inset), ImVec2(s_pill[1], pos.y + strip - inset),
                          ImGui::GetColorU32(selected), (strip - inset * 2.0f) * 0.5f);
      ImGui::PushItemFlag(ImGuiItemFlags_NoNav, true);  // tabs are for LB / RB and the mouse
      x = x0;
      for (int i = 0; i < kTabCount; ++i)
      {
        const float w = widths[i] + extra;
        ImGui::SetCursorScreenPos(ImVec2(x, pos.y));
        ImGui::PushID(i);
        if (ImGui::InvisibleButton("##tab", ImVec2(w, strip)) && i != s_tab)
        {
          s_tab = i;
          s_jump = i;
          s_tab_scroll = true;
        }
        const bool hovered = ImGui::IsItemHovered();
        ImGui::PopID();
        if (hovered && i != s_tab)
        {
          draw->AddRectFilled(ImVec2(x + inset, pos.y + inset),
                              ImVec2(x + w - inset, pos.y + strip - inset),
                              ImGui::GetColorU32(ImGuiCol_HeaderHovered), (strip - inset * 2.0f) * 0.5f);
        }
        const ImVec4 text = i == s_tab ? selected_text :
                            ImGui::GetStyleColorVec4(hovered ? ImGuiCol_Text : ImGuiCol_TextDisabled);
        draw->AddText(ImVec2(x + extra * 0.5f, pos.y + (strip - ImGui::GetTextLineHeight()) * 0.5f),
                      ImGui::GetColorU32(text), kTabNames[i]);
        x += w;
      }
      ImGui::PopItemFlag();
      if (chips)
      {
        const float size = font * 0.7f;
        const auto bumper = [&](float left, const char* text) {
          const ImVec2 a(left, pos.y + strip * 0.15f), b(left + chip, pos.y + strip * 0.85f);
          draw->AddRectFilled(a, b, ImGui::GetColorU32(ImGuiCol_FrameBg), font * 0.25f);
          const ImVec2 t = ImGui::GetFont()->CalcTextSizeA(size, FLT_MAX, 0.0f, text);
          draw->AddText(ImGui::GetFont(), size, ImVec2((a.x + b.x - t.x) * 0.5f, (a.y + b.y - t.y) * 0.5f),
                        ImGui::GetColorU32(ImGuiCol_TextDisabled), text);
        };
        bumper(pos.x, "LB");
        bumper(pos.x + inner - chip, "RB");
      }
      ImGui::PopFont();
      ImGui::SetCursorScreenPos(ImVec2(pos.x, pos.y + strip));
      ImGui::Dummy(ImVec2(inner, font * 0.25f));
    }
    bool changed = false;
    if (s_jump == 2 && !IsVulkan())
      s_jump = 0;  // nothing in the HDR tab can be used: stay on Resume, never fall onto Quit
    if (s_focus_resume || s_jump == 0)
    {
      FocusNextItem();
      s_focus_resume = false;
      if (s_jump == 0)
        s_jump = -1;
    }
    // Resume is the primary action: filled with the theme's strong colour.
    int primary = 0;
    if (theme.custom)
    {
      const ImVec4 white(1.0f, 1.0f, 1.0f, 1.0f);
      ImGui::PushStyleColor(ImGuiCol_Button, theme.primary);
      ImGui::PushStyleColor(ImGuiCol_ButtonHovered, Mix(theme.primary, white, 0.15f));
      ImGui::PushStyleColor(ImGuiCol_ButtonActive, Mix(theme.primary, white, 0.3f));
      ImGui::PushStyleColor(ImGuiCol_Text, theme.primary_text);
      primary = 4;
    }
    if (ImGui::Button("Resume", ImVec2(inner, font * 1.6f)))
      SetOpen(false);
    ImGui::PopStyleColor(primary);

    if (s_tab == 0 || s_tab == 1)
    {
      header("DISPLAY", 1);
      row("Resolution");
      if (ImGui::Combo("##resolution", &s.resolution, kResolutionNames,
                       static_cast<int>(std::size(kResolutionNames))))
      {
        QueueResolution();
        changed = true;
      }
      row("Aspect ratio");
      if (ImGui::BeginCombo("##aspect", kAspects[s.aspect].name))
      {
        for (int i = 0; i < static_cast<int>(std::size(kAspects)); ++i)
        {
          if (ImGui::Selectable(kAspects[i].name, i == s.aspect) && i != s.aspect)
          {
            s.aspect = i;
            QueueAspect();
            changed = true;
          }
        }
        ImGui::EndCombo();
      }
      // The tick follows the real window (F11 / Alt+Enter change it too).
      if (s_fullscreen_wait <= 0.0f)
        s.fullscreen = WindowFullscreen();
      if (ImGui::Checkbox("Fullscreen", &s.fullscreen))
      {
        SetFullscreen(s.fullscreen);
        changed = true;
      }
      if (ImGui::Checkbox("HD textures (from the HD folder)", &s.hd_textures))
      {
        QueueHd();
        changed = true;
      }
    }

    if (s_tab == 0 || s_tab == 2)
    {
      header("HDR", 2);
      ImGui::BeginDisabled(!IsVulkan());
      if (ImGui::Checkbox(IsVulkan() ? "HDR output" : "HDR output (Vulkan only)", &s.hdr))
      {
        QueueHdr();
        changed = true;
      }
      ImGui::EndDisabled();
      // The tuning shows on All only while HDR is on; the HDR tab always lists it.
      const bool hdr_on = s.hdr && IsVulkan();
      if (hdr_on || s_tab == 2)
      {
        if (!hdr_on)
        {
          ImGui::PushTextWrapPos(inner + pad);
          ImGui::TextDisabled("Turn on HDR output (Vulkan) to adjust these.");
          ImGui::PopTextWrapPos();
        }
        ImGui::BeginDisabled(!hdr_on);
        const auto edited = [&] {
          if (ImGui::IsItemDeactivatedAfterEdit())
            changed = true;
        };
        row("Paper white");
        if (ImGui::SliderFloat("##hdr_paper_white", &s.hdr_paper_white, 80.0f, 500.0f, "%.0f nits"))
          QueuePaperWhite();
        edited();
        if (hdr_on)
        {
          row("Menu brightness");
          if (stepped("##hdr_menu_nits", s.hdr_menu_nits, 10.0f, 80.0f, 400.0f, "%.0f nits"))
            g_wario_menu_nits.store(s.hdr_menu_nits);
          edited();
        }
        row("Highlight boost");
        ImGui::SliderInt("##hdr_boost", &s.hdr_boost, 0, 100, s.hdr_boost == 0 ? "Off" : "%d%%");
        edited();
        ImGui::BeginDisabled(s.hdr_boost == 0);
        row("Peak brightness");
        ImGui::SliderFloat("##hdr_peak", &s.hdr_peak, 400.0f, 4000.0f, "%.0f nits");
        edited();
        ImGui::EndDisabled();
        row("White level");
        // Hundreds of nits, 3 = off, so one press is 100 nits (the format prints the "00").
        int white = s.hdr_white_nits == 0 ? 3 : s.hdr_white_nits / 100;
        if (ImGui::SliderInt("##hdr_white", &white, 3, 40, white == 3 ? "Off" : "%d00 nits",
                             ImGuiSliderFlags_NoInput))
        {
          s.hdr_white_nits = white == 3 ? 0 : white * 100;
        }
        edited();
        ImGui::PushTextWrapPos(inner + pad);
        ImGui::TextDisabled("The brightest the picture may get: highlights roll off smoothly "
                            "towards it instead of clipping. Set it to your screen's peak if "
                            "bright areas lose detail. Off = no limit.");
        ImGui::PopTextWrapPos();
        row("Saturation");
        ImGui::SliderInt("##hdr_saturation", &s.hdr_saturation, 0, 200, "%d%%");
        edited();
        row("Vibrance");
        ImGui::SliderInt("##hdr_vibrance", &s.hdr_vibrance, -100, 100, "%+d%%");
        edited();
        ImGui::PushTextWrapPos(inner + pad);
        ImGui::TextDisabled("Like saturation, but boosts muted colours most and spares vivid "
                            "colours and skin tones.");
        ImGui::PopTextWrapPos();
        row("Contrast");
        ImGui::SliderInt("##hdr_contrast", &s.hdr_contrast, 50, 150, "%d%%");
        edited();
        row("Gamma");
        stepped("##hdr_gamma", s.hdr_gamma, 0.01f, 0.7f, 1.3f, "%.2f");
        edited();
        row("Black level");
        ImGui::SliderInt("##hdr_black", &s.hdr_black, -10, 10, "%+d");
        edited();
        if (ImGui::Button("Reset HDR to defaults", ImVec2(inner, 0.0f)))
        {
          ResetHdr();
          changed = true;
        }
        ImGui::EndDisabled();
      }
    }

    if (s_tab == 0 || s_tab == 3)
    {
      header("MOTION", 3);
      row("Frame rate");
      if (ImGui::Combo("##frame_rate", &s.frame_rate, kFrameRateNames,
                       static_cast<int>(std::size(kFrameRateNames))))
      {
        QueueFps();
        changed = true;
      }
      row("VSync");
      if (ImGui::Combo("##vsync", &s.vsync, kVsyncNames, static_cast<int>(std::size(kVsyncNames))))
      {
        VideoCommon::g_wario_vsync_mode.store(s.vsync);  // read live by the presenter
        changed = true;
      }
      ImGui::BeginDisabled(s.frame_rate == 0);
      row("Motion");
      if (ImGui::Combo("##motion", &s.motion, kMotionNames, static_cast<int>(std::size(kMotionNames))))
      {
        QueueFps();
        changed = true;
      }
      ImGui::EndDisabled();
      ImGui::PushTextWrapPos(inner + pad);
      ImGui::TextDisabled("Extra frames are interpolated; game speed is unchanged. Adds ~8-12 ms "
                          "delay. Pick no more than your screen's refresh rate.");
      ImGui::TextDisabled("VSync Auto gives every generated frame its own screen refresh (cleanest "
                          "motion). Off can reduce latency but may show afterimages.");
      ImGui::PopTextWrapPos();
    }

    if (s_tab == 0 || s_tab == 4)
    {
      header("AUDIO", 4);
      const auto edited = [&] {
        if (ImGui::IsItemDeactivatedAfterEdit())
          changed = true;
      };
      row("Master");
      if (ImGui::SliderInt("##volume", &s.volume, 0, 100, "%d%%"))
        QueueVolume();
      edited();
      ImGui::BeginDisabled(!s_audio_exports);
      row("Music");
      ImGui::SliderInt("##music", &s.music, 0, 100, "%d%%");  // applied every frame
      edited();
      row("Sound effects");
      ImGui::SliderInt("##sfx", &s.sfx, 0, 100, "%d%%");
      edited();
      if (ImGui::Checkbox("Mute pause menu music", &s.mute_pause_music))
        changed = true;
      ImGui::EndDisabled();
      ImGui::PushTextWrapPos(inner + pad);
      if (!s_audio_exports)
        ImGui::TextDisabled("Music and sound effects need the newer game module.");
      ImGui::PopTextWrapPos();
    }

    if (s_tab == 0 || s_tab == 5)
    {
      header("CONTROLS", 5);
      ImGui::PushTextWrapPos(inner + pad);
      ImGui::TextDisabled("GameCube layout: A bottom, B left, X right, Y top. Select a control, "
                          "then press the new button or key.");
      ImGui::PopTextWrapPos();
      for (int i = 0; i < static_cast<int>(std::size(kPadControls)); ++i)
      {
        const PadControl& control = kPadControls[i];
        if (!control.label)
          continue;
        row(control.label);
        ImGui::PushID(i);
        std::string text = s_binding == i ?
                               fmt::format("Press a button or key...  {:.0f}",
                                           std::ceil(std::max(6.0f - s_binding_time, 0.0f))) :
                               BindingSummary(control);
        if (ImGui::Button((text + "###bind").c_str(), ImVec2(field, 0.0f)) && !s_detector)
          StartBinding(i);
        ImGui::PopID();
      }
      if (!s_binding_note.empty())
        ImGui::TextDisabled("%s", s_binding_note.c_str());
      if (ImGui::Checkbox("Rumble", &s.rumble))
      {
        ApplyRumble();
        CommitPad(true);
        changed = true;
      }
      ImGui::BeginDisabled(!s.rumble);
      row("Rumble strength");
      if (ImGui::SliderInt("##rumble_strength", &s.rumble_strength, 0, 100, "%d%%"))
        ApplyRumble();
      if (ImGui::IsItemDeactivatedAfterEdit())
      {
        CommitPad(true);
        changed = true;
      }
      ImGui::EndDisabled();
      if (ImGui::Button("Reset controls to defaults", ImVec2(inner, 0.0f)))
      {
        ResetPadDefaults();
        changed = true;
      }
      ImGui::PushTextWrapPos(inner + pad);
      ImGui::TextDisabled("Back and Tab always open this menu. Sticks keep their defaults.");
      ImGui::PopTextWrapPos();
    }

    if (s_tab == 0 || s_tab == 6)
    {
      header("CHEATS", 6);
      ImGui::BeginDisabled(!s_cheat_exports);
      const auto hint = [&](const char* text) {
        ImGui::PushTextWrapPos(inner + pad);
        ImGui::TextDisabled("%s", text);
        ImGui::PopTextWrapPos();
      };
      row("Jump height");
      // Tens of percent, so one d-pad press is 10 % (the format prints the trailing 0).
      int tens = s.jump_percent / 10;
      if (ImGui::SliderInt("##jump_percent", &tens, 10, 50, tens == 10 ? "100%% (original)" : "%d0%%",
                           ImGuiSliderFlags_NoInput))
      {
        s.jump_percent = tens * 10;
      }
      if (ImGui::IsItemDeactivatedAfterEdit())
        changed = true;
      if (ImGui::Checkbox("Walk through walls", &s.noclip))
        changed = true;
      hint("Wario can fall out of the world where a wall has nothing behind it.");
      if (ImGui::Checkbox("Super punches", &s.super_punch))
        changed = true;
      hint("Every punch hits like the 3rd combo punch.");
      // One-shots: applied by the module at the next player update, so only with a save loaded.
      // Like Quit, the first press only arms the button for 3 s: these change the save file.
      const auto one_shot = [&](int index, const char* label, volatile s32* request) {
        static float armed[2] = {0.0f, 0.0f};
        armed[index] = std::max(armed[index] - ImGui::GetIO().DeltaTime, 0.0f);
        const s32 state = request ? *request : 0;
        const bool confirm = armed[index] > 0.0f;
        if (confirm)
          ImGui::PushStyleColor(ImGuiCol_Button, ImVec4(0.65f, 0.12f, 0.1f, 1.0f));
        const std::string text = confirm ? fmt::format("Press again to apply###one_shot{}", index) :
                                           fmt::format("{}###one_shot{}", label, index);
        if (ImGui::Button(text.c_str(), ImVec2(inner, 0.0f)) && request && state != 1)
        {
          if (confirm)
          {
            *request = 1;
            armed[index] = 0.0f;
          }
          else
          {
            armed[index] = 3.0f;
          }
        }
        if (confirm)
          ImGui::PopStyleColor();
        hint("Permanent once you save the game. Re-enter the hub to see the doors and the final "
             "chest update.");
        if (state == 1)
          hint("Waiting: applies once a save file is loaded and Wario is in the world.");
        else if (state == 2)
          hint("Applied.");
      };
      one_shot(0, "Unlock all stages", s_cheat_unlock);
      hint("Every stage and world opens; the final boss stays uncleared.");
      one_shot(1, "Mark all collectables as grabbed", s_cheat_collect);
      hint("Treasures, red diamonds, Spritelings and statue parts in every stage. The final chest "
           "also needs every stage cleared.");
      ImGui::EndDisabled();
      if (!s_cheat_exports)
        hint("Cheats need the newer game module.");
    }

    if (s_tab == 0 || s_tab == 7)
    {
      header("SYSTEM", 7);
      row("UI style");
      if (ImGui::BeginCombo("##style", kThemes[s.style].name))
      {
        for (int i = 0; i < static_cast<int>(std::size(kThemes)); ++i)
        {
          if (ImGui::Selectable(kThemes[i].name, i == s.style) && i != s.style)
          {
            s.style = i;
            changed = true;
          }
        }
        ImGui::EndCombo();
      }
      row("Menu size");
      // Live with the pad; with the mouse only on release, so the slider does not move under the
      // cursor while the menu resizes.
      static float dragged_scale = 0.0f;
      float scale = dragged_scale > 0.0f ? dragged_scale : s.menu_scale;
      stepped("##menu_scale", scale, 0.1f, 0.6f, 1.6f, "%.1fx");
      if (ImGui::IsItemActive() && ImGui::IsMouseDown(ImGuiMouseButton_Left))
      {
        dragged_scale = scale;
      }
      else
      {
        s.menu_scale = scale;
        dragged_scale = 0.0f;
      }
      if (ImGui::IsItemDeactivatedAfterEdit())
        changed = true;

      row("Graphics");
      if (ImGui::Combo("##backend", &s.backend, kBackendNames,
                       static_cast<int>(std::size(kBackendNames))))
      {
        changed = true;
      }
      if (ImGui::Checkbox("Performance mode (multithreaded)", &s.performance))
        changed = true;
      ImGui::PushTextWrapPos(inner + pad);
      ImGui::TextDisabled("Runs GPU emulation on its own thread so heavy scenes and HD textures "
                          "don't slow the game. Slightly less timing-accurate than the default.");
      if (s.hdr && s.backend != 1)
        ImGui::TextDisabled("HDR output needs Vulkan.");
      // Both are read by the starter at launch (backend=, performance= -> Dolphin.ini).
      if (s.backend != s_backend_running || s.performance != s_performance_running)
      {
        ImGui::TextDisabled("Applies after restart.");
        if (ImGui::Button("Restart now", ImVec2(inner, 0.0f)))
          Restart();
      }
      ImGui::PopTextWrapPos();

      static const std::string extract_command = EnvUtf8("MODERNGEKKO_WARIO_EXTRACT_CMD");
      static const std::string extracted_dir = EnvUtf8("MODERNGEKKO_WARIO_EXTRACTED_DIR");
      static const std::string log_path = EnvUtf8("MODERNGEKKO_WARIO_LOG");
      ImGui::Dummy(ImVec2(0.0f, font * 0.1f));
      if (!extract_command.empty())
      {
        const bool running = s_extract_state == ExtractState::Running;
        ImGui::BeginDisabled(running);
        if (ImGui::Button(running ? "Extracting textures...###extract" : "Extract all textures###extract",
                          ImVec2(inner, 0.0f)))
        {
          StartExtract(extract_command);
        }
        ImGui::EndDisabled();
        ImGui::PushTextWrapPos(inner + pad);
        if (running)
        {
          ImGui::TextDisabled("Runs in the background, so keep playing. Takes a minute or two.");
        }
        else if (s_extract_state == ExtractState::Finished)
          ImGui::TextDisabled("Textures extracted.");
        else if (s_extract_state == ExtractState::Failed)
          ImGui::TextColored(ImVec4(0.95f, 0.35f, 0.3f, 1.0f), "Extraction failed (code %lu).", s_extract_code);
        ImGui::PopTextWrapPos();
      }
      if (!extracted_dir.empty())
      {
        if (ImGui::Button("Open extracted textures", ImVec2(inner, 0.0f)))
          OpenPath(extracted_dir, true);
      }
      if (ImGui::Button("Open HD texture folder", ImVec2(inner, 0.0f)))
        OpenPath(File::GetUserPath(D_HIRESTEXTURES_IDX) + "GWWE01", true);
      if (!log_path.empty())
      {
        if (ImGui::Button("Open last log", ImVec2(inner, 0.0f)))
          OpenPath(log_path, false);
      }
      if (ReportSnapshotAvailable())
      {
        if (ImGui::Button("Save bug report snapshot (F12)", ImVec2(inner, 0.0f)))
          SaveReportSnapshot();
        ImGui::PushTextWrapPos(inner + pad);
        ImGui::TextDisabled("Saves a savestate and a screenshot of this moment for a bug report.");
        ImGui::PopTextWrapPos();
      }

      static const bool test_controls = std::getenv("MODERNGEKKO_WARIO_MENU_TEST") != nullptr;
      if (test_controls && s_tab == 7)
        ImGui::SetNextItemOpen(true);  // snapshots show the help text
      if (ImGui::CollapsingHeader("Controls"))
      {
        // Key on the left, what it does on the game pad on the right.
        const auto keys = [&](const char* title, std::initializer_list<std::pair<const char*, const char*>> list) {
          ImGui::TextColored(theme.accent, "%s", title);
          for (const auto& [key, action] : list)
          {
            ImGui::TextUnformatted(key);
            ImGui::SameLine(label + pad);
            ImGui::TextDisabled("%s", action);
          }
          ImGui::Spacing();
        };
        keys("Xbox / PlayStation", {{"A / Cross", "A (jump)"},
                                    {"X / Square", "B (punch)"},
                                    {"B / Circle", "X"},
                                    {"Y / Triangle", "Y"},
                                    {"Left stick", "Move"},
                                    {"Right stick", "C-stick (camera)"},
                                    {"Menu / Options", "Start"},
                                    {"RB / R1", "Z"},
                                    {"LT RT / L2 R2", "L  R"}});
        keys("Keyboard", {{"Arrows", "Move"},
                          {"Enter", "Start"},
                          {"X  Z", "A  B"},
                          {"C  S  D", "X  Y  Z"},
                          {"Q  W", "L  R"},
                          {"I  J  K  L", "C-stick"},
                          {"T  F  G  H", "D-pad"}});
        ImGui::PushTextWrapPos(inner + pad);
        ImGui::TextDisabled("GameCube layout by position; rebind in the Controls tab. Yes / No "
                            "menus use the stick, not the D-pad. Back or Tab opens this menu.");
        ImGui::PopTextWrapPos();
      }
    }

    ImGui::Dummy(ImVec2(0.0f, font * 0.3f));
    {
      const float y = ImGui::GetCursorScreenPos().y;
      const float x0 = ImGui::GetCursorScreenPos().x;
      // Rule that fades out at both ends.
      const float mid = (x0 + right) * 0.5f;
      const ImVec4 rule = WithAlpha(theme.accent, 0.4f);
      const float thickness = std::max(1.0f, font * 0.06f);
      const ImU32 solid = ImGui::GetColorU32(rule), clear = ImGui::GetColorU32(WithAlpha(rule, 0.0f));
      draw->AddRectFilledMultiColor(ImVec2(x0, y), ImVec2(mid, y + thickness), clear, solid, solid,
                                    clear);
      FadeLine(draw, mid, right, y, thickness, rule);
    }
    ImGui::Dummy(ImVec2(0.0f, font * 0.3f));
    // Quit needs a second press within 3 s, so a stray A on the last item never closes the game.
    s_quit_armed = std::max(s_quit_armed - ImGui::GetIO().DeltaTime, 0.0f);
    const bool armed = s_quit_armed > 0.0f;
    if (armed)
      ImGui::PushStyleColor(ImGuiCol_Button, ImVec4(0.65f, 0.12f, 0.1f, 1.0f));
    if (ImGui::Button(armed ? "Press again to quit###quit" : "Quit game###quit", ImVec2(inner, 0.0f)))
    {
      if (armed)
        Quit();
      else
        s_quit_armed = 3.0f;
    }
    if (armed)
      ImGui::PopStyleColor();
    ImGui::Spacing();
    ImGui::PushTextWrapPos(inner + pad);
    ImGui::TextDisabled("A select   B close   LB / RB tabs");
    ImGui::PopTextWrapPos();
    ImGui::PopFont();
    if (changed)
      Save();
  }
  ImGui::End();
  ImGui::PopStyleColor(colours);
  ImGui::PopStyleVar(10);
}
}  // namespace WarioMenu

// Called inside OnScreenUI::Finalize (ImGui frame open, ImGui lock held).
void WarioMenuDraw(u32 width, u32 height)
{
  using namespace WarioMenu;
  if (!s_loaded)
  {
    s_loaded = true;
    // Only settings saved by the menu are applied at startup; anything else keeps the session's
    // own configuration (a fixed aspect that is not a menu preset is never reset to 4:3).
    const std::vector<std::string> saved = Load();
    const auto has = [&](const char* key) {
      return std::find(saved.begin(), saved.end(), key) != saved.end();
    };
    if (has("resolution"))
      QueueResolution();
    if (has("aspect"))
      QueueAspect();
    if (has("hd_textures"))
      QueueHd();
    if (has("hdr"))
      QueueHdr();
    if (has("hdr_paper_white"))
      QueuePaperWhite();
    VideoCommon::g_wario_vsync_mode.store(s_settings.vsync);
    g_wario_menu_nits.store(s_settings.hdr_menu_nits);
    if (has("volume"))
      QueueVolume();
    if (has("frame_rate") || has("fps") || has("motion"))
      QueueFps();
  }
  ImGuiIO& io = ImGui::GetIO();
  const float dt = std::clamp(io.DeltaTime, 0.0f, 0.1f);
  const PadState pad = WindowFocused() ? ReadPads() : PadState{};
  const unsigned pressed = pad.buttons & ~s_previous_buttons;
  s_previous_buttons = pad.buttons;
  const bool tab = KeyDown(VK_TAB);
  {
    static const char* test = std::getenv("MODERNGEKKO_WARIO_MENU_TEST");
    static float test_time = 0.0f;
    static int test_stage = 0;
    if (test && *test)
    {
      test_time += dt;
      if (test_stage == 0 && test_time > 6.0f)
      {
        SetOpen(true);
        if (const char* test_tab = std::getenv("MODERNGEKKO_WARIO_MENU_TAB"))
          s_tab = s_jump = std::clamp(std::atoi(test_tab), 0, kTabCount - 1);
        // MODERNGEKKO_WARIO_MENU_TEST_EXTRACT: run the extract command as if pressed.
        if (std::getenv("MODERNGEKKO_WARIO_MENU_TEST_EXTRACT"))
          StartExtract(EnvUtf8("MODERNGEKKO_WARIO_EXTRACT_CMD"));
        test_stage = 1;
      }
      else if (test_stage == 1 && s_anim >= 1.0f && test_time > 7.0f)
      {
        g_wario_menu_snapshot.store(true);
        test_stage = 2;
      }
      else if (test_stage >= 2 && test_stage < 6 && std::getenv("MODERNGEKKO_WARIO_MENU_TEST_FULLSCREEN") &&
               test_time > 8.0f + (test_stage - 2))
      {
        // MODERNGEKKO_WARIO_MENU_TEST_FULLSCREEN: request on, on again, off, logging the real window
        // state before each step (the last line is after "off").
        static const bool requests[] = {true, true, false};
        std::fprintf(stderr, "wario-menu: fullscreen test step %d, window fullscreen=%d\n",
                     test_stage - 2, WindowFullscreen() ? 1 : 0);
        if (test_stage < 5)
          SetFullscreen(requests[test_stage - 2]);
        ++test_stage;
      }
      else if (test_stage == 2 && test_time > 8.5f && std::getenv("MODERNGEKKO_WARIO_MENU_TEST_CHEATS"))
      {
        // MODERNGEKKO_WARIO_MENU_TEST_CHEATS: request "Unlock all stages", close the menu so the game
        // runs, then log the module's answer (2 = applied).
        if (s_cheat_unlock)
          *s_cheat_unlock = 1;
        SetOpen(false);
        test_stage = 9;
      }
      else if (test_stage == 9 && test_time > 11.0f)
      {
        std::fprintf(stderr, "wario-menu: cheat exports=%d unlock_stages=%d\n", s_cheat_exports ? 1 : 0,
                     s_cheat_unlock ? static_cast<int>(*s_cheat_unlock) : -1);
        test_stage = 10;
      }
      else if (test_stage == 2 && test_time > 8.5f && std::getenv("MODERNGEKKO_WARIO_MENU_TEST_REPORT"))
      {
        // MODERNGEKKO_WARIO_MENU_TEST_REPORT: "Save bug report snapshot", then a menu picture with
        // the toast once it is showing.
        SaveReportSnapshot();
        test_stage = 7;
      }
      else if (test_stage == 7 && test_time > 9.0f)
      {
        g_wario_menu_snapshot.store(true);
        test_stage = 8;
      }
      else if (test_stage == 2 && test_time > 8.5f && std::getenv("MODERNGEKKO_WARIO_MENU_TEST_PAD"))
      {
        // MODERNGEKKO_WARIO_MENU_TEST_PAD: "Reset controls to defaults" (writes GCPadNew.ini).
        ResetPadDefaults();
        g_wario_menu_snapshot.store(true);  // a second picture, after the reset
        test_stage = 6;
      }
      else if (test_stage == 2 && test_time > 9.0f && std::getenv("MODERNGEKKO_WARIO_MENU_TEST_RESTART"))
      {
        // MODERNGEKKO_WARIO_MENU_TEST_RESTART: press Restart now after the snapshot.
        Restart();
        test_stage = 3;
      }
    }
  }
  SyncPadDevices(dt);
  PollBinding(dt);
  const bool binding = s_detector != nullptr;  // waiting for a new button: pad / Tab go there
  if (!binding && ((pressed & PAD_BACK) || (tab && !s_previous_tab)))
    SetOpen(!s_open);
  s_previous_tab = tab;
  const bool idle = !binding && !ImGui::IsPopupOpen("", ImGuiPopupFlags_AnyPopupId) &&
                    !ImGui::IsAnyItemActive();
  if (s_open && (pressed & PAD_B) && idle)
    SetOpen(false);
  if (s_open && (pressed & (PAD_LB | PAD_RB)) && idle)
  {
    s_tab = (s_tab + ((pressed & PAD_RB) ? 1 : kTabCount - 1)) % kTabCount;
    s_jump = s_tab;
    s_tab_scroll = true;
    ImGui::SetNavCursorVisible(true);
  }
  s_fullscreen_wait = std::max(s_fullscreen_wait - dt, 0.0f);
  s_anim = std::clamp(s_anim + (s_open ? dt : -dt) / 0.18f, 0.0f, 1.0f);
  g_wario_menu_open.store(s_open || s_anim > 0.0f);
  FeedNavigation(pad, s_open && !binding);
#ifdef _WIN32
  // Game module exports are looked up again while missing: the menu can tick before
  // gGWWE01_recomp.dll is loaded.
  const auto module_s32 = [](volatile s32*& slot, const char* name) {
    if (!slot)
      slot = WarioModuleS32(name);
    return slot;
  };
  // Game audio mix (docs/engine/AUDIO.md), written every frame. A module built before the exports
  // existed has none, and the Music / SFX controls say so.
  static volatile s32* audio_music = nullptr;
  static volatile s32* audio_sfx = nullptr;
  static volatile s32* audio_mute_pause = nullptr;
  s_audio_exports = module_s32(audio_music, "wario_audio_music") &&
                    module_s32(audio_sfx, "wario_audio_sfx") &&
                    module_s32(audio_mute_pause, "wario_audio_mute_pause_music");
  if (s_audio_exports)
  {
    *audio_music = s_settings.music;
    *audio_sfx = s_settings.sfx;
    *audio_mute_pause = s_settings.mute_pause_music ? 1 : 0;
  }
  // The game module tags its matrices only while object interpolation is wanted, so the default
  // GX command stream stays exactly the original.
  // Cheats (docs/modding/CHEATS.md): toggles and jump height every frame (the module resets them
  // each launch); the one-shots are only written when their button is pressed.
  static volatile s32* cheat_noclip = nullptr;
  static volatile s32* cheat_punch = nullptr;
  static volatile s32* cheat_jump = nullptr;
  s_cheat_exports = module_s32(cheat_noclip, "wario_cheat_noclip") &&
                    module_s32(cheat_punch, "wario_cheat_super_punch") &&
                    module_s32(cheat_jump, "wario_cheat_jump_percent") &&
                    module_s32(s_cheat_unlock, "wario_cheat_unlock_stages") &&
                    module_s32(s_cheat_collect, "wario_cheat_collect_all");
  if (s_cheat_exports)
  {
    *cheat_noclip = s_settings.noclip ? 1 : 0;
    *cheat_punch = s_settings.super_punch ? 1 : 0;
    *cheat_jump = s_settings.jump_percent;
  }
  static volatile s32* tagging = nullptr;
  if (module_s32(tagging, "wario_fps_tagging"))
    *tagging = (g_wario_fps_multiplier.load() > 1 && g_wario_fps_objects.load()) ? 1 : 0;
#endif
  static float auto_timer = 0.0f;
  if (s_settings.frame_rate == 4 && (auto_timer += dt) > 2.0f)
  {
    auto_timer = 0.0f;
    QueueFps();
  }
  PollExtract();
  // F12: bug report snapshot, with or without the menu open.
  static bool previous_f12 = false;
  const bool f12 = KeyDown(VK_F12);
  if (f12 && !previous_f12 && ReportSnapshotAvailable())
    SaveReportSnapshot();
  previous_f12 = f12;
  if (s_anim > 0.0f)
    DrawPanel(static_cast<float>(width), static_cast<float>(height));
  if (s_toast_time > 0.0f)
  {
    // Small note at the bottom centre; fades out over its last half second.
    s_toast_time -= dt;
    const float font = std::clamp(18.0f * UiScale(), 10.0f, 96.0f);
    ImGui::SetNextWindowPos(ImVec2(width * 0.5f, height - font * 2.0f), ImGuiCond_Always,
                            ImVec2(0.5f, 1.0f));
    ImGui::SetNextWindowBgAlpha(0.85f);
    ImGui::PushStyleVar(ImGuiStyleVar_Alpha, std::clamp(s_toast_time / 0.5f, 0.0f, 1.0f));
    ImGui::PushStyleVar(ImGuiStyleVar_WindowRounding, font * 0.4f);
    ImGui::PushStyleVar(ImGuiStyleVar_WindowPadding, ImVec2(font * 0.9f, font * 0.5f));
    if (ImGui::Begin("##wario_toast", nullptr,
                     ImGuiWindowFlags_NoDecoration | ImGuiWindowFlags_AlwaysAutoResize |
                         ImGuiWindowFlags_NoInputs | ImGuiWindowFlags_NoNav |
                         ImGuiWindowFlags_NoFocusOnAppearing | ImGuiWindowFlags_NoSavedSettings))
    {
      ImGui::PushFont(nullptr, font);
      ImGui::TextUnformatted(s_toast.c_str());
      ImGui::PopFont();
    }
    ImGui::End();
    ImGui::PopStyleVar(3);
  }
}

// Called by Presenter::Present after Finalize, outside the ImGui lock.
void WarioMenuApplyPending()
{
  std::vector<std::function<void()>> pending;
  pending.swap(WarioMenu::s_pending);
  // Shutting down: drop the changes (they are in WarioWorld.ini already, or will be on close).
  if (!Config::GetLayer(Config::LayerType::CurrentRun))
    return;
  for (auto& apply : pending)
    apply();
  WarioMenu::ApplyHdrGrading();
}
// ---------------------------------------------------------------------------
"""

OSUI_DRAW_OLD = "  DrawChallengesAndLeaderboards();\n  ImGui::Render();"
OSUI_DRAW_NEW = ("  DrawChallengesAndLeaderboards();\n"
                 "  WarioMenuDraw(m_backbuffer_width, m_backbuffer_height);\n"
                 "  ImGui::Render();")

OSUI_PIXEL_OLD = "FramebufferShaderGen::GenerateImGuiPixelShader(linear_space_output)"
OSUI_PIXEL_NEW = "WarioImGuiPixelShader(linear_space_output)"

OSUI_REBUILD_OLD = """void OnScreenUI::DrawImGui()
{
  ImDrawData* draw_data = ImGui::GetDrawData();
  if (!draw_data)
    return;
"""
OSUI_REBUILD_NEW = OSUI_REBUILD_OLD + """
  // Wario menu (scripts/tool_fix_wario_menu.py): rebuild the ImGui pipeline when the framebuffer
  // it draws into changes format (HDR switched on or off) or the HDR menu brightness changes.
  if (const AbstractFramebuffer* target = g_gfx->GetCurrentFramebuffer())
  {
    const AbstractTextureFormat format = target->GetColorFormat();
    const float nits = g_wario_menu_nits.load();
    if (format != AbstractTextureFormat::Undefined &&
        (format != s_wario_imgui_built_format ||
         (format == AbstractTextureFormat::RGBA16F && nits != s_wario_menu_nits_built)))
    {
      s_wario_imgui_format = format;
      RecompileImGuiPipeline();
      static const bool log = std::getenv("MODERNGEKKO_WARIO_MENU_TEST") != nullptr;
      if (log)
      {
        std::fprintf(stderr, "wario-menu: ImGui pipeline rebuilt for %s, menu brightness %.0f nits\\n",
                     format == AbstractTextureFormat::RGBA16F ? "RGBA16F (HDR)" : "SDR", nits);
      }
    }
  }
"""

OSUI_LINEAR_OLD = """  const bool linear_space_output =
      g_presenter->GetBackbufferFormat() == AbstractTextureFormat::RGBA16F;
"""
OSUI_LINEAR_NEW = "  const bool linear_space_output = WarioImGuiFormat() == AbstractTextureFormat::RGBA16F;\n"

OSUI_FORMAT_OLD = "  pconfig.framebuffer_state.color_texture_format = g_presenter->GetBackbufferFormat();\n"
OSUI_FORMAT_NEW = "  pconfig.framebuffer_state.color_texture_format = s_wario_imgui_built_format;\n"

PRESENT_DECL_OLD = '#include "VideoCommon/VideoEvents.h"\n'
PRESENT_DECL_NEW = (PRESENT_DECL_OLD + "\n// Wario World in-game menu (scripts/tool_fix_wario_menu.py).\n"
                    "void WarioMenuApplyPending();\n#include <atomic>\nextern std::atomic<bool> g_wario_menu_snapshot;\n")

PRESENT_APPLY_OLD = """  if (m_onscreen_ui)
  {
    m_onscreen_ui->Finalize();
    if (backbuffer_bound)
      m_onscreen_ui->DrawImGui();
  }
"""
PRESENT_APPLY_NEW = PRESENT_APPLY_OLD + """  WarioMenuApplyPending();
  if (m_onscreen_ui && g_wario_menu_snapshot.exchange(false))
  {
    // Diagnostics (MODERNGEKKO_WARIO_MENU_TEST): game picture + menu, rendered offscreen.
    const char* path = std::getenv("MODERNGEKKO_WARIO_MENU_TEST");
    const TextureConfig config(m_backbuffer_width, m_backbuffer_height, 1, 1, 1,
                               AbstractTextureFormat::RGBA8, AbstractTextureFlag_RenderTarget,
                               AbstractTextureType::Texture_2DArray);
    auto texture = g_gfx->CreateTexture(config, "Wario menu snapshot");
    auto framebuffer = texture ? g_gfx->CreateFramebuffer(texture.get(), nullptr) : nullptr;
    if (framebuffer && path)
    {
      g_gfx->SetAndClearFramebuffer(framebuffer.get(), {{0.0f, 0.0f, 0.0f, 1.0f}});
      if (m_xfb_entry)
        RenderXFBToScreen(GetTargetRectangle(), m_xfb_entry->texture.get(), AdjustForCustomCrop(m_xfb_rect));
      m_onscreen_ui->DrawImGui();
      texture->Save(path, 0);
      g_gfx->BindBackbuffer({{0.0f, 0.0f, 0.0f, 1.0f}});
    }
  }
"""

PAD_DECL_OLD = '#include "InputCommon/InputConfig.h"\n'
PAD_DECL_NEW = (PAD_DECL_OLD + "\n#include <atomic>\n\n"
                "// Wario World in-game menu: the game sees a neutral pad while it is open.\n"
                "extern std::atomic<bool> g_wario_menu_open;\n")

PAD_STATUS_OLD = """GCPadStatus GetStatus(int pad_num)
{
  return static_cast<GCPad*>(s_config.GetController(pad_num))->GetInput();"""
PAD_STATUS_NEW = """GCPadStatus GetStatus(int pad_num)
{
  if (g_wario_menu_open.load(std::memory_order_relaxed))
    return GCPadStatus{};
  return static_cast<GCPad*>(s_config.GetController(pad_num))->GetInput();"""

WIN_DECL_OLD = '#include "resource.h"\n'
WIN_DECL_NEW = (WIN_DECL_OLD + "\n#include <atomic>\n\n"
                "// Wario World in-game menu (VideoCommon/OnScreenUI.cpp).\n"
                "extern void* g_wario_hwnd;\n"
                "extern std::atomic<int> g_wario_mouse_wheel;\n")

WIN_CREATE_OLD = "      // Remove rounded corners from the render window on Windows 11\n"
WIN_CREATE_NEW = "      g_wario_hwnd = hwnd;\n" + WIN_CREATE_OLD

WIN_MOUSE_OLD = """  case WM_SIZE:
  {
    if (g_presenter)
      g_presenter->ResizeSurface();
  }
  break;
"""
WIN_MOUSE_NEW = WIN_MOUSE_OLD + """
  // Mouse for the in-game menu (ImGui overlay).
  case WM_MOUSEMOVE:
    if (g_presenter)
    {
      g_presenter->SetMousePos(static_cast<float>(static_cast<short>(LOWORD(lParam))),
                               static_cast<float>(static_cast<short>(HIWORD(lParam))));
    }
    break;

  case WM_LBUTTONDOWN:
  case WM_LBUTTONUP:
  case WM_RBUTTONDOWN:
  case WM_RBUTTONUP:
    if (g_presenter)
    {
      g_presenter->SetMousePress(((wParam & MK_LBUTTON) ? 1u : 0u) |
                                 ((wParam & MK_RBUTTON) ? 2u : 0u));
    }
    break;

  case WM_MOUSEWHEEL:
    g_wario_mouse_wheel += GET_WHEEL_DELTA_WPARAM(wParam);
    break;
"""


HDR_SHADER = r"""// Wario World HDR tuning (scripts/tool_fix_wario_menu.py; values come from the in-game menu).
// The menu loads it only while HDR output is on and a value differs from its default; every
// default is the identity (white level 0 = off). Highlight boost follows Dolphin's AutoHDR.glsl (Filoppi's PumboAutoHDR).

/*
[configuration]

[OptionRangeFloat]
GUIName = Peak brightness (nits)
OptionName = WW_PEAK_NITS
MinValue = 400
MaxValue = 4000
StepAmount = 10
DefaultValue = 1000

[OptionRangeFloat]
GUIName = Highlight boost
OptionName = WW_HIGHLIGHTS
MinValue = 0
MaxValue = 1
StepAmount = 0.01
DefaultValue = 0

[OptionRangeFloat]
GUIName = Saturation
OptionName = WW_SATURATION
MinValue = 0
MaxValue = 2
StepAmount = 0.01
DefaultValue = 1

[OptionRangeFloat]
GUIName = Vibrance
OptionName = WW_VIBRANCE
MinValue = -1
MaxValue = 1
StepAmount = 0.01
DefaultValue = 0

[OptionRangeFloat]
GUIName = White level (nits, 0 = off)
OptionName = WW_WHITE_NITS
MinValue = 0
MaxValue = 4000
StepAmount = 100
DefaultValue = 0

[OptionRangeFloat]
GUIName = Contrast
OptionName = WW_CONTRAST
MinValue = 0.5
MaxValue = 1.5
StepAmount = 0.01
DefaultValue = 1

[OptionRangeFloat]
GUIName = Gamma
OptionName = WW_GAMMA
MinValue = 0.7
MaxValue = 1.3
StepAmount = 0.01
DefaultValue = 1

[OptionRangeFloat]
GUIName = Black level
OptionName = WW_BLACK
MinValue = -0.1
MaxValue = 0.1
StepAmount = 0.01
DefaultValue = 0

[/configuration]
*/

float luminance(float3 color)
{
	return dot(color, float3(0.2126, 0.7152, 0.0722));
}

void main()
{
	float4 color = Sample();

	// SDR output: nothing to do
	if (!OptionEnabled(hdr_output) || !OptionEnabled(linear_space_output))
	{
		SetOutput(color);
		return;
	}

	// Linear, 1 = paper white (the game's SDR white)
	const float paper_white = hdr_paper_white_nits / hdr_sdr_white_nits;
	float3 c = color.rgb / paper_white;

	// Black level: positive crushes, negative lifts
	c = max((c - WW_BLACK) / (1.0 - WW_BLACK), 0.0);
	c = pow(c, float3(WW_GAMMA, WW_GAMMA, WW_GAMMA));
	// Contrast around middle grey
	c = 0.18 * pow(c / 0.18, float3(WW_CONTRAST, WW_CONTRAST, WW_CONTRAST));

	const float y = luminance(c);
	c = max(y + (c - y) * WW_SATURATION, 0.0);

	// Vibrance: saturation weighted towards muted colours, so vivid colours change little; skin
	// tones (red > green > blue with green about 40 % of the way) are partly protected
	if (WW_VIBRANCE != 0.0)
	{
		const float top = max(c.r, max(c.g, c.b));
		const float bottom = min(c.r, min(c.g, c.b));
		const float chroma = top > 0.0 ? (top - bottom) / top : 0.0;
		float amount = WW_VIBRANCE * (1.0 - chroma);
		if (c.r > c.g && c.g > c.b)
		{
			const float hue = (c.g - c.b) / max(c.r - c.b, 0.00001);
			amount *= 1.0 - 0.6 * clamp(1.0 - abs(hue - 0.4) / 0.3, 0.0, 1.0);
		}
		const float v = luminance(c);
		c = max(v + (c - v) * (1.0 + amount), 0.0);
	}

	// Highlight boost (AutoHDR, shoulder from black, power 2.5): bright SDR colours stretch
	// towards the peak brightness
	const float sdr = luminance(c);
	if (WW_HIGHLIGHTS > 0.0 && sdr > 0.0)
	{
		const float max_white = max(WW_PEAK_NITS / hdr_paper_white_nits, 1.0);
		const float shoulder = clamp(sdr, 0.0, 1.0);
		const float extra = pow(shoulder, 2.5) * (max_white - 1.0) * WW_HIGHLIGHTS;
		c *= (sdr + extra) / sdr;
	}

	// White level: nothing gets brighter than this; above 75 % of it, highlights roll off smoothly
	// (slope 1 at the knee, so nothing below it changes)
	if (WW_WHITE_NITS > 0.0)
	{
		const float white = WW_WHITE_NITS / hdr_paper_white_nits;
		const float knee = 0.75 * white;
		const float lum = luminance(c);
		if (lum > knee)
		{
			const float range = white - knee;
			c *= (knee + range * (1.0 - exp(-(lum - knee) / range))) / lum;
		}
	}

	SetOutput(float4(c * paper_white, color.a));
}
"""


def apply(replace, runtime):
    dolphin = runtime / "vendor/dolphin/Source/Core"
    shader = runtime / "vendor/dolphin/Data/Sys/Shaders/WarioHDR.glsl"
    if not shader.is_file() or shader.read_text(encoding="utf-8") != HDR_SHADER:
        shader.write_text(HDR_SHADER, encoding="utf-8", newline="\n")
    replace(dolphin / "VideoCommon/OnScreenUI.cpp", OSUI_INCLUDE_OLD, OSUI_INCLUDE_NEW)
    replace(dolphin / "VideoCommon/OnScreenUI.cpp", OSUI_DRAW_OLD, OSUI_DRAW_NEW)
    replace(dolphin / "VideoCommon/OnScreenUI.cpp", OSUI_PIXEL_OLD, OSUI_PIXEL_NEW)
    replace(dolphin / "VideoCommon/OnScreenUI.cpp", OSUI_REBUILD_OLD, OSUI_REBUILD_NEW)
    replace(dolphin / "VideoCommon/OnScreenUI.cpp", OSUI_LINEAR_OLD, OSUI_LINEAR_NEW)
    replace(dolphin / "VideoCommon/OnScreenUI.cpp", OSUI_FORMAT_OLD, OSUI_FORMAT_NEW)
    replace(dolphin / "VideoCommon/Present.cpp", PRESENT_DECL_OLD, PRESENT_DECL_NEW)
    replace(dolphin / "VideoCommon/Present.cpp", PRESENT_APPLY_OLD, PRESENT_APPLY_NEW)
    replace(dolphin / "Core/HW/GCPad.cpp", PAD_DECL_OLD, PAD_DECL_NEW)
    replace(dolphin / "Core/HW/GCPad.cpp", PAD_STATUS_OLD, PAD_STATUS_NEW)
    replace(dolphin / "DolphinNoGUI/PlatformWin32.cpp", WIN_DECL_OLD, WIN_DECL_NEW)
    replace(dolphin / "DolphinNoGUI/PlatformWin32.cpp", WIN_CREATE_OLD, WIN_CREATE_NEW)
    replace(dolphin / "DolphinNoGUI/PlatformWin32.cpp", WIN_MOUSE_OLD, WIN_MOUSE_NEW)
