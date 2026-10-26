"""Look up main.dol addresses in the private dtk analysis disassembly.

Prints the containing function (dtk .fn label) and the original instruction or
data object for each address, plus the callers of each containing function.
Usage: python scripts/asm_lookup.py 0x800682E0 8006F7E8 ...
Reads generated/analysis/asm (private, game-derived; never commit output).
"""
import re
import sys
from pathlib import Path

ASM = Path(__file__).resolve().parents[1] / "generated/analysis/asm"
LINE = re.compile(r"/\* ([0-9A-F]{8}) [0-9A-F]{8}  ([0-9A-F ]{11}) \*/\t(.*)")
FN = re.compile(r"^\.fn ([^,\s]+)")
OBJ = re.compile(r"^\.obj ([^,\s]+)")


def index():
    instructions, owners, objects, calls = {}, {}, {}, {}
    for path in sorted(ASM.glob("*.s")):
        current = None
        obj = None
        for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if m := FN.match(raw):
                current = m.group(1)
            elif m := OBJ.match(raw):
                obj = [m.group(1), []]
                objects[m.group(1)] = obj
            elif raw.startswith(".endobj"):
                obj = None
            elif obj is not None and raw.strip():
                obj[1].append(raw.strip())
            if m := LINE.search(raw):
                address = int(m.group(1), 16)
                instructions[address] = (m.group(2), m.group(3))
                owners[address] = current
                if m.group(3).startswith("bl ") and current:
                    calls.setdefault(m.group(3).split()[1], set()).add(current)
    return instructions, owners, objects, calls


def main() -> int:
    instructions, owners, objects, calls = index()
    for argument in sys.argv[1:]:
        address = int(argument, 16)
        label = "lbl_%08X" % address
        if label in objects:
            print(f"{address:08X} data {label}: {' | '.join(objects[label][1][:4])}")
            continue
        if address not in instructions:
            print(f"{address:08X} not found")
            continue
        owner = owners[address]
        callers = sorted(calls.get(owner, ()))
        word, text = instructions[address]
        print(f"{address:08X} in {owner}: [{word}] {text}; callers={callers[:8]}{'...' if len(callers) > 8 else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
