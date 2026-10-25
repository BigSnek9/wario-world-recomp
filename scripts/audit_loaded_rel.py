"""Compare loaded executable REL sections against independently relocated inputs."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from build import check_game
from inspect_boot import summarize
from relocation_model import parse, apply

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("run", type=Path)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
check_game()
run = args.run.resolve()
inspection = summarize(run)
memory = (run / "control/mem1-low.bin").read_bytes() + (run / "control/mem1-high.bin").read_bytes()
linked = [m for m in inspection["module_header_candidates"] if m["state"] == "linked absolute table"]
addresses = {m["module_id"]: {s["index"]: int(s["start"], 16) & ~3 for s in m["sections"]} for m in linked}
inventory, checks = [], []
for path in sorted((ROOT / "original/GWWE01/files/dll").glob("*.rel")):
    model = parse(path.read_bytes())
    all_kinds = Counter(r["kind"] for r in model["records"])
    code_kinds = Counter(r["kind"] for r in model["records"] if model["sections"][r["section"]]["executable"])
    inventory.append(dict(name=path.name, module_id=model["module_id"], relocations=dict(all_kinds), code_relocations=dict(code_kinds)))
    if model["module_id"] not in addresses:
        continue
    expected = apply(model, addresses)
    for section in model["sections"]:
        if not section["executable"] or not section["size"]:
            continue
        start = addresses[model["module_id"]][section["index"]] - 0x80000000
        end = start + section["size"]
        if not 0 <= start < end <= len(memory):
            raise ValueError("Loaded code section outside snapshot")
        actual, wanted = memory[start:end], bytes(expected[section["index"]])
        differences = [i for i, (a, b) in enumerate(zip(actual, wanted)) if a != b]
        checks.append(dict(name=path.name, module_id=model["module_id"], section=section["index"],
                           runtime_start=f"0x{start + 0x80000000:08X}", size=len(wanted),
                           mismatched_bytes=len(differences), first_offsets=differences[:16],
                           expected_sha256=hashlib.sha256(wanted).hexdigest(), actual_sha256=hashlib.sha256(actual).hexdigest()))
report = dict(run=str(run), inventory=inventory, executable_checks=checks,
              limitation="Checks loaded code bytes after relocation, not execution semantics, active lifetime, data state or full-game coverage.")
args.output.write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(checks, indent=2))
raise SystemExit(not checks or any(c["mismatched_bytes"] for c in checks))
