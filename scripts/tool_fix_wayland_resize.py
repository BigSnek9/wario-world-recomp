"""Vulkan swap chain size on Wayland (Linux).

A Wayland surface leaves its extent to the client (currentExtent = UINT32_MAX), and
VKSwapChain::CreateSwapChain then reused the presenter's previous backbuffer size. A resize,
including the switch to fullscreen at start-up, therefore recreated the swap chain at the old
window size: on a 1280x720 fullscreen output the backbuffer stayed 1556x934 and the picture
was shown off centre and cropped. The Wayland window now passes the size the compositor
configured through Presenter::ResizeSurface(width, height), and the swap chain takes it.

Ported from kobayashi90/RecompCore commit 794f2080237b5042bbfe15884a17998b4c288cb2
(Presenter::ResizeSurface(int, int), Presenter::TakeRequestedSurfaceSize, the VKSwapChain size
selection and the PlatformWayland call), without that commit's diagnostic prints.

That covers resizes after start-up only. The first configure, which already carries the
fullscreen size when the starter asks for fullscreen, arrives in PlatformWayland::Init before
the presenter exists, and the initial swap chain reads MAIN_RENDER_WINDOW_WIDTH/HEIGHT. Init
therefore puts the configured size into the current-run config layer (not saved to Dolphin.ini).
"""

PRESENT_H_DECL_OLD = "  void ResizeSurface();\n"
PRESENT_H_DECL_NEW = """  void ResizeSurface(int width = 0, int height = 0);
  // Pops the size passed to ResizeSurface (0x0 when none is pending). Wayland surfaces leave the
  // extent to the client, so the swap chain takes the size the compositor configured.
  void TakeRequestedSurfaceSize(int& width, int& height);
"""

PRESENT_H_MEMBER_OLD = "  Common::Flag m_surface_resized;\n"
PRESENT_H_MEMBER_NEW = PRESENT_H_MEMBER_OLD + """  int m_requested_surface_width = 0;
  int m_requested_surface_height = 0;
"""

PRESENT_CPP_OLD = """void Presenter::ResizeSurface()
{
  std::lock_guard<std::mutex> lock(m_swap_mutex);
  m_surface_resized.Set();
}
"""
PRESENT_CPP_NEW = """void Presenter::ResizeSurface(int width, int height)
{
  std::lock_guard<std::mutex> lock(m_swap_mutex);
  m_surface_resized.Set();
  m_requested_surface_width = width > 0 ? width : 0;
  m_requested_surface_height = height > 0 ? height : 0;
}

void Presenter::TakeRequestedSurfaceSize(int& width, int& height)
{
  std::lock_guard<std::mutex> lock(m_swap_mutex);
  width = m_requested_surface_width;
  height = m_requested_surface_height;
  m_requested_surface_width = 0;
  m_requested_surface_height = 0;
}
"""

SWAPCHAIN_OLD = """  VkExtent2D size = surface_capabilities.currentExtent;
  if (size.width == UINT32_MAX)
  {"""
SWAPCHAIN_NEW = """  VkExtent2D size = surface_capabilities.currentExtent;
  int requested_width = 0;
  int requested_height = 0;
  if (g_presenter)
    g_presenter->TakeRequestedSurfaceSize(requested_width, requested_height);
  if (requested_width > 0 && requested_height > 0)
  {
    size.width = static_cast<uint32_t>(requested_width);
    size.height = static_cast<uint32_t>(requested_height);
  }
  else if (size.width == UINT32_MAX)
  {"""

WAYLAND_OLD = """    if (g_presenter)
      g_presenter->ResizeSurface();"""
WAYLAND_NEW = """    if (g_presenter)
      g_presenter->ResizeSurface(platform->m_width, platform->m_height);"""


WAYLAND_INIT_OLD = """  while (!m_configured)
  {
    if (wl_display_dispatch(m_display) < 0)
      return false;
  }
"""
WAYLAND_INIT_NEW = WAYLAND_INIT_OLD + """  // The initial Vulkan swap chain is created before the presenter exists and takes its size from
  // these settings; use what the compositor configured (fullscreen included).
  Config::SetCurrent(Config::MAIN_RENDER_WINDOW_WIDTH, m_width);
  Config::SetCurrent(Config::MAIN_RENDER_WINDOW_HEIGHT, m_height);
"""


def apply(replace, runtime):
    dolphin = runtime / "vendor/dolphin/Source/Core"
    replace(dolphin / "VideoCommon/Present.h", PRESENT_H_DECL_OLD, PRESENT_H_DECL_NEW)
    replace(dolphin / "VideoCommon/Present.h", PRESENT_H_MEMBER_OLD, PRESENT_H_MEMBER_NEW)
    replace(dolphin / "VideoCommon/Present.cpp", PRESENT_CPP_OLD, PRESENT_CPP_NEW)
    replace(dolphin / "VideoBackends/Vulkan/VKSwapChain.cpp", SWAPCHAIN_OLD, SWAPCHAIN_NEW)
    replace(dolphin / "DolphinNoGUI/PlatformWayland.cpp", WAYLAND_OLD, WAYLAND_NEW)
    replace(dolphin / "DolphinNoGUI/PlatformWayland.cpp", WAYLAND_INIT_OLD, WAYLAND_INIT_NEW)
