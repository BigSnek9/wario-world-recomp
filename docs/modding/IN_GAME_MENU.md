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

- **Tabs:** All · Display · HDR · Motion · Audio · Controls · Cheats · System. LB / RB
  (or a click) switch tabs, wrapping round; the highlight slides to the new
  tab and the selection lands on its first setting (focus only: the item is
  not activated, so a slider does not open its text entry). The menu always opens on
  All (every section on one page) with the selection on Resume. Resume and
  Quit show on every tab.
- **Navigation:** D-pad or left stick moves, A selects. The tab strip is not
  in the D-pad order. Tab labels keep a fixed padding and shrink before the
  LB / RB chips are dropped. Menu size (0.1), rise speed (0.1) and HDR gamma
  (0.01) are whole-step sliders, so one press is one step (ImGui moves float
  sliders 1 % of the range per press, rounded to the shown precision, so
  single presses looked dead); menu size applies live with the pad and on
  release with the mouse. The mouse works too: move, left/right click and wheel
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
| Aspect (Auto / Original 4:3 / 16:9 / 16:10 / 21:9 / 32:9) | `g_wario_aspect_target` -> runtime `UpdateWarioAspect` (Original restores the game's exact 4:3 values once), host aspect mode Stretch / ForceStandard / CustomStretch (absolute width:height; the relative Custom mode kept the VI analog-width correction and left thin side bars at 16:9 on a 16:9 screen) |
| Fullscreen | absolute: the tick mirrors the real window (no `WS_CAPTION` = fullscreen, as `PlatformWin32::ToggleFullscreen` leaves it, so F11 / Alt+Enter show up too) and F11 is posted only when the request differs. It used to post F11 as a blind toggle, which inverted the tick when the starter had already launched fullscreen. Verified hidden 2026-10-27 (`MODERNGEKKO_WARIO_MENU_TEST_FULLSCREEN`): windowed, on, on again (no change), off |
| HD textures | Config `GFX_HIRES_TEXTURES` |
| HDR output | Config `GFX_ENHANCE_HDR_OUTPUT` (Vulkan only) |
| HDR paper white (80-500 nits, default 203) | Config `GFX_CC_HDR_PAPER_WHITE_NITS` |
| HDR menu brightness (80-400 nits, default 80; shown only while HDR is on) | `g_wario_menu_nits`: the ImGui pixel shader's linear output is scaled by nits / 80 (Dolphin draws ImGui in scRGB, 1.0 = 80 nits); `DrawImGui` rebuilds the ImGui pipeline when it changes; saved as `hdr_menu_nits` |
| HDR highlight boost (Off-100 %), peak brightness (400-4000 nits, default 1000), white level (Off or 400-4000 nits), saturation, vibrance (-100..+100 %), contrast, gamma, black level | `WarioHDR` post-process shader (below) |
| VSync Auto (on with frame gen) / Off | `VideoCommon::g_wario_vsync_mode` (VideoCommon/Present.cpp, from tool_fix_wario_fps.py), live; saved as `vsync=auto` / `off` |
| Frame rate 60 / 120 / 180 / 240 / Auto | `g_wario_fps_multiplier` (Auto = monitor refresh / 59.94, max 4), switched at the next XFB copy |
| Master volume | Config `MAIN_AUDIO_VOLUME` + `AudioCommon::UpdateSoundStream` (saved as `volume`) |
| Music, Sound effects (0-100 %, default 100), Mute pause menu music | game module exports `wario_audio_music`, `wario_audio_sfx`, `wario_audio_mute_pause_music` (s32, see docs/engine/AUDIO.md), found with GetProcAddress on `gGWWE01_recomp.dll` and written every frame; saved as `music`, `sfx`, `mute_pause_music`. A module without the exports leaves the controls disabled with a hint. The pause music follows the Music slider and mute applies at once, even with the book open (module fix def8821). Export lookups retry each frame until the module is loaded. No Voice slider: Wario's voice clips are ordinary SFX whose ids are not identified yet |
| Jump height (100-500 %, 10 % per press; default 100 = original) | `wario_cheat_jump_percent`: the game's own jump launch speed is scaled (200 % = 2x peak). Replaces the old "Moon jump" levitation (it pushed Wario's y up every frame while A was held, frame-rate dependent); its `moon_jump` / `moon_speed` keys are dropped on the next save |
| Walk through walls, Super punches | `wario_cheat_noclip`, `wario_cheat_super_punch` (0 / 1) |
| Unlock all stages, Mark all collectables as grabbed (one-shot buttons, not saved) | `wario_cheat_unlock_stages`, `wario_cheat_collect_all`: the menu writes 1, the module applies it at the next player update (a save loaded, Wario in the world) and sets 2; the menu shows "Waiting" / "Applied". The final boss stays uncleared |
| UI style, menu size | menu only |
| Graphics (OpenGL / Vulkan) | saved as `backend=opengl` / `vulkan` for the starter; applies after a restart |
| Performance mode (multithreaded) | saved as `performance=0` / `1`; the starter writes Dolphin.ini [Core] CPUThread at launch (dual core: GPU emulation on its own thread); applies after a restart |
| Quit game | posts WM_CLOSE |

## HDR tuning

- The HDR section holds the HDR output switch. Its tuning shows on All only
  while HDR output is on; the HDR tab always lists it, disabled with a hint
  when HDR is off or the backend is not Vulkan. "Reset HDR to defaults"
  restores every tuning value, menu brightness included (not the switch).
- Every default is the untouched picture. The grading shader is set as the
  post-process shader only while HDR output is on and a grading value differs
  from its default; otherwise the session's own post shader (normally none)
  is restored, so the default picture never goes through an extra pass.
- `WarioHDR.glsl` is written by the tool fix to
  `vendor/dolphin/Data/Sys/Shaders/`, which the build copies to `Sys/` next to
  the runner. It works in linear light with 1 = paper white. In order:
  black level, gamma, contrast around middle grey, saturation, vibrance
  (saturation scaled by 1 - chroma, skin hues with red > green > blue
  partly protected), highlight boost (Dolphin's AutoHDR curve: shoulder from
  black, power 2.5, stretching towards the peak brightness), then white level
  (a luminance ceiling: above 75 % of it highlights roll off exponentially,
  slope 1 at the knee, never exceeding it). On SDR output it passes the
  picture through unchanged.
- 2026-10-27 user feedback: Warmth removed (an old `hdr_warmth` key is dropped
  on the next save); White level and Vibrance added, both off by default.
  Verified hidden on Vulkan: with boost, vibrance and white level set, the real
  shader ran on the HDR swap chain with no compile or load errors and the ini
  saved without `hdr_warmth`. A test copy without the HDR-only guard raised the
  game area's mean saturation from 67 to 101 at vibrance +100.
- Cheats one-shots: the first press arms the button for 3 s ("Press again to
  apply", red); each carries "Permanent once you save the game."
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
- Overlay pipeline format: the ImGui pipeline is built for the colour format
  of the framebuffer `DrawImGui` really draws into, and rebuilt when that
  changes. `Presenter::GetBackbufferFormat()` goes stale when HDR is switched
  on at runtime on Vulkan: the swap chain is recreated as RGBA16F scRGB but
  `VKGfx::OnSwapChainResized` passes only the new size. The overlay then kept
  its SDR pipeline in HDR (gamma values written as linear light) and the menu
  brightness never applied (user report 2026-10-27).
- Verified 2026-10-27 in hidden Vulkan runs with HDR on (this machine gets an
  RGBA16F swap chain even hidden): with `hdr_menu_nits` at 80 and at 200 the
  runner logs `ImGui pipeline rebuilt for RGBA16F (HDR)` (the SDR / HDR pair
  after it is the menu snapshot's RGBA8 texture). The brightness itself was
  not measured on screen.
- Audio controls verified 2026-10-27 hidden with `build/module-audio-test`
  (`--dump-audio`, savestate 093938_AR51): the DSP dump RMS was ~3500 at
  music 100 / sfx 100 and settled to ~140 (DC level) with music 0 / sfx 0,
  so the menu's values reach the module. That scene is mostly SFX, so music
  0 alone changed little.
- Controls tab (2026-10-27): rebinding of A / B / X / Y / Z / Start / L / R / D-pad,
  Rumble on/off + strength, "Reset controls to defaults". GameCube-layout defaults,
  SDL gamepad sync and the full design are in docs/CONTROLS.md. While a binding waits
  for input the menu ignores the pad (no navigation, close or tab switch). Test hook
  `MODERNGEKKO_WARIO_MENU_TEST_PAD=1` presses "Reset controls to defaults" after the
  snapshot and takes a second one.
- Bug report snapshot (2026-10-27): System tab "Save bug report snapshot (F12)" and the
  F12 key (menu open or closed) queue `save_state` and `screenshot` commands for the
  runner's automation folder (`MODERNGEKKO_WARIO_CONTROL_DIR`, falling back to the
  runner's `--automation-dir` argument) as `<16-digit ms>-menu-report-*.txt`, written
  to a temporary file and renamed into `commands/` like launcher/play_tracker.py. The
  files go to `MODERNGEKKO_WARIO_REPORT_DIR/report-<HHMMSS>.sav` / `.png`; without a
  report folder the button and F12 do nothing. A toast ("Snapshot saved: report-...")
  shows for 3 s. Verified hidden (`MODERNGEKKO_WARIO_MENU_TEST_REPORT=1`): both files
  written (25 MB state, game-only screenshot), commands processed with no error.
- The System tab's controls help lists the GameCube-by-position layout.
- Cheats (2026-10-27): module exports in docs/modding/CHEATS.md, looked up with
  GetProcAddress and retried while missing; toggles and jump height are written every
  frame (the module resets them each launch) and saved as `cheat_noclip`,
  `cheat_super_punch`, `cheat_jump_percent`. Without the exports the tab is disabled
  with a hint. Test hook `MODERNGEKKO_WARIO_MENU_TEST_CHEATS=1` requests "Unlock all
  stages" after the snapshot, closes the menu and logs the module's answer.
