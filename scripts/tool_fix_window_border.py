"""Game window fixes (2026-10-27).

1. No sunken window edge in fullscreen. DolphinNoGUI's Win32 window is created with
   WS_EX_CLIENTEDGE, a 3D sunken border drawn inside the window. Fullscreen only replaces
   GWL_STYLE, so the extended style stayed and showed as a thin light line along the top, left and
   bottom screen edges (human report: "white border"). Not visible in automated captures (they
   read the rendered frame, not the window).

2. Clean quit. The window procedure (main thread) calls g_presenter for WM_SIZE and the in-game
   menu's mouse messages after an `if (g_presenter)` check, while the emulation thread destroys the
   presenter in VideoBackendBase::ShutdownShared. A mouse move over the window (or the resize when
   fullscreen is left) during quit then used a freed presenter: access violation inside the window
   callback, exit code 0xC000041D (human report, WER offset 0x92B08). Both sides now share
   g_wario_presenter_mutex; the window procedure only try-locks (it skips the presenter call while
   the presenter is being destroyed), so it can never deadlock the shutdown.
"""

CREATE_OLD = "m_hwnd = CreateWindowEx(WS_EX_CLIENTEDGE | (m_hidden ? WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE : 0),"
CREATE_NEW = "m_hwnd = CreateWindowEx((m_hidden ? WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE : 0),"

WIN_INCLUDE_OLD = '#include "VideoCommon/Present.h"\n'
WIN_INCLUDE_NEW = (WIN_INCLUDE_OLD + "\n#include <mutex>\n\n"
                   "// Held while VideoBackendBase::ShutdownShared destroys g_presenter.\n"
                   "extern std::mutex g_wario_presenter_mutex;\n")

WNDPROC_OLD = """  PlatformWin32* platform = reinterpret_cast<PlatformWin32*>(GetWindowLongPtr(hwnd, GWLP_USERDATA));
  switch (msg)
  {"""
WNDPROC_NEW = """  PlatformWin32* platform = reinterpret_cast<PlatformWin32*>(GetWindowLongPtr(hwnd, GWLP_USERDATA));
  // WM_SIZE and the menu's mouse messages call g_presenter, which the emulation thread destroys at
  // shutdown: skip them while that is in progress instead of touching a freed presenter.
  std::unique_lock<std::mutex> wario_presenter_lock(g_wario_presenter_mutex, std::defer_lock);
  if ((msg == WM_SIZE || (msg >= WM_MOUSEFIRST && msg <= WM_MOUSELAST)) &&
      !wario_presenter_lock.try_lock())
  {
    return DefWindowProc(hwnd, msg, wParam, lParam);
  }
  switch (msg)
  {"""

VB_INCLUDE_OLD = "#include <memory>\n#include <string>\n#include <vector>\n"
VB_INCLUDE_NEW = "#include <memory>\n#include <mutex>\n#include <string>\n#include <vector>\n"

VB_SHUTDOWN_OLD = """void VideoBackendBase::ShutdownShared()
{"""
VB_SHUTDOWN_NEW = """// Shared with DolphinNoGUI's window procedure (tool_fix_window_border.py), which uses g_presenter
// from the main thread.
std::mutex g_wario_presenter_mutex;

void VideoBackendBase::ShutdownShared()
{"""

VB_RESET_OLD = "  g_frame_dumper.reset();\n  g_presenter.reset();\n"
VB_RESET_NEW = """  g_frame_dumper.reset();
  {
    std::lock_guard<std::mutex> wario_lock(g_wario_presenter_mutex);
    g_presenter.reset();
  }
"""


def apply(replace, runtime):
    # fix_silent_headless (apply_tool_fixes.py) now writes the edge-free line itself; this converts
    # source trees patched before 2026-10-27 and is a no-op otherwise.
    dolphin = runtime / "vendor/dolphin/Source/Core"
    path = dolphin / "DolphinNoGUI/PlatformWin32.cpp"
    if CREATE_OLD in path.read_text(encoding="utf-8"):
        replace(path, CREATE_OLD, CREATE_NEW)


def apply_late(replace, runtime):
    dolphin = runtime / "vendor/dolphin/Source/Core"
    replace(dolphin / "DolphinNoGUI/PlatformWin32.cpp", WIN_INCLUDE_OLD, WIN_INCLUDE_NEW)
    replace(dolphin / "DolphinNoGUI/PlatformWin32.cpp", WNDPROC_OLD, WNDPROC_NEW)
    replace(dolphin / "VideoCommon/VideoBackendBase.cpp", VB_INCLUDE_OLD, VB_INCLUDE_NEW)
    replace(dolphin / "VideoCommon/VideoBackendBase.cpp", VB_SHUTDOWN_OLD, VB_SHUTDOWN_NEW)
    replace(dolphin / "VideoCommon/VideoBackendBase.cpp", VB_RESET_OLD, VB_RESET_NEW)
