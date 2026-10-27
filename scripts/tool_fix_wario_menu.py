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
- fullscreen, HD textures, HDR output (Vulkan only)
- frame rate 60/120/180/240/auto (g_wario_fps_multiplier -> scripts/tool_fix_wario_fps.py)
- volume, moon jump cheat (hold A), quit

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
#include <functional>
#include <string>
#include <vector>

#include "AudioCommon/AudioCommon.h"
#include "Core/HW/Memmap.h"

#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <windows.h>
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
void* g_wario_hwnd = nullptr;
extern std::atomic<int> g_wario_fps_multiplier;  // VideoCommon/BPStructs.cpp (1 = off)
extern std::atomic<bool> g_wario_fps_objects;     // false = camera only

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
  int motion = 0;      // 0 = camera only, 1 = camera + objects
  int volume = 100;
  bool moon_jump = false;
  float moon_speed = 2.0f;
};

constexpr const char* kResolutionNames[] = {"Auto (fits window)", "Native 1x (accurate)", "2x",
                                            "3x", "4x", "5x", "6x", "8x"};
constexpr int kResolutionScales[] = {0, 1, 2, 3, 4, 5, 6, 8};
constexpr const char* kFrameRateNames[] = {"Original 60 (accurate)", "120 (2x)", "180 (3x)",
                                           "240 (4x)", "Auto (match screen)"};
constexpr const char* kFrameRateKeys[] = {"60", "120", "180", "240", "auto"};
constexpr const char* kMotionNames[] = {"Camera only (clean)", "Camera + objects (experimental)"};
constexpr const char* kMotionKeys[] = {"camera", "objects"};
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
bool s_loaded = false;
bool s_open = false;
float s_anim = 0.0f;  // 0 closed .. 1 open
bool s_focus_next = false;
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
                 "volume=%d\nmoon_jump=%d\nmoon_speed=%.2f\n",
                 kResolutionScales[s.resolution], kAspects[s.aspect].key, s.fullscreen,
                 s.hd_textures, s.hdr, kFrameRateKeys[s.frame_rate], kMotionKeys[s.motion], s.volume, s.moon_jump,
                 s.moon_speed);
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
  s.motion = g_wario_fps_objects.load() ? 1 : 0;
  s.hd_textures = Config::Get(Config::GFX_HIRES_TEXTURES);
  s.hdr = Config::Get(Config::GFX_ENHANCE_HDR_OUTPUT);
  s.volume = Config::Get(Config::MAIN_AUDIO_VOLUME);
  const int scale = Config::Get(Config::GFX_EFB_SCALE);
  for (int i = 0; i < static_cast<int>(std::size(kResolutionScales)); ++i)
    if (kResolutionScales[i] == scale)
      s.resolution = i;
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
      s.motion = value == "objects" ? 1 : 0;
    else if (key == "volume")
      s.volume = std::clamp(number, 0, 100);
    else if (key == "moon_jump")
      s.moon_jump = number != 0;
    else if (key == "moon_speed")
      s.moon_speed = std::clamp(static_cast<float>(std::atof(value.c_str())), 0.5f, 8.0f);
  }
  std::fclose(file);
  return saved;
}

bool IsVulkan()
{
  return Config::Get(Config::MAIN_GFX_BACKEND) == "Vulkan";
}

void QueueResolution()
{
  const int scale = kResolutionScales[s_settings.resolution];
  s_pending.push_back([scale] { Config::SetCurrent(Config::GFX_EFB_SCALE, scale); });
}

void QueueAspect()
{
  const Aspect aspect = kAspects[s_settings.aspect];
  s_pending.push_back([aspect] {
    g_wario_aspect_target.store(aspect.ratio);
    if (aspect.ratio < 0.0f)
    {
      Config::SetCurrent(Config::GFX_ASPECT_RATIO, AspectMode::Stretch);
    }
    else if (aspect.ratio == 0.0f)
    {
      Config::SetCurrent(Config::GFX_ASPECT_RATIO, AspectMode::ForceStandard);
    }
    else
    {
      Config::SetCurrent(Config::GFX_CUSTOM_ASPECT_RATIO_WIDTH, aspect.width);
      Config::SetCurrent(Config::GFX_CUSTOM_ASPECT_RATIO_HEIGHT, aspect.height);
      Config::SetCurrent(Config::GFX_ASPECT_RATIO, AspectMode::Custom);
    }
  });
}

void QueueHd()
{
  const bool hd = s_settings.hd_textures;
  s_pending.push_back([hd] { Config::SetCurrent(Config::GFX_HIRES_TEXTURES, hd); });
}

void QueueHdr()
{
  const bool hdr = s_settings.hdr && IsVulkan();
  s_pending.push_back([hdr] { Config::SetCurrent(Config::GFX_ENHANCE_HDR_OUTPUT, hdr); });
}

void QueueVolume()
{
  const int volume = s_settings.volume;
  s_pending.push_back([volume] {
    Config::SetCurrent(Config::MAIN_AUDIO_VOLUME, volume);
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

void ToggleFullscreen()
{
#ifdef _WIN32
  if (g_wario_hwnd)
    PostMessageW(static_cast<HWND>(g_wario_hwnd), WM_KEYDOWN, VK_F11, 0);
#endif
}

void Quit()
{
#ifdef _WIN32
  if (g_wario_hwnd)
    PostMessageW(static_cast<HWND>(g_wario_hwnd), WM_CLOSE, 0, 0);
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
                   PAD_BACK = 0x0020, PAD_A = 0x1000, PAD_B = 0x2000;

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

// Moon jump: while A (or keyboard X) is held, Wario's height rises (player actor
// [0x801C5820], y at +0x18). Changes game memory; off by default.
void MoonJump(float dt, bool a_held)
{
  if (!s_settings.moon_jump || g_wario_menu_open.load() || !a_held)
    return;
  auto& memory = Core::System::GetInstance().GetMemory();
  const u32 player = memory.Read_U32(0x801C5820u);
  if (player < 0x80000000u || player >= 0x817FFF00u)
    return;
  u32 bits = memory.Read_U32(player + 0x18u);
  float y;
  std::memcpy(&y, &bits, sizeof(y));
  if (!std::isfinite(y))
    return;
  y += s_settings.moon_speed * 20.0f * std::min(dt, 0.05f);
  std::memcpy(&bits, &y, sizeof(bits));
  memory.Write_U32(bits, player + 0x18u);
}

void SetOpen(bool open)
{
  if (open == s_open)
    return;
  s_open = open;
  if (open)
    s_focus_next = true;
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

void DrawPanel(float width, float height)
{
  Settings& s = s_settings;
  const float panel = width * 0.5f;
  const float t = std::clamp(s_anim, 0.0f, 1.0f);
  const float ease = 1.0f - (1.0f - t) * (1.0f - t) * (1.0f - t);
  ImGui::SetNextWindowPos(ImVec2(-panel * (1.0f - ease), 0.0f));
  ImGui::SetNextWindowSize(ImVec2(panel, height));
  ImGui::SetNextWindowBgAlpha(0.9f * ease);
  if (s_focus_next)
  {
    ImGui::SetNextWindowFocus();
    s_focus_next = false;
  }
  ImGui::PushStyleVar(ImGuiStyleVar_WindowRounding, 0.0f);
  ImGui::PushStyleVar(ImGuiStyleVar_WindowPadding, ImVec2(panel * 0.06f, height * 0.04f));
  ImGui::PushStyleVar(ImGuiStyleVar_ItemSpacing, ImVec2(panel * 0.02f, height * 0.012f));
  ImGui::PushStyleVar(ImGuiStyleVar_FramePadding, ImVec2(panel * 0.015f, height * 0.008f));
  ImGui::PushStyleVar(ImGuiStyleVar_Alpha, std::max(ease, 0.01f));
  const ImGuiWindowFlags flags = ImGuiWindowFlags_NoTitleBar | ImGuiWindowFlags_NoResize |
                                 ImGuiWindowFlags_NoMove | ImGuiWindowFlags_NoCollapse |
                                 ImGuiWindowFlags_NoSavedSettings;
  if (ImGui::Begin("##wario_menu", nullptr, flags))
  {
    const float font = std::clamp(height * 0.032f, 14.0f, 64.0f);
    ImGui::PushFont(nullptr, font * 1.6f);
    ImGui::TextColored(ImVec4(1.0f, 0.82f, 0.1f, 1.0f), "WARIO WORLD");
    ImGui::PopFont();
    ImGui::PushFont(nullptr, font);
    ImGui::TextDisabled("Settings apply immediately and are saved.");
    ImGui::Spacing();
    const float label = panel * 0.38f;
    const float field = panel * 0.82f - label;
    const auto row = [&](const char* text) {
      ImGui::AlignTextToFramePadding();
      ImGui::TextUnformatted(text);
      ImGui::SameLine(label + panel * 0.06f);
      ImGui::SetNextItemWidth(field);
    };
    bool changed = false;
    if (ImGui::Button("Resume", ImVec2(panel * 0.88f, 0.0f)))
      SetOpen(false);

    ImGui::SeparatorText("Display");
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
    if (ImGui::Checkbox("Fullscreen", &s.fullscreen))
    {
      ToggleFullscreen();
      changed = true;
    }
    if (ImGui::Checkbox("HD textures (from the HD folder)", &s.hd_textures))
    {
      QueueHd();
      changed = true;
    }
    ImGui::BeginDisabled(!IsVulkan());
    if (ImGui::Checkbox(IsVulkan() ? "HDR output" : "HDR output (needs Vulkan, set in launcher)",
                        &s.hdr))
    {
      QueueHdr();
      changed = true;
    }
    ImGui::EndDisabled();

    ImGui::SeparatorText("Motion");
    row("Frame rate");
    if (ImGui::Combo("##frame_rate", &s.frame_rate, kFrameRateNames,
                     static_cast<int>(std::size(kFrameRateNames))))
    {
      QueueFps();
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
    ImGui::TextDisabled("Extra frames are interpolated; game speed is unchanged.");
    ImGui::TextDisabled("Adds ~8-12 ms delay. Pick no more than your screen's refresh rate.");

    ImGui::SeparatorText("Audio");
    row("Volume");
    if (ImGui::SliderInt("##volume", &s.volume, 0, 100, "%d%%"))
      QueueVolume();
    if (ImGui::IsItemDeactivatedAfterEdit())
      changed = true;

    ImGui::SeparatorText("Cheats");
    if (ImGui::Checkbox("Moon jump (hold A / X)", &s.moon_jump))
      changed = true;
    ImGui::BeginDisabled(!s.moon_jump);
    row("Rise speed");
    ImGui::SliderFloat("##moon", &s.moon_speed, 0.5f, 8.0f, "%.1f");
    if (ImGui::IsItemDeactivatedAfterEdit())
      changed = true;
    ImGui::EndDisabled();

    ImGui::Spacing();
    ImGui::Separator();
    if (ImGui::Button("Quit game", ImVec2(panel * 0.88f, 0.0f)))
      Quit();
    ImGui::Spacing();
    ImGui::TextDisabled("Back / B: close    A: select    D-pad / stick: move");
    ImGui::TextDisabled("Mouse works too. Tab opens and closes on the keyboard.");
    ImGui::PopFont();
    if (changed)
      Save();
  }
  ImGui::End();
  ImGui::PopStyleVar(5);
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
  if ((pressed & PAD_BACK) || (tab && !s_previous_tab))
    SetOpen(!s_open);
  s_previous_tab = tab;
  if (s_open && (pressed & PAD_B) && !ImGui::IsPopupOpen("", ImGuiPopupFlags_AnyPopupId) &&
      !ImGui::IsAnyItemActive())
  {
    SetOpen(false);
  }
  s_anim = std::clamp(s_anim + (s_open ? dt : -dt) / 0.18f, 0.0f, 1.0f);
  g_wario_menu_open.store(s_open || s_anim > 0.0f);
  FeedNavigation(pad, s_open);
  MoonJump(dt, (pad.buttons & PAD_A) != 0 || KeyDown('X'));
  static float auto_timer = 0.0f;
  if (s_settings.frame_rate == 4 && (auto_timer += dt) > 2.0f)
  {
    auto_timer = 0.0f;
    QueueFps();
  }
  if (s_anim > 0.0f)
    DrawPanel(static_cast<float>(width), static_cast<float>(height));
}

// Called by Presenter::Present after Finalize, outside the ImGui lock.
void WarioMenuApplyPending()
{
  std::vector<std::function<void()>> pending;
  pending.swap(WarioMenu::s_pending);
  for (auto& apply : pending)
    apply();
}
// ---------------------------------------------------------------------------
"""

OSUI_DRAW_OLD = "  DrawChallengesAndLeaderboards();\n  ImGui::Render();"
OSUI_DRAW_NEW = ("  DrawChallengesAndLeaderboards();\n"
                 "  WarioMenuDraw(m_backbuffer_width, m_backbuffer_height);\n"
                 "  ImGui::Render();")

PRESENT_DECL_OLD = '#include "VideoCommon/VideoEvents.h"\n'
PRESENT_DECL_NEW = (PRESENT_DECL_OLD + "\n// Wario World in-game menu (scripts/tool_fix_wario_menu.py).\n"
                    "void WarioMenuApplyPending();\n")

PRESENT_APPLY_OLD = """  if (m_onscreen_ui)
  {
    m_onscreen_ui->Finalize();
    if (backbuffer_bound)
      m_onscreen_ui->DrawImGui();
  }
"""
PRESENT_APPLY_NEW = PRESENT_APPLY_OLD + "  WarioMenuApplyPending();\n"

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


def apply(replace, runtime):
    dolphin = runtime / "vendor/dolphin/Source/Core"
    replace(dolphin / "VideoCommon/OnScreenUI.cpp", OSUI_INCLUDE_OLD, OSUI_INCLUDE_NEW)
    replace(dolphin / "VideoCommon/OnScreenUI.cpp", OSUI_DRAW_OLD, OSUI_DRAW_NEW)
    replace(dolphin / "VideoCommon/Present.cpp", PRESENT_DECL_OLD, PRESENT_DECL_NEW)
    replace(dolphin / "VideoCommon/Present.cpp", PRESENT_APPLY_OLD, PRESENT_APPLY_NEW)
    replace(dolphin / "Core/HW/GCPad.cpp", PAD_DECL_OLD, PAD_DECL_NEW)
    replace(dolphin / "Core/HW/GCPad.cpp", PAD_STATUS_OLD, PAD_STATUS_NEW)
    replace(dolphin / "DolphinNoGUI/PlatformWin32.cpp", WIN_DECL_OLD, WIN_DECL_NEW)
    replace(dolphin / "DolphinNoGUI/PlatformWin32.cpp", WIN_CREATE_OLD, WIN_CREATE_NEW)
    replace(dolphin / "DolphinNoGUI/PlatformWin32.cpp", WIN_MOUSE_OLD, WIN_MOUSE_NEW)
