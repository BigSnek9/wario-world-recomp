# Graphics enhancements

Status 2026-10-27: done, all optional, all in the in-game menu
(IN_GAME_MENU.md). The accurate baseline stays native 1x, 4:3, SDR.

- **Internal resolution:** Auto (follows the window, Dolphin's
  InternalResolution=0) or 1x-8x, applied live through `GFX_EFB_SCALE`.
- **HD texture packs:** Dolphin's hash-named loader
  (`tex1_{w}x{h}[_m]_{hash}_{fmt}`, ../engine/ASSETS.md), folder
  `<user>/Load/Textures/GWWE01`. Uploads are streamed: at most 32 MB of HD
  texture data per frame (`MODERNGEKKO_HD_UPLOAD_MB`), the original texture
  shows for a frame or two until the HD one is in
  (`scripts/tool_fix_hd_texture_streaming.py`, FPS_UNLOCK.md).
- **Texture extractor:** `scripts/extract_textures.py` reads every texture
  from the disc archives with loader-compatible names (1,701 textures; menu
  System tab "Extract all textures").
- **HDR (Vulkan):** scRGB output plus the `WarioHDR` grading shader (paper
  white, peak, highlight boost, white level, saturation, vibrance, contrast,
  gamma, black level) and menu brightness in nits. The grading pass runs only
  while a value differs from its default. IN_GAME_MENU.md "HDR tuning".

Not verified by a hidden test: real HDR output on an HDR display.
