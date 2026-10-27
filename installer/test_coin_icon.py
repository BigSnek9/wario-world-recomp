"""Tests for the coin icon (python -m unittest discover -s installer -p "test_*.py").

The synthetic tests need no game files. The real-coin test reads the local extracted disc
(original/GWWE01, read only) when present and writes nothing outside a temporary folder.
"""
import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import coin_icon as ci  # noqa: E402

GAME = Path(__file__).resolve().parents[1] / "original/GWWE01"


def read_ico(data):
    """[(size, bmp bytes)] from an .ico."""
    reserved, kind, count = struct.unpack_from("<HHH", data, 0)
    assert (reserved, kind) == (0, 1)
    entries = []
    for index in range(count):
        width, height, _c, _r, planes, bpp, length, offset = struct.unpack_from("<BBBBHHII", data, 6 + 16 * index)
        assert width == height and planes == 1 and bpp == 32
        entries.append((width or 256, data[offset:offset + length]))
    return entries


def bmp_pixel(blob, size, x, y):
    """(r, g, b, a) of a 32-bit bottom-up icon BMP."""
    offset = 40 + ((size - 1 - y) * size + x) * 4
    b, g, r, a = blob[offset:offset + 4]
    return r, g, b, a


class Cmpr(unittest.TestCase):
    def test_solid_block(self):
        # c1 = pure red (0xF800) > c2 = black: index 0 everywhere -> red, opaque.
        block = struct.pack(">HHI", 0xF800, 0x0000, 0)
        texels = ci.decode_cmpr(block * 64)
        self.assertEqual(texels[0][0], [255, 0, 0, 255])
        self.assertEqual(texels[31][31], [255, 0, 0, 255])

    def test_transparent_index(self):
        # c1 <= c2 selects the 3-colour mode; index 3 is transparent.
        block = struct.pack(">HHI", 0x0000, 0xFFFF, 0xFFFFFFFF)
        texels = ci.decode_cmpr(block * 64)
        self.assertEqual(texels[5][5][3], 0)


class Icon(unittest.TestCase):
    def check(self, texture):
        data = ci.ico_bytes(ci.icon_images(texture))
        entries = read_ico(data)
        self.assertEqual([size for size, _ in entries], list(ci.ICON_SIZES))
        for size, blob in entries:
            self.assertEqual(struct.unpack_from("<I", blob, 0)[0], 40)
            self.assertEqual(bmp_pixel(blob, size, 0, 0)[3], 0, "corners are transparent")
            self.assertEqual(bmp_pixel(blob, size, size // 2, size // 2)[3], 255, "the coin is opaque")
        return entries

    def test_synthetic(self):
        self.check(struct.pack(">HHI", 0xFE00, 0x0000, 0) * 64)

    @unittest.skipUnless((GAME / "files/rsc/ATT.RSC").is_file(), "needs the local extracted disc")
    def test_real_coin(self):
        texture = ci.read_coin(GAME)
        entries = self.check(texture)
        r, g, b, _a = bmp_pixel(entries[0][1], 256, 128, 200)
        self.assertGreater(r, b, "the coin is gold")
        with tempfile.TemporaryDirectory() as folder:
            icon = ci.write_icon(GAME, Path(folder) / "game.ico")
            self.assertEqual(icon.read_bytes()[:4], b"\0\0\1\0")

    def test_missing_coin(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                ci.read_coin(folder)


if __name__ == "__main__":
    unittest.main()
