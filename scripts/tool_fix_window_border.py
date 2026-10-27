"""No sunken window edge in fullscreen (2026-10-27).

DolphinNoGUI's Win32 window is created with WS_EX_CLIENTEDGE, a 3D sunken border drawn inside the
window. Fullscreen only replaces GWL_STYLE, so the extended style stayed and showed as a thin light
line along the top, left and bottom screen edges (human report: "white border"). Dropping it
leaves the windowed frame to the normal caption/frame styles and fullscreen edge-to-edge. Not
visible in automated captures (they read the rendered frame, not the window).
"""

CREATE_OLD = "m_hwnd = CreateWindowEx(WS_EX_CLIENTEDGE | (m_hidden ? WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE : 0),"
CREATE_NEW = "m_hwnd = CreateWindowEx((m_hidden ? WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE : 0),"


def apply(replace, runtime):
    # fix_silent_headless (apply_tool_fixes.py) now writes the edge-free line itself; this converts
    # source trees patched before 2026-10-27 and is a no-op otherwise.
    path = runtime / "vendor/dolphin/Source/Core/DolphinNoGUI/PlatformWin32.cpp"
    if CREATE_OLD in path.read_text(encoding="utf-8"):
        replace(path, CREATE_OLD, CREATE_NEW)
