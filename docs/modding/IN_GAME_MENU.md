# In-game menu

Status 2026-10-27: implemented (scripts/tool_fix_wario_menu.py). Hidden tests
can render it: `MODERNGEKKO_WARIO_MENU_TEST=<png>` opens the menu after 6 s
and saves the game picture with the menu on top once.
`MODERNGEKKO_WARIO_MENU_STYLE=<key>` picks the UI style and
`MODERNGEKKO_WARIO_MENU_TAB=<n>` the starting tab for such snapshots.

- **Open/close:** Back on the controller, or Tab on the keyboard. B also
  closes it (when no dropdown is open), as does Resume.
- **Look:** an ImGui panel (Dolphin's overlay) slides in from the left in
  0.18 s (ease-out). The panel has a vertical gradient, an accent glow at the
  top, an accent stripe on its right edge and a soft shadow over the game. The
  title has a drop shadow and a fading underline, and section headers have an
  accent tab, a small-caps label and a fading rule. Text is 18 px times the
  Windows display scaling of the game window's monitor times the Menu size
  setting (0.6-1.6x); the panel is 26 em wide, at most half the screen.
- **UI style** (System section, saved as `menu_style`):

  | Style | Key | Colours |
  |---|---|---|
  | Classic | `classic` | Dolphin's ImGui colours (the original look) |
  | Wario (purple & gold) | `wario` | purple panel, gold accent |
  | Midnight | `midnight` | navy, cyan accent |
  | Garlic green | `garlic` | dark green, lime accent |
  | Treasure red | `treasure` | maroon, gold accent |
  | Wario yellow (light) | `yellow` | soft butter yellow, purple accent |

- **Tabs:** All · Display · HDR · Motion · Audio · Cheats · System. LB / RB
  (or a click) switch tabs, wrapping round; the highlight slides to the new
  tab and the selection lands on its first setting. The menu always opens on
  All (every section on one page) with the selection on Resume. Resume and
  Quit show on every tab.
- **Navigation:** D-pad or left stick moves, A selects. The tab strip is not
  in the D-pad order. The mouse works too: move, left/right click and wheel
  are forwarded from the Win32 game window (DolphinNoGUI/PlatformWin32.cpp)
  to ImGui.
- **Input blocking:** while the menu is open (including its close
  animation), `Pad::GetStatus` returns a neutral pad, so the game does not
  see menu input.
- **Quit:** needs a second press within 3 s.
- **Settings:** all apply live, are saved to
  `<user>/Config/WarioWorld.ini`, and are applied on the first frame of the
  next session. Keys the menu does not know (for example ones the starter
  adds) are kept when it rewrites the file.

| Setting | How it applies |
|---|---|
| Resolution (Auto / 1x / 2x-8x) | Config `GFX_EFB_SCALE` (0 = follow window) |
| Aspect (Auto / Original 4:3 / 16:9 / 16:10 / 21:9 / 32:9) | `g_wario_aspect_target` -> runtime `UpdateWarioAspect` (Original restores the game's exact 4:3 values once), host aspect mode Stretch / ForceStandard / Custom |
| Fullscreen | posts F11 to the game window |
| HD textures | Config `GFX_HIRES_TEXTURES` |
| HDR output | Config `GFX_ENHANCE_HDR_OUTPUT` (Vulkan only) |
| HDR paper white (80-500 nits, default 203) | Config `GFX_CC_HDR_PAPER_WHITE_NITS` |
| HDR highlight boost (Off-100 %), peak brightness (400-4000 nits, default 1000), saturation, warmth, contrast, gamma, black level | `WarioHDR` post-process shader (below) |
| Frame rate 60 / 120 / 180 / 240 / Auto | `g_wario_fps_multiplier` (Auto = monitor refresh / 59.94, max 4), switched at the next XFB copy |
| Volume | Config `MAIN_AUDIO_VOLUME` + `AudioCommon::UpdateSoundStream` |
| Moon jump + rise speed | while A / X is held: player actor `[0x801C5820]` y (+0x18) rises |
| UI style, menu size | menu only |
| Graphics (OpenGL / Vulkan) | saved as `backend=opengl` / `vulkan` for the starter; applies after a restart |
| Quit game | posts WM_CLOSE |

## HDR tuning

- The HDR section holds the HDR output switch. Its tuning shows on All only
  while HDR output is on; the HDR tab always lists it, disabled with a hint
  when HDR is off or the backend is not Vulkan. "Reset HDR to defaults"
  restores every tuning value (not the switch).
- Every default is the untouched picture. The grading shader is set as the
  post-process shader only while HDR output is on and a grading value differs
  from its default; otherwise the session's own post shader (normally none)
  is restored, so the default picture never goes through an extra pass.
- `WarioHDR.glsl` is written by the tool fix to
  `vendor/dolphin/Data/Sys/Shaders/`, which the build copies to `Sys/` next to
  the runner. It works in linear light with 1 = paper white. In order:
  black level, gamma, contrast around middle grey, warmth (keeping
  luminance), saturation, then highlight boost (Dolphin's AutoHDR curve:
  shoulder from black, power 2.5, stretching towards the peak brightness).
  On SDR output it passes the picture through unchanged.
- The menu pushes the option values each frame from `Presenter::Present`
  (`ApplyHdrGrading`), so sliders apply live and survive shader reloads.
- Verified 2026-10-27 in hidden runs: the menu loads the shader on Vulkan and
  the values reach it (checked with a test copy that skips the HDR-only
  guard on an SDR snapshot); on OpenGL the controls are disabled. Real HDR
  output (scRGB swapchain on an HDR display) cannot be checked headless and
  is still unverified.

## System tab

The Tk launcher window is gone; the starter (`launcher/wario_launcher.pyw`,
no window) launches the runner and passes paths in environment variables.

- **Graphics backend:** OpenGL / Vulkan, saved as `backend=` in
  WarioWorld.ini and read by the starter at the next launch. When the choice
  differs from the running backend the menu shows "Applies after restart"
  and **Restart now**: it writes the empty marker
  `<user>/Config/WarioWorld.restart`, saves the settings and quits like Quit
  game; the starter deletes the marker and relaunches. With HDR on and
  OpenGL chosen it notes that HDR needs Vulkan.
- **Extract all textures** (shown when `MODERNGEKKO_WARIO_EXTRACT_CMD` is
  set): runs that command line with `CreateProcessW`, `CREATE_NO_WINDOW`,
  below-normal priority. The menu polls it every frame (never blocks) and
  shows running / "Textures extracted." / "Extraction failed (code N)."
  (N = exit code, or the Windows error if it could not start).
- **Open extracted textures** (`MODERNGEKKO_WARIO_EXTRACTED_DIR`), **Open
  HD texture folder** (`<user>/Load/Textures/GWWE01`) and **Open last log**
  (`MODERNGEKKO_WARIO_LOG`): `ShellExecuteW` "open"; folders are created
  first. A missing variable hides its button. Windows decides whether
  Explorer comes in front of the game.
- **Controls:** a collapsible key / action list for the Xbox controller and
  the keyboard, plus "Yes / No menus use the stick, not the D-pad".
- Test hooks: `MODERNGEKKO_WARIO_MENU_TEST_EXTRACT=1` starts the extract
  command when the test opens the menu; `MODERNGEKKO_WARIO_MENU_TEST_RESTART=1`
  presses Restart now after the snapshot.
- Verified 2026-10-27 in hidden runs (OpenGL, env set by hand): the backend
  mismatch note and Restart now (marker written, `backend=vulkan` saved,
  runner exits early); extraction success, failure (exit code 3) and running
  states, with no window. Opening folders / the log was not run, since it
  would open visible Explorer windows.

- **Threading:** config changes are queued while the ImGui lock is held and
  run from `Presenter::Present` right after `OnScreenUI::Finalize`.
- **Environment variables:** `MODERNGEKKO_WARIO_ASPECT` and
  `MODERNGEKKO_WARIO_FPS` still set the starting values for hidden tests,
  which never draw the menu.
