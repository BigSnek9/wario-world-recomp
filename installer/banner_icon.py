"""Game icon from the user's own disc banner (files/opening.bnr), pure Python.

The banner holds a 96x32 RGB5A3 image in GameCube 4x4 tiles at offset 0x20. It is decoded,
placed on a square transparent canvas and written as a multi-size PNG-compressed .ico.
The result is derived from the user's disc: it is generated only inside the install folder
and must never be committed or distributed.
"""
from __future__ import annotations

import struct
import zlib
from pathlib import Path

WIDTH, HEIGHT = 96, 32
IMAGE_OFFSET = 0x20
ICON_SIZES = (256, 128, 64, 48, 32, 16)
# The banner is pinned by the disc hash (GWWE01 rev 0): stone background, castle and the
# "WARIOWORLD" logo. Large icons show the whole banner (rounded corners) centred on a transparent
# square; at 48 px and below a 96-wide strip is unreadable, so those show the logo's "W".
SMALL_ICON_MAX = 48
W_CROP = (1, 9, 23, 23)  # left, top, width, height in banner pixels


def find_banner(game_dir):
    """opening.bnr of an extracted disc (dolrecomp puts it in files/)."""
    game_dir = Path(game_dir)
    for candidate in (game_dir / "files/opening.bnr", game_dir / "opening.bnr", game_dir / "root/opening.bnr"):
        if candidate.is_file():
            return candidate
    found = sorted(game_dir.rglob("opening.bnr"))
    return found[0] if found else None


def rgb5a3(value):
    if value & 0x8000:  # opaque RGB555
        r, g, b = (value >> 10) & 0x1F, (value >> 5) & 0x1F, value & 0x1F
        return (r << 3 | r >> 2, g << 3 | g >> 2, b << 3 | b >> 2, 255)
    a, r, g, b = (value >> 12) & 0x7, (value >> 8) & 0xF, (value >> 4) & 0xF, value & 0xF
    return (r * 17, g * 17, b * 17, a << 5 | a << 2 | a >> 1)


def decode_banner(data):
    """96x32 RGBA rows (list of lists of (r, g, b, a)) from opening.bnr bytes."""
    if data[:3] != b"BNR" or len(data) < IMAGE_OFFSET + WIDTH * HEIGHT * 2:
        raise ValueError("not a GameCube opening.bnr")
    pixels = [[(0, 0, 0, 0)] * WIDTH for _ in range(HEIGHT)]
    offset = IMAGE_OFFSET
    for tile_y in range(0, HEIGHT, 4):
        for tile_x in range(0, WIDTH, 4):
            for y in range(4):
                for x in range(4):
                    pixels[tile_y + y][tile_x + x] = rgb5a3(struct.unpack_from(">H", data, offset)[0])
                    offset += 2
    return pixels


def opaque_bounds(pixels, threshold=16):
    rows = [y for y, row in enumerate(pixels) if any(p[3] > threshold for p in row)]
    cols = [x for x in range(len(pixels[0])) if any(row[x][3] > threshold for row in pixels)]
    if not rows or not cols:
        return 0, 0, len(pixels[0]), len(pixels)
    return cols[0], rows[0], cols[-1] + 1, rows[-1] + 1


def square_icon(pixels, size, box=None, rounded=True):
    """The banner (or the box (left, top, width, height) of it; default its visible part) scaled
    to fit a size x size transparent square, centred, optionally with rounded corners.
    Box filter when shrinking, nearest neighbour when enlarging."""
    if box:
        left, top, right, bottom = box[0], box[1], box[0] + box[2], box[1] + box[3]
    else:
        left, top, right, bottom = opaque_bounds(pixels)
    width, height = right - left, bottom - top
    scale = size / max(width, height)
    out_w, out_h = max(1, round(width * scale)), max(1, round(height * scale))
    x0, y0 = (size - out_w) // 2, (size - out_h) // 2
    canvas = [[(0, 0, 0, 0)] * size for _ in range(size)]
    for oy in range(out_h):
        sy0, sy1 = top + oy / scale, top + (oy + 1) / scale
        for ox in range(out_w):
            sx0, sx1 = left + ox / scale, left + (ox + 1) / scale
            if scale >= 1:
                canvas[y0 + oy][x0 + ox] = pixels[min(bottom - 1, int(sy0))][min(right - 1, int(sx0))]
                continue
            # Box filter with alpha-weighted colour (no dark fringes at transparent edges).
            total = r = g = b = a = 0.0
            for sy in range(int(sy0), min(bottom, int(-(-sy1 // 1)))):
                wy = min(sy + 1, sy1) - max(sy, sy0)
                for sx in range(int(sx0), min(right, int(-(-sx1 // 1)))):
                    w = wy * (min(sx + 1, sx1) - max(sx, sx0))
                    if w <= 0:
                        continue
                    pr, pg, pb, pa = pixels[sy][sx]
                    total += w
                    a += pa * w
                    r += pr * pa * w
                    g += pg * pa * w
                    b += pb * pa * w
            if total and a:
                canvas[y0 + oy][x0 + ox] = (round(r / a), round(g / a), round(b / a), round(a / total))
    if rounded:
        round_corners(canvas, x0, y0, out_w, out_h, max(1.0, 0.14 * min(out_w, out_h)))
    return canvas


def round_corners(canvas, x0, y0, width, height, radius):
    """Fade the rectangle's corners to transparent (anti-aliased quarter circles)."""
    for y in range(height):
        for x in range(width):
            dx = max(radius - (x + 0.5), (x + 0.5) - (width - radius), 0.0)
            dy = max(radius - (y + 0.5), (y + 0.5) - (height - radius), 0.0)
            if not dx or not dy:
                continue
            coverage = max(0.0, min(1.0, radius + 0.5 - (dx * dx + dy * dy) ** 0.5))
            r, g, b, a = canvas[y0 + y][x0 + x]
            canvas[y0 + y][x0 + x] = (r, g, b, round(a * coverage))


def icon_images(pixels):
    return [square_icon(pixels, size, W_CROP if size <= SMALL_ICON_MAX else None) for size in ICON_SIZES]


def png_bytes(pixels):
    height, width = len(pixels), len(pixels[0])
    raw = b"".join(b"\0" + bytes(c for p in row for c in p) for row in pixels)

    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def ico_bytes(images):
    """images: list of square RGBA pixel grids; PNG-compressed entries (Windows Vista and later)."""
    pngs = [(len(img), png_bytes(img)) for img in images]
    header = struct.pack("<HHH", 0, 1, len(pngs))
    offset = 6 + 16 * len(pngs)
    entries, blobs = b"", b""
    for size, blob in pngs:
        entries += struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(blob), offset + len(blobs))
        blobs += blob
    return header + entries + blobs


def write_icon(banner_path, icon_path, preview_png=None):
    pixels = decode_banner(Path(banner_path).read_bytes())
    images = icon_images(pixels)
    icon_path = Path(icon_path)
    icon_path.parent.mkdir(parents=True, exist_ok=True)
    temp = icon_path.with_suffix(".ico.tmp")
    temp.write_bytes(ico_bytes(images))
    temp.replace(icon_path)
    if preview_png:  # all sizes side by side on a transparent strip
        height = ICON_SIZES[0]
        strip = [[(0, 0, 0, 0)] * (sum(ICON_SIZES) + 8 * len(ICON_SIZES)) for _ in range(height)]
        x = 0
        for image in images:
            for y, row in enumerate(image):
                strip[y][x:x + len(row)] = row
            x += len(image) + 8
        Path(preview_png).write_bytes(png_bytes(strip))
    return icon_path
