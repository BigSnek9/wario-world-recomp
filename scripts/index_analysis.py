"""Index local dtk assembly without copying game instructions into public docs."""
import argparse
import csv
from pathlib import Path
import re

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--analysis", type=Path, required=True)
parser.add_argument("--out", type=Path, required=True)
args = parser.parse_args()
functions = []
calls = []
for path in sorted(args.analysis.rglob("*.s")):
    pending = None
    current = None
    module = path.relative_to(args.analysis).parts[0]
    if module == "asm":
        module = "main"
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        match = re.match(r"# (\S+):0x([0-9A-Fa-f]+) \| 0x([0-9A-Fa-f]+) \| size: 0x([0-9A-Fa-f]+)", line)
        if match:
            pending = dict(module=module, section=match[1], section_offset="0x" + match[2],
                           address_or_offset="0x" + match[3], size=int(match[4], 16),
                           assembly=path.relative_to(args.analysis).as_posix())
        fn = re.match(r"\.fn (.+), (?:global|local|weak)", line)
        if fn and pending:
            current = {**pending, "name": fn[1], "line": line_number}
            functions.append(current)
        call = re.search(r"/\* ([0-9A-Fa-f]+) .*?\*/\s+(bl|bctrl)\s*(\S*)", line)
        if call and current:
            calls.append(dict(module=module, caller=current["name"],
                              source="0x" + call[1], target=call[3] or "ctr_indirect",
                              assembly=current["assembly"], line=line_number))
args.out.mkdir(parents=True, exist_ok=True)
for filename, records, fields in [
    ("functions.csv", functions, ["module", "section", "section_offset", "address_or_offset", "size", "assembly", "name", "line"]),
    ("calls.csv", calls, ["module", "caller", "source", "target", "assembly", "line"]),
]:
    with (args.out / filename).open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)
print(f"Indexed {len(functions)} functions and {len(calls)} call sites; outputs are private analysis evidence.")
