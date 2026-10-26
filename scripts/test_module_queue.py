import struct
import unittest
from inspect_boot import read_module_queue

class ModuleQueueTests(unittest.TestCase):
    def memory(self,head=0,tail=0):
        m=bytearray(0x4000)
        struct.pack_into(">II",m,0x30c8,head,tail)
        return m
    def header(self,m,address,next_=0,prev=0):
        off=address-0x80000000
        for delta,value in [(0,7),(4,next_),(8,prev),(12,23),(16,address+0x4c),(28,2)]:
            struct.pack_into(">I",m,off+delta,value)
    def test_empty(self):self.assertTrue(read_module_queue(self.memory())["consistent"])
    def test_one(self):
        m=self.memory(0x80003200,0x80003200);self.header(m,0x80003200)
        q=read_module_queue(m);self.assertTrue(q['consistent']);self.assertEqual(len(q['headers']),1)
    def test_two(self):
        m=self.memory(0x80003200,0x80003300);self.header(m,0x80003200,0x80003300);self.header(m,0x80003300,prev=0x80003200)
        q=read_module_queue(m);self.assertTrue(q['consistent']);self.assertEqual(len(q['headers']),2)
    def test_missing(self):self.assertFalse(read_module_queue(b'')['consistent'])
    def test_outside(self):self.assertFalse(read_module_queue(self.memory(0x90000000,0x90000000))['consistent'])
    def test_unaligned(self):self.assertFalse(read_module_queue(self.memory(0x80003201,0x80003201))['consistent'])
    def test_bad_backlink(self):
        m=self.memory(0x80003200,0x80003200);self.header(m,0x80003200,prev=0x80003300)
        self.assertFalse(read_module_queue(m)['consistent'])
    def test_bad_tail(self):
        m=self.memory(0x80003200,0x80003300);self.header(m,0x80003200)
        self.assertFalse(read_module_queue(m)['consistent'])
    def test_cycle(self):
        m=self.memory(0x80003200,0x80003300);self.header(m,0x80003200,0x80003300);self.header(m,0x80003300,0x80003200,0x80003200)
        self.assertFalse(read_module_queue(m)['consistent'])

if __name__=='__main__':unittest.main()
