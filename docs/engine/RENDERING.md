# Rendering

Host renderer: ModernGekko's Dolphin-derived video backend (OpenGL used in tests). Runtime shortcuts that remain unvalidated are listed in ../ACCURACY_REVIEW.md (EFB access, EFB/XFB copies, texture cache sampling, ForceProgressive). Framebuffer toggle 0x80041B30 and draw-done callback 0x80042280 (FUNCTION_DATABASE F-0005/F-0006).
