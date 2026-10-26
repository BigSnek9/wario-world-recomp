"""Optional, off-by-default enhancements for the playtest launcher.

Accuracy baseline = native 1x, 4:3 (ForceStandard), no guest changes. These
helpers only run when the human turns an option on.

Resolution: config.ini [Video] resolution picks the runtime's integer EFB
scale (labels from ModernGekko tools/frontend_config.cpp SupportedResolutions).

Widescreen / any aspect (docs/engine/WIDESCREEN.md, CAMERA.md):
- Guest: the camera aspect default HC-0001 (.sdata2 0x801FE5B0, 4/3) is copied
  into every camera block (+0x44) at camera init (fn_80068250); the per-frame
  camera update fn_80042714 rebuilds the projection AND the frustum side planes
  from it, so wider aspect widens rendering and culling together (Hor+: the
  45 degree vertical FOV is kept). The 2D layer half-width HC-0007
  (0x801FE6CC, 320) is scaled by the same factor so 2D art keeps its shape;
  HUD stays in the centred 4:3 area (HUD-edge immediates WS-003 are compiled
  code and are not touched).
- Host: GFX AspectRatio=Custom (relative), CustomAspectRatioWidth/Height =
  target, which scales the game's own ~4:3 VI picture by target/(4/3).
- The values are written once into guest RAM after boot through the runner's
  automation folder (command=write_memory). Cameras created before that write
  (only the earliest boot screens) stay 4:3 until the next scene.
"""
import math
import struct
from pathlib import Path

RESOLUTIONS = [  # (label in launcher, config.ini resolution, scale)
    ("Native 1x (accurate, default)", "640x528", 1),
    ("2x (~720p)", "1280x720", 2),
    ("3x (~1080p)", "1920x1080", 3),
    ("4x (~1440p)", "2560x1440", 4),
    ("6x (~4K)", "3840x2160", 6),
    ("8x (~5K)", "5120x2880", 8),
]

ASPECTS = [  # (label, (w, h) or None for screen)
    ("Match my screen", None),
    ("16:9", (16, 9)),
    ("16:10", (16, 10)),
    ("21:9", (64, 27)),
    ("32:9", (32, 9)),
]

CAMERA_ASPECT_DEFAULT = 0x801FE5B0  # HC-0001, f32 4/3
HALF_WIDTH_2D = 0x801FE6CC         # HC-0007, f32 320


def reduce_ratio(width, height):
    divisor = math.gcd(int(width), int(height))
    return int(width) // divisor, int(height) // divisor


def widescreen_writes(width, height):
    """[(address, bytes)] for a target aspect width:height."""
    aspect = width / height
    return [(CAMERA_ASPECT_DEFAULT, struct.pack(">f", aspect)),
            (HALF_WIDTH_2D, struct.pack(">f", 320.0 * aspect / (4.0 / 3.0)))]


def write_memory_command(address, data):
    return f"command=write_memory\naddress=0x{address:08X}\ndata={data.hex()}\n"


def apply_host_aspect(set_ini, user_dir, ratio):
    """ratio None -> accurate 4:3 baseline; else Custom aspect w:h."""
    gfx = Path(user_dir) / "Config/GFX.ini"
    if ratio is None:
        set_ini(gfx, {"Settings": {"AspectRatio": "2", "wideScreenHack": "False"}})
    else:
        width, height = reduce_ratio(*ratio)
        set_ini(gfx, {"Settings": {"AspectRatio": "4", "CustomAspectRatioWidth": str(width),
                                   "CustomAspectRatioHeight": str(height), "wideScreenHack": "False",
                                   "Crop": "False"}})
