"""Tests for the disc-banner icon (python -m unittest discover -s installer).

The synthetic tests need no game files. The real-banner test reads the local extracted disc
(original/GWWE01, read only) when present and writes nothing outside a temporary folder.
"""
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import banner_icon as bi  # noqa: E402

GAME = Path(__file__).resolve().parents[1] / "original/GWWE01"


def synthetic_banner(value_at):
    """A BNR1 file whose 96x32 image holds value_at(x, y) in GameCube 4x4-tile order."""
    data = bytearray(b"BNR1" + bytes(0x1C))
    for tile_y in range(0, 32, 4):
        for tile_x in range(0, 96, 4):
            for y in range(4):
                for x in range(4):
                    data += struct.pack(">H", value_at(tile_x + x, tile_y + y))
    return bytes(data + bytes(0x140 * 6))


def read_ico(data):
    """[(size, png bytes)] from an .ico."""
    reserved, kind, count = struct.unpack_from("<HHH", data, 0)
    assert (reserved, kind) == (0, 1)
    entries = []
    for index in range(count):
        width, _h, _c, _r, _p, _bpp, length, offset = struct.unpack_from("<BBBBHHII", data, 6 + 16 * index)
        entries.append((width or 256, data[offset:offset + length]))
    return entries


def read_png(blob):
    """(width, height, rows of RGBA tuples) for the 8-bit RGBA, filter-0 PNGs png_bytes writes."""
    assert blob[:8] == b"\x89PNG\r\n\x1a\n"
    width, height = struct.unpack_from(">II", blob, 16)
    pos, idat = 8, b""
    while pos < len(blob):
        length, kind = struct.unpack_from(">I4s", blob, pos)
        if kind == b"IDAT":
            idat += blob[pos + 8:pos + 8 + length]
        pos += 12 + length
    raw = zlib.decompress(idat)
    stride = 1 + width * 4
    rows = []
    for y in range(height):
        line = raw[y * stride + 1:(y + 1) * stride]
        rows.append([tuple(line[i:i + 4]) for i in range(0, len(line), 4)])
    return width, height, rows


class Rgb5a3(unittest.TestCase):
    def test_opaque_rgb555(self):
        self.assertEqual(bi.rgb5a3(0xFFFF), (255, 255, 255, 255))
        self.assertEqual(bi.rgb5a3(0x8000), (0, 0, 0, 255))
        self.assertEqual(bi.rgb5a3(0x8000 | 0x1F << 10), (255, 0, 0, 255))
        self.assertEqual(bi.rgb5a3(0x8000 | 0x10 << 5), (0, 132, 0, 255))

    def test_translucent_argb3444(self):
        self.assertEqual(bi.rgb5a3(0x0000), (0, 0, 0, 0))
        self.assertEqual(bi.rgb5a3(0x7FFF), (255, 255, 255, 255))
        self.assertEqual(bi.rgb5a3(0x40F0), (0, 255, 0, 146))


class Decode(unittest.TestCase):
    def test_tile_order(self):
        # Encode each pixel's coordinates in an opaque colour: red = x / 4, green = y.
        data = synthetic_banner(lambda x, y: 0x8000 | (x // 4) << 10 | y << 5 | (x % 4))
        pixels = bi.decode_banner(data)
        self.assertEqual((len(pixels[0]), len(pixels)), (96, 32))
        for y in range(32):
            for x in range(96):
                self.assertEqual(pixels[y][x], bi.rgb5a3(0x8000 | (x // 4) << 10 | y << 5 | (x % 4)))

    def test_rejects_other_files(self):
        with self.assertRaises(ValueError):
            bi.decode_banner(b"\0" * 0x2000)
        with self.assertRaises(ValueError):
            bi.decode_banner(b"BNR1" + b"\0" * 0x100)


class Icon(unittest.TestCase):
    def check_icon(self, banner):
        with tempfile.TemporaryDirectory() as folder:
            icon = bi.write_icon(banner, Path(folder) / "game.ico", Path(folder) / "preview.png")
            entries = read_ico(icon.read_bytes())
            self.assertEqual(sorted(size for size, _ in entries), sorted(bi.ICON_SIZES))
            for size, blob in entries:
                width, height, rows = read_png(blob)
                self.assertEqual((width, height), (size, size))
                self.assertLess(rows[0][0][3], 128, "corners are transparent or rounded off")
                self.assertTrue(any(p[3] == 255 for p in rows[size // 2]), "the middle row shows the banner")
            self.assertTrue((Path(folder) / "preview.png").read_bytes().startswith(b"\x89PNG"))

    def test_synthetic_banner(self):
        with tempfile.TemporaryDirectory() as folder:
            banner = Path(folder) / "files/opening.bnr"
            banner.parent.mkdir()
            banner.write_bytes(synthetic_banner(lambda x, y: 0x8000 | x % 32 << 10 | y << 5))
            self.assertEqual(bi.find_banner(folder), banner)
            self.check_icon(banner)

    @unittest.skipUnless((GAME / "files/opening.bnr").is_file(), "no local extracted GWWE01")
    def test_real_banner(self):
        banner = bi.find_banner(GAME)
        pixels = bi.decode_banner(banner.read_bytes())
        self.assertEqual((len(pixels[0]), len(pixels)), (96, 32))
        self.assertTrue(all(p[3] > 0 for row in pixels for p in row), "the GWWE01 banner is fully opaque")
        colours = {p[:3] for row in pixels for p in row}
        self.assertGreater(len(colours), 200, "a real picture, not a flat fill")
        self.check_icon(banner)


if __name__ == "__main__":
    unittest.main()
