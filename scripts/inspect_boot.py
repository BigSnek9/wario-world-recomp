"""Summarize private boot evidence without changing game memory or instructions."""
import argparse
import json
from pathlib import Path
import re
import struct

ROOT = Path(__file__).resolve().parents[1]


def summarize(run, root=ROOT):
    low, high = run / "control/mem1-low.bin", run / "control/mem1-high.bin"
    memory = low.read_bytes() + high.read_bytes() if low.exists() and high.exists() else b""
    def word(address):
        offset = address - 0x80000000
        return struct.unpack_from(">I", memory, offset)[0] if 0 <= offset <= len(memory) - 4 else None

    listing = {}
    for source in (root / "generated/analysis/asm").glob("*.s"):
        for line in source.read_text(errors="replace").splitlines():
            match = re.match(r"/\* ([0-9A-Fa-f]{8}) [0-9A-Fa-f]{8}\s+(?:[0-9A-Fa-f]{2}\s+){4}\*/\s*(.*)", line)
            if match:
                listing[int(match[1], 16)] = match[2]
    helpers = []
    for pc, raw in re.findall(r"\[wario-helper\] pc=([0-9a-f]+) raw=([0-9a-f]+)", (run / "runner.log").read_text(errors="replace")):
        address = int(pc, 16)
        helpers.append(dict(address=f"0x{address:08X}", instruction=f"0x{int(raw, 16):08X}",
                            disassembly=listing.get(address), memory_word=word(address)))
    modules = []
    for path in sorted((root / "original/GWWE01/files/dll").glob("*.rel")):
        original = path.read_bytes()
        module_id, count, table, version = (struct.unpack_from(">I", original, x)[0] for x in (0, 12, 16, 28))
        cursor = 0
        while memory:
            offset = memory.find(struct.pack(">I", module_id), cursor)
            if offset < 0:
                break
            cursor = offset + 4
            address = 0x80000000 + offset
            if offset % 4 or word(address + 12) != count or word(address + 28) != version:
                continue
            table_value = word(address + 16)
            if table_value == table:
                section_table = address + table
                state = "unlinked file-offset table"
            elif table_value == address + table:
                section_table = table_value
                state = "linked absolute table"
            else:
                continue
            sections = []
            for index in range(count):
                start, size = word(section_table + index * 8), word(section_table + index * 8 + 4)
                sections.append(dict(index=index, start=None if start is None else f"0x{start:08X}", size=size))
            modules.append(dict(name=path.name, module_id=module_id, header=f"0x{address:08X}", state=state, sections=sections))
    globals_ = {f"0x{x:08X}": word(x) for x in (0x801FD910, 0x801FD914, 0x801FD924, 0x801FD930, 0x801FD95C, 0x801FD960)}
    return dict(run=str(run), memory_bytes=len(memory), globals=globals_, helper_sites=helpers,
                module_header_candidates=modules,
                limitation="Header candidates are not proof of active execution. This is a paused diagnostic snapshot, not a parity or coverage test.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = json.dumps(summarize(args.run.resolve()), indent=2) + "\n"
    if args.output:
        args.output.write_text(report, encoding="utf-8")
    else:
        print(report)
