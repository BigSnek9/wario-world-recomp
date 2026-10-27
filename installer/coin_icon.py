"""Game icon from the player's own disc: Wario World's gold "W" coin texture, pure Python.

The coin is a 32x32 CMPR texture (Dolphin HD name tex1_32x32_m_5b7df270a43b0ca3_14, the base
level only) in files/rsc/ATT.RSC at 0x1148A0 (512 bytes; the same bytes are also in AOP.RSC at
0x19E660). The disc is pinned by its hash, so the location is fixed; the bytes are still checked
against COIN_SHA256 before use. The texture is decoded (Dolphin's CMPR rules, as
scripts/extract_textures.py), cut to the round coin with an anti-aliased edge and a transparent
outside, and resampled to every icon size: Catmull-Rom (bicubic) when enlarging, an area average
of bicubic samples when shrinking. The .ico holds uncompressed 32-bit BMP entries.

The native launcher (release/launcher/coin_icon.h) implements the same steps with the same
arithmetic, so both produce byte-identical icons (release/test_release.py checks this).
The result is derived from the player's disc: it is only ever written to the player's own install
folder and must never be committed or distributed.
"""
from __future__ import annotations

import hashlib
import math
import struct
from pathlib import Path

COIN_ARCHIVES = (("files/rsc/ATT.RSC", 0x1148A0), ("files/rsc/AOP.RSC", 0x19E660))
COIN_SIZE = 512  # 32x32 CMPR base level: 4x4 blocks of 8x8 pixels, 32 bytes each
COIN_SHA256 = "7416b9493e5d3349b4741d1ec510312d344761247d517b24ad10e956440201a1"
TEXELS = 32
# The coin fills the texture; its rim touches the edges. A slightly smaller cut keeps the
# texture's orange corner background out of the anti-aliased edge.
RADIUS = 15.6
ICON_SIZES = (256, 128, 64, 48, 32, 24, 16)


def read_coin(game_dir):
    """The coin's 512 texture bytes from an extracted disc, or raise ValueError."""
    game_dir = Path(game_dir)
    for relative, offset in COIN_ARCHIVES:
        path = game_dir / relative
        try:
            with path.open("rb") as stream:
                stream.seek(offset)
                data = stream.read(COIN_SIZE)
        except OSError:
            continue
        if len(data) == COIN_SIZE and hashlib.sha256(data).hexdigest() == COIN_SHA256:
            return data
    raise ValueError("the coin texture was not found in the game files")


def _c5(v):
    return (v << 3) | (v >> 2)


def _c6(v):
    return (v << 2) | (v >> 4)


def decode_cmpr(data, width=TEXELS, height=TEXELS):
    """RGBA rows (lists of [r, g, b, a]) of a CMPR texture, Dolphin's generic decoder rules."""
    pixels = [[[0, 0, 0, 0] for _ in range(width)] for _ in range(height)]
    offset = 0
    for block_y in range(0, height, 8):
        for block_x in range(0, width, 8):
            for sub in range(4):
                c1, c2 = struct.unpack_from(">HH", data, offset)
                bits = struct.unpack_from(">I", data, offset + 4)[0]
                offset += 8
                col1 = (_c5(c1 >> 11 & 31), _c6(c1 >> 5 & 63), _c5(c1 & 31))
                col2 = (_c5(c2 >> 11 & 31), _c6(c2 >> 5 & 63), _c5(c2 & 31))
                if c1 > c2:
                    col3 = tuple((b * 3 + a * 5) >> 3 for a, b in zip(col1, col2))
                    col4 = tuple((a * 3 + b * 5) >> 3 for a, b in zip(col1, col2))
                    palette = (col1 + (255,), col2 + (255,), col3 + (255,), col4 + (255,))
                else:
                    mid = tuple((a + b) // 2 for a, b in zip(col1, col2))
                    palette = (col1 + (255,), col2 + (255,), mid + (255,), mid + (0,))
                sx, sy = block_x + (sub & 1) * 4, block_y + (sub >> 1) * 4
                for y in range(4):
                    for x in range(4):
                        index = bits >> (30 - 2 * (y * 4 + x)) & 3
                        if sy + y < height and sx + x < width:
                            pixels[sy + y][sx + x] = list(palette[index])
    return pixels


def _cubic(t):
    """Catmull-Rom weights for the four texels around a sample at fraction t."""
    t2, t3 = t * t, t * t * t
    return (-0.5 * t3 + t2 - 0.5 * t,
            1.5 * t3 - 2.5 * t2 + 1.0,
            -1.5 * t3 + 2.0 * t2 + 0.5 * t,
            0.5 * t3 - 0.5 * t2)


def _sample(texels, u, v):
    """Bicubic RGB at texel-space position (u, v) (texel centres at i + 0.5), edges clamped."""
    x, y = u - 0.5, v - 0.5
    x0, y0 = math.floor(x), math.floor(y)
    wx, wy = _cubic(x - x0), _cubic(y - y0)
    last = TEXELS - 1
    r = g = b = 0.0
    for j in range(4):
        row = texels[min(last, max(0, y0 - 1 + j))]
        for i in range(4):
            w = wx[i] * wy[j]
            p = row[min(last, max(0, x0 - 1 + i))]
            r += p[0] * w
            g += p[1] * w
            b += p[2] * w
    return r, g, b


def _byte(value):
    return 0 if value <= 0.0 else 255 if value >= 255.0 else int(value + 0.5)


def render(texels, size):
    """The round coin on a transparent size x size square: rows of (r, g, b, a)."""
    scale = TEXELS / size  # texels per output pixel
    samples = max(2, math.ceil(2.0 * scale))  # per axis; area average when shrinking
    centre = TEXELS / 2.0
    image = []
    for oy in range(size):
        row = []
        for ox in range(size):
            # Coverage of the circle at this pixel (anti-aliased edge, one output pixel wide).
            dx, dy = (ox + 0.5) * scale - centre, (oy + 0.5) * scale - centre
            distance = math.sqrt(dx * dx + dy * dy) / scale
            coverage = RADIUS / scale - distance + 0.5
            if coverage <= 0.0:
                row.append((0, 0, 0, 0))
                continue
            r = g = b = 0.0
            for sy in range(samples):
                v = (oy + (sy + 0.5) / samples) * scale
                for sx in range(samples):
                    sr, sg, sb = _sample(texels, (ox + (sx + 0.5) / samples) * scale, v)
                    r += sr
                    g += sg
                    b += sb
            n = samples * samples
            row.append((_byte(r / n), _byte(g / n), _byte(b / n), _byte(min(1.0, coverage) * 255.0)))
        image.append(row)
    return image


def ico_bytes(images):
    """A .ico of square RGBA images with uncompressed 32-bit BMP entries (plus the AND mask)."""
    blobs = []
    for image in images:
        size = len(image)
        mask_stride = ((size + 31) // 32) * 4
        pixels = bytearray()
        mask = bytearray()
        for row in reversed(image):  # bottom-up
            bits = bytearray(mask_stride)
            for x, (r, g, b, a) in enumerate(row):
                pixels += bytes((b, g, r, a))
                if a == 0:
                    bits[x >> 3] |= 0x80 >> (x & 7)
            mask += bits
        header = struct.pack("<IiiHHIIiiII", 40, size, size * 2, 1, 32, 0, len(pixels) + len(mask), 0, 0, 0, 0)
        blobs.append((size, header + bytes(pixels) + bytes(mask)))
    out = struct.pack("<HHH", 0, 1, len(blobs))
    offset = 6 + 16 * len(blobs)
    entries, data = b"", b""
    for size, blob in blobs:
        entries += struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(blob), offset + len(data))
        data += blob
    return out + entries + data


def icon_images(texture_bytes, sizes=ICON_SIZES):
    texels = decode_cmpr(texture_bytes)
    return [render(texels, size) for size in sizes]


def write_icon(game_dir, icon_path):
    """Write the coin .ico made from the extracted disc in game_dir; returns its path."""
    images = icon_images(read_coin(game_dir))
    icon_path = Path(icon_path)
    icon_path.parent.mkdir(parents=True, exist_ok=True)
    temp = icon_path.with_suffix(".ico.tmp")
    temp.write_bytes(ico_bytes(images))
    temp.replace(icon_path)
    return icon_path


def png_bytes(image):
    """An 8-bit RGBA PNG of rows of (r, g, b, a) (previews only)."""
    import zlib
    height, width = len(image), len(image[0])
    raw = b"".join(b"\0" + bytes(c for p in row for c in p) for row in image)

    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def preview_strip(images, background=(0, 0, 0, 0)):
    """All sizes side by side (8 px gaps) on one strip, for checking by eye."""
    height = max(len(image) for image in images)
    width = sum(len(image) for image in images) + 8 * (len(images) - 1)
    strip = [[background] * width for _ in range(height)]
    x = 0
    for image in images:
        top = height - len(image)
        for y, row in enumerate(image):
            strip[top + y][x:x + len(row)] = row
        x += len(image) + 8
    return strip


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--game", type=Path, required=True, help="extracted disc folder (GWWE01)")
    parser.add_argument("--out", type=Path, required=True, help="the .ico to write")
    parser.add_argument("--preview", type=Path, help="also write a PNG with every size")
    args = parser.parse_args()
    print(write_icon(args.game, args.out))
    if args.preview:
        args.preview.write_bytes(png_bytes(preview_strip(icon_images(read_coin(args.game)))))
