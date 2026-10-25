"""Synthetic DOL fixtures for SDK vector derivation, without game bytes."""
import struct
import unittest
from prepare_vector_sources import vector_images


def fake_dol():
    output = bytearray(0x400)
    for index, (address, size, offset) in enumerate(((0x8019CFE4,0x98,0x100), (0x801A2EB4,0x1c,0x200), (0x801A146C,0x80,0x280))):
        for header, value in ((index*4,offset),(0x48+index*4,address),(0x90+index*4,size)):
            struct.pack_into(">I",output,header,value)
        output[offset:offset+size] = bytes([index+1])*size
    struct.pack_into(">I",output,0x168,0x38600000)
    return bytes(output)


class VectorCases(unittest.TestCase):
    def test_vector_ids_and_source_preserved(self):
        source = fake_dol()
        images = vector_images(source)
        self.assertEqual(len(images),16)
        for index, (name,address,code) in enumerate(images[:15]):
            if address == 0xc00:
                continue
            self.assertEqual(struct.unpack_from(">I",code,0x68)[0],0x38600000|index)
            self.assertEqual(code[:0x68],source[0x100:0x168])
            self.assertEqual(code[0x6c:],source[0x16c:0x198])
        self.assertEqual(source,fake_dol())

    def test_syscall_and_physical_config(self):
        images = vector_images(fake_dol())
        self.assertEqual(images[9][1:],(0xc00,bytes([2])*0x1c))
        self.assertEqual(images[-1][1:],(0x001a146c,bytes([3])*0x80))

    def test_bad_template_rejected(self):
        data=bytearray(fake_dol()); data[0x168]=0
        with self.assertRaises(ValueError):
            vector_images(data)


if __name__ == "__main__":
    unittest.main()
