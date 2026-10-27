# In-game menu

Status 2026-10-27: implemented (scripts/tool_fix_wario_menu.py). Hidden tests
can render it: `MODERNGEKKO_WARIO_MENU_TEST=<png>` opens the menu after 6 s
and saves the game picture with the menu on top once.

- **Open/close:** Back on the controller, or Tab on the keyboard. B also
  closes it (when no dropdown is open), as does Resume.
- **Look:** an ImGui panel (Dolphin's overlay) slides in from the left in
  0.18 s (ease-out). Text is 18 px times the Windows display scaling of the
  game window's monitor times the Menu size setting (0.6-1.6x); the panel is
  26 em wide, at most half the screen.
- **Navigation:** D-pad or left stick moves, A selects. The mouse works too:
  move, left/right click and wheel are forwarded from the Win32 game window
  (DolphinNoGUI/PlatformWin32.cpp) to ImGui.
- **Input blocking:** while the menu is open (including its close
  animation), `Pad::GetStatus` returns a neutral pad, so the game does not
  see menu input.
- **Settings:** all apply live, are saved to
  `<user>/Config/WarioWorld.ini`, and are applied on the first frame of the
  next session.

| Setting | How it applies |
|---|---|
| Resolution (Auto / 1x / 2x-8x) | Config `GFX_EFB_SCALE` (0 = follow window) |
| Aspect (Auto / Original 4:3 / 16:9 / 16:10 / 21:9 / 32:9) | `g_wario_aspect_target` -> runtime `UpdateWarioAspect` (Original restores the game's exact 4:3 values once), host aspect mode Stretch / ForceStandard / Custom |
| Fullscreen | posts F11 to the game window |
| HD textures | Config `GFX_HIRES_TEXTURES` |
| HDR output | Config `GFX_ENHANCE_HDR_OUTPUT` (Vulkan only) |
| Frame rate 60 / 120 / 180 / 240 / Auto | `g_wario_fps_multiplier` (Auto = monitor refresh / 59.94, max 4), switched at the next XFB copy |
| Volume | Config `MAIN_AUDIO_VOLUME` + `AudioCommon::UpdateSoundStream` |
| Moon jump + rise speed | while A / X is held: player actor `[0x801C5820]` y (+0x18) rises |
| Quit game | posts WM_CLOSE |

- **Threading:** config changes are queued while the ImGui lock is held and
  run from `Presenter::Present` right after `OnScreenUI::Finalize`.
- **Launcher:** now only the build, the graphics backend (needs a restart),
  Play and the tools. On first run it migrates its old choices into
  WarioWorld.ini.
- **Environment variables:** `MODERNGEKKO_WARIO_ASPECT` and
  `MODERNGEKKO_WARIO_FPS` still set the starting values for hidden tests,
  which never draw the menu.
