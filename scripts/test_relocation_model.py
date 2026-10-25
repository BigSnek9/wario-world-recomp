"""Synthetic relocation edge cases; no game bytes."""
import struct
import unittest
from relocation_model import apply


def model(kind, addend, target=0, target_section=0, data=b"\x48\x00\x00\x01"):
    return dict(module_id=8, sections=[dict(bytes=data)], records=[dict(section=0, offset=0,
                kind=kind, target_module=target, target_section=target_section, addend=addend)])


class RelocationCases(unittest.TestCase):
    def test_main_absolute(self):
        self.assertEqual(apply(model(1, 0x80123456), {})[0], bytes.fromhex("80123456"))

    def test_low_and_adjusted_high(self):
        self.assertEqual(apply(model(4, 0x80128000), {})[0][:2], bytes.fromhex("8000"))
        self.assertEqual(apply(model(6, 0x80128000), {})[0][:2], bytes.fromhex("8013"))
        self.assertEqual(apply(model(6, 0x80127fff), {})[0][:2], bytes.fromhex("8012"))

    def test_empty_target_section_addend(self):
        self.assertEqual(apply(model(6, 0x12348000, 8, 2), {8: {2: 0}})[0][:2], bytes.fromhex("1235"))

    def test_signed_branch_preserves_link(self):
        self.assertEqual(apply(model(10, 0x80000000), {8: {0: 0x80400000}})[0], bytes.fromhex("4bc00001"))

    def test_branch_range_rejected(self):
        with self.assertRaises(ValueError):
            apply(model(10, 0x84000000), {8: {0: 0x80000000}})

    def test_missing_module_rejected(self):
        with self.assertRaises(KeyError):
            apply(model(1, 0x20, 7), {8: {0: 0x80400000}})

    def test_symbol_wrap(self):
        self.assertEqual(apply(model(1, 0x30, 8), {8: {0: 0xfffffff0}})[0], struct.pack(">I", 0x20))


if __name__ == "__main__":
    unittest.main()
