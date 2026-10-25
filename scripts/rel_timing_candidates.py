"""Static timing-candidate scan for the eight REL modules.

Extends reports/timing-candidates.csv (main.dol) with REL entries expressed as
module ID + original section index + section offset, never a runtime address.
Two evidence kinds are combined per module:
- relocation records: REL24 calls and ADDR32/HA/LO references whose main-module
  symbol matches a timing routine;
- direct word scans of executable sections for timebase/decrementer SPR access
  and addis loads of 0xCC00/0xCD00 hardware bases (any destination register).
Linear scans admit false positives from embedded data; relocations are exact.
This is a static candidate inventory, not runtime proof.
"""
from __future__ import annotations
import argparse
import csv
import re
import struct
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from relocation_model import parse  # noqa: E402

TIMING_PATTERN = re.compile(r"Time|Tick|Alarm|Retrace|VIWait|SISetSampling|PPCMtdec")
TIMING_SPR = {22: "decrementer", 268: "timebase_low", 269: "timebase_high"}
WRITE_SPR = {22, 284, 285}


def u32(data, offset):
    return struct.unpack_from(">I", data, offset)[0]


def load_symbols(path):
    """Address -> name for identified main-module text symbols."""
    symbols = {}
    if path and path.is_file():
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            match = re.match(r"\s*\.\w+\s*\|\s*(0x[0-9A-Fa-f]+)\s*\|[^|]*\|\s*(\S+)", line)
            if match:
                symbols[int(match[1], 16)] = match[2]
    return symbols


def word_kind(word):
    """Classify one raw instruction word, mirroring the main.dol scan rules."""
    op, xo = word >> 26, (word >> 1) & 1023
    spr = ((word >> 16) & 31) | (((word >> 11) & 31) << 5)
    if op == 31 and xo in (339, 371) and spr in TIMING_SPR:
        return f"read_{TIMING_SPR[spr]}"
    if op == 31 and xo == 467 and spr in WRITE_SPR:
        return f"write_timing_spr_{spr}"
    if op == 15 and (word & 0xffff) in (0xCC00, 0xCD00):
        register = (word >> 16) & 31
        return f"hardware_base_load_candidate_r{register}"
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--modules", type=Path, default=ROOT / "original/GWWE01/files/dll")
    parser.add_argument("--dtk-info", type=Path, default=ROOT / "reports/dtk-main-info.txt")
    parser.add_argument("--out", type=Path, default=ROOT / "reports/timing-candidates-rel.csv")
    args = parser.parse_args()
    symbols = load_symbols(args.dtk_info)
    hits = []
    scanned = {"executable_words": 0, "data_words": 0}
    for rel in sorted(args.modules.glob("*.rel")):
        data = rel.read_bytes()
        model = parse(data)
        module_id = model["module_id"]
        # Exact relocation evidence: what each patched site references.
        for record in model["records"]:
            if record["target_module"] != 0:
                continue
            name = symbols.get(record["addend"])
            if not name or not TIMING_PATTERN.search(name):
                continue
            section = record["section"]
            offset = record["offset"]
            kind = record["kind"]
            label = {1: "addr32", 4: "lo16", 6: "ha16", 10: "rel24_call"}[kind]
            hits.append(dict(
                module=f"{rel.stem}_{module_id}", section=section,
                offset=f"0x{offset:08X}", address="unloaded",
                file_offset=f"0x{model['sections'][section]['offset'] + offset:08X}"
                if model["sections"][section]["offset"] else "unloaded",
                word=f"0x{u32(model['sections'][section]['bytes'], offset):08X}",
                reason=f"{label}_{name}",
                status="relocation_target_static_candidate_not_runtime_proven"))
        # Direct word scan of executable sections, matching the main.dol rules
        # but reporting any destination register for hardware-base addis.
        for section in model["sections"]:
            if not section["offset"] or not section["size"]:
                continue
            executable = section["executable"]
            for relative in range(0, section["size"] - 3, 4):
                scanned["executable_words" if executable else "data_words"] += 1
                word = u32(section["bytes"], relative)
                if executable:
                    reason = word_kind(word)
                elif 0xCC000000 <= word <= 0xCDFFFFFF:
                    # Non-executable data holding an absolute hardware MMIO
                    # address; recorded for completeness, may be a false positive.
                    reason = "hardware_address_data_candidate"
                else:
                    reason = None
                if reason:
                    hits.append(dict(
                        module=f"{rel.stem}_{module_id}", section=section["index"],
                        offset=f"0x{relative:08X}", address="unloaded",
                        file_offset=f"0x{section['offset'] + relative:08X}",
                        word=f"0x{word:08X}", reason=reason,
                        status="static_candidate_not_runtime_proven"))
    with args.out.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=[
            "module", "section", "offset", "address", "file_offset", "word", "reason", "status"])
        writer.writeheader()
        writer.writerows(hits)
    counts = {}
    for hit in hits:
        counts[hit["module"]] = counts.get(hit["module"], 0) + 1
    print(f"{len(hits)} REL timing candidates -> {args.out}")
    print(f"scanned words: {scanned['executable_words']} executable, {scanned['data_words']} data")
    for name in sorted(counts):
        print(f"  {name}: {counts[name]}")


if __name__ == "__main__":
    main()
