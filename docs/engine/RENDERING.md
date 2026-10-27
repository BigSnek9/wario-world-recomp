# Rendering

Host renderer: ModernGekko's Dolphin-derived video backend, OpenGL or Vulkan
(menu choice, applies after a restart). Hidden tests mostly use OpenGL; Vulkan
is covered by release-runner and HDR runs (../progress/TEST_RESULTS.md). HDR
output and its grading shader are Vulkan only (../modding/IN_GAME_MENU.md).

Runtime shortcuts that remain unvalidated against hardware are listed in
../ACCURACY_REVIEW.md (EFB access, EFB/XFB copies, texture cache sampling,
ForceProgressive). Framebuffer toggle 0x80041B30 and draw-done callback
0x80042280 (FUNCTION_DATABASE F-0005/F-0006). The 3D render target is 512x448
(WIDESCREEN.md WS-004).

Enhancement layers on top of the renderer: ../modding/GRAPHICS_ENHANCEMENTS.md
(resolution, HD textures, HDR) and ../modding/FPS_UNLOCK.md (frame generation
by GPU command replay).
