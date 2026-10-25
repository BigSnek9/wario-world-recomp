"""Synthetic disc tests: byte verification must reject corrupted/truncated assets."""
from pathlib import Path
import struct
import tempfile
import unittest
from audit_game import parse_dol, parse_rel, verify_extraction


class DiscAuditTests(unittest.TestCase):
    def setUp(self):
        test_root = Path(__file__).resolve().parents[1] / "build/audit-tests"
        test_root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=test_root)
        self.root = Path(self.temp.name)
        self.extracted = self.root / "extracted"
        (self.extracted / "sys").mkdir(parents=True)
        (self.extracted / "files").mkdir()
        dol = bytearray(0x104)
        for offset, value in [(0, 0x100), (0x48, 0x80003100), (0x90, 4), (0xe0, 0x80003100)]:
            struct.pack_into(">I", dol, offset, value)
        dol[0x100:] = b"TEST"
        fst = struct.pack(">IIIIII", 0x01000000, 0, 2, 1, 0x700, 5) + b"\0sample\0"
        iso = bytearray(0x800)
        iso[:6] = b"TEST01"
        struct.pack_into(">I", iso, 0x1c, 0xc2339f3d)
        struct.pack_into(">III", iso, 0x420, 0x440, 0x600, len(fst))
        iso[0x440:0x544] = dol
        iso[0x600:0x600 + len(fst)] = fst
        iso[0x700:0x705] = b"hello"
        self.iso = self.root / "test.iso"
        self.iso.write_bytes(iso)
        (self.extracted / "sys/main.dol").write_bytes(dol)
        (self.extracted / "sys/fst.bin").write_bytes(fst)
        (self.extracted / "files/sample").write_bytes(b"hello")

    def tearDown(self):
        self.temp.cleanup()

    def test_matching_disc(self):
        _, files = verify_extraction(self.iso, self.extracted)
        self.assertEqual([(f["path"], f["size"]) for f in files], [("sample", 5)])

    def test_same_size_corruption_rejected(self):
        (self.extracted / "files/sample").write_bytes(b"jello")
        with self.assertRaisesRegex(ValueError, "bytes differ"):
            verify_extraction(self.iso, self.extracted)

    def test_truncated_asset_rejected(self):
        (self.extracted / "files/sample").write_bytes(b"hell")
        with self.assertRaisesRegex(ValueError, "size or offset"):
            verify_extraction(self.iso, self.extracted)

    def test_unsafe_disc_path_rejected(self):
        image = bytearray(self.iso.read_bytes())
        image[0x600 + 25:0x600 + 32] = b"../bad\0"
        self.iso.write_bytes(image)
        (self.extracted / "sys/fst.bin").write_bytes(image[0x600:0x620])
        with self.assertRaisesRegex(ValueError, "Unsafe disc filename"):
            verify_extraction(self.iso, self.extracted)

    def test_truncated_executables_rejected(self):
        for parser in (parse_dol, parse_rel):
            with self.subTest(parser=parser.__name__), self.assertRaises(ValueError):
                parser(b"short")


if __name__ == "__main__":
    unittest.main()
