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
        if not section["size"] or not section["offset"]:
            continue  # BSS has no initialized bytes to compare.
        executable = section["executable"]
        start = addresses[model["module_id"]][section["index"]] - 0x80000000
        end = start + section["size"]
        if not 0 <= start < end <= len(memory):
            raise ValueError("Loaded section outside snapshot")
        actual, wanted = memory[start:end], bytes(expected[section["index"]])
        differences = [i for i, (a, b) in enumerate(zip(actual, wanted)) if a != b]
        if executable:
            checks.append(dict(name=path.name, module_id=model["module_id"], section=section["index"],
                               runtime_start=f"0x{start + 0x80000000:08X}", size=len(wanted),
                               mismatched_bytes=len(differences), first_offsets=differences[:16],
                               expected_sha256=hashlib.sha256(wanted).hexdigest(), actual_sha256=hashlib.sha256(actual).hexdigest()))
            continue
        # Data section: classify byte differences by whether the 4-byte word
        # containing them is a relocation write site. Relocation sites that
        # still match indicate the modeled link value survived; differences at
        # relocation sites or elsewhere indicate later guest mutation, which is
        # legal in mutable data and recorded for investigation, not treated as
        # an error.
        site_offsets = {r["offset"] for r in model["records"] if r["section"] == section["index"]}
        site_bytes = set()
        for site in site_offsets:
            site_bytes.update(range(site, min(site + 4, section["size"])))
        site_diffs = [i for i in differences if i in site_bytes]
        other_diffs = [i for i in differences if i not in site_bytes]
        checks.append(dict(name=path.name, module_id=model["module_id"], section=section["index"],
                           kind="data", runtime_start=f"0x{start + 0x80000000:08X}", size=len(wanted),
                           relocation_sites=len(site_offsets), mismatched_relocation_bytes=len(site_diffs),
                           first_relocation_offsets=site_diffs[:16], other_mismatched_bytes=len(other_diffs),
                           first_other_offsets=other_diffs[:16]))
report = dict(run=str(run), inventory=inventory, executable_checks=[c for c in checks if c.get("kind") != "data"],
              data_checks=[c for c in checks if c.get("kind") == "data"],
              limitation="Checks loaded code bytes and data relocation sites after relocation, not execution semantics, active lifetime or full-game coverage. Data mutations after load are legal and only recorded.")
args.output.write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(checks, indent=2))
raise SystemExit(any(c.get("mismatched_bytes", c.get("mismatched_relocation_bytes", 0)) for c in checks))
