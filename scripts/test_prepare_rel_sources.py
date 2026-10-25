"""Synthetic relocation-to-C operand and architectural-address checks."""
import struct
import unittest
from prepare_rel_sources import transform_chunk

BASE = 0x80570000


def fixture(kind=6, opcode=15):
    data = struct.pack(">I", (opcode << 26) | (3 << 21)) + bytes(12)
    return dict(module_id=1, sections=[dict(offset=0x100, size=16, executable=True, bytes=data)],
                records=[dict(section=0, offset=2, kind=kind, target_module=1, target_section=0, addend=0x8000)])


class TransformCases(unittest.TestCase):
    def test_ha_dynamic_symbol(self):
        text = "    // 80570100: lis r3, 0\n    ctx->gpr[3] = ((u32)(s32)(0) << 16);\n"
        changed, count = transform_chunk(text, fixture(), BASE)
        self.assertEqual(count, 1)
        self.assertIn("wario_rel_symbol(ctx, 1u, 0u, 0x00008000u)", changed)
        self.assertIn("+ 0x8000u) >> 16", changed)

    def test_lo_keeps_register_arithmetic(self):
        text = "    // 80570100: addi r3,r4,0\n    ctx->gpr[3] = ctx->gpr[4] + (u32)(s32)(0);\n"
        changed, count = transform_chunk(text, fixture(4, 14), BASE)
        self.assertEqual(count, 1)
        self.assertIn("ctx->gpr[4] + (u32)(s32)(s16)", changed)

    def test_pc_lr_cia_and_dispatch_namespace(self):
        model = fixture()
        model["records"] = []
        text = """    switch (ctx->pc) {
    case 0x80570100u: goto label_80570100;
    }
    ctx->pc = 0x80570100u;
    ctx->lr = 0x80570104u;
    if (ctx->pc == 0x80570108u) goto label_80570108;
    ppc_fallback_instruction(ctx, 0x80570100u, 0x80570100u);
    ctx->gpr[4] &= 0x80570100u;
"""
        changed, _ = transform_chunk(text, model, BASE)
        self.assertIn("switch (wario_rel_to_linked(ctx, 1u, ctx->pc))", changed)
        self.assertIn("case 0x80570100u: goto label_80570100;", changed)
        self.assertIn("ctx->lr = wario_rel_to_runtime(ctx, 1u, 0x80570104u)", changed)
        self.assertIn("ppc_fallback_instruction(ctx, 0x80570100u, wario_rel_to_runtime(ctx, 1u, 0x80570100u))", changed)
        self.assertIn("ctx->gpr[4] &= 0x80570100u;", changed)

    def test_unreviewed_opcode_rejected(self):
        with self.assertRaises(ValueError):
            transform_chunk("    // 80570100: ori\n    (u32)(s32)(0);\n", fixture(4, 24), BASE)

    def test_ambiguous_immediate_rejected(self):
        with self.assertRaises(ValueError):
            transform_chunk("    // 80570100: lis\n    (u32)(s32)(0) + (u32)(s32)(0);\n", fixture(), BASE)


if __name__ == "__main__":
    unittest.main()
