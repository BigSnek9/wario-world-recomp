"""Read-only disc/executable audit. Standard library only; no game patching."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import struct


def u32(data, offset):
    return struct.unpack_from(">I", data, offset)[0]


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def checked_slice(data, offset, size):
    if offset < 0 or size < 0 or offset + size > len(data):
        raise ValueError(f"Out-of-bounds region: {offset:#x}+{size:#x}")
    return data[offset:offset + size]


def parse_dol(data):
    checked_slice(data, 0, 0x100)
    sections = []
    for kind, count, off_base, addr_base, size_base in [
        ("text", 7, 0, 0x48, 0x90), ("data", 11, 0x1c, 0x64, 0xac)
    ]:
        for index in range(count):
            offset, address, size = (u32(data, b + index * 4) for b in
                                     (off_base, addr_base, size_base))
            if size:
                checked_slice(data, offset, size)
                sections.append(dict(kind=kind, index=index, offset=offset,
                                     address=address, size=size))
    return dict(entry=u32(data, 0xe0), bss_address=u32(data, 0xd8),
                bss_size=u32(data, 0xdc), sections=sections)


def parse_rel(data):
    checked_slice(data, 0, 0x40)
    count, table = u32(data, 0xc), u32(data, 0x10)
    checked_slice(data, table, count * 8)
    sections = []
    for index in range(count):
        raw, size = struct.unpack_from(">II", data, table + index * 8)
        offset = raw & ~3
        if size and offset:
            checked_slice(data, offset, size)
        sections.append(dict(index=index, offset=offset, size=size,
                             executable=bool(raw & 1), bss=not offset and bool(size)))
    imports = []
    imp_offset, imp_size = u32(data, 0x28), u32(data, 0x2c)
    checked_slice(data, imp_offset, imp_size)
    if imp_size % 8:
        raise ValueError("REL import table size must be a multiple of eight")
    for offset in range(imp_offset, imp_offset + imp_size, 8):
        module_id, reloc_offset = struct.unpack_from(">II", data, offset)
        records = 0
        while True:
            checked_slice(data, reloc_offset, 8)
            _, rtype, _, _ = struct.unpack_from(">HBBI", data, reloc_offset)
            records += 1
            reloc_offset += 8
            if rtype == 203:  # R_DOLPHIN_END
                break
        imports.append(dict(module_id=module_id, relocation_records=records))
    return dict(module_id=u32(data, 0), version=u32(data, 0x1c),
                bss_size=u32(data, 0x20), sections=sections, imports=imports,
                prolog_section=data[0x30], prolog_offset=u32(data, 0x34),
                epilog_section=data[0x31], epilog_offset=u32(data, 0x38))


def fst_entries(fst):
    checked_slice(fst, 0, 12)
    if fst[0] != 1:
        raise ValueError("Invalid FST root")
    count = u32(fst, 8)
    checked_slice(fst, 0, count * 12)
    strings = count * 12
    stack = [(count, Path())]
    for index in range(1, count):
        while index >= stack[-1][0]:
            stack.pop()
        word, offset, size = struct.unpack_from(">III", fst, index * 12)
        start = strings + (word & 0xffffff)
        checked_slice(fst, start, 1)
        end = fst.index(0, start)
        name = fst[start:end].decode("ascii")
        if name in ("", ".", "..") or any(c in name for c in "/\\:"):
            raise ValueError("Unsafe disc filename")
        path = stack[-1][1] / name
        if word >> 24:
            if not index < size <= stack[-1][0]:
                raise ValueError("Invalid directory boundary")
            stack.append((size, path))
        else:
            yield path, offset, size


def verify_extraction(iso, extracted):
    records = []
    with iso.open("rb") as stream:
        header = stream.read(0x440)
        if u32(header, 0x1c) != 0xc2339f3d:
            raise ValueError("Not a GameCube disc")
        dol_offset, fst_offset, fst_size = struct.unpack_from(">III", header, 0x420)
        stream.seek(fst_offset)
        fst = stream.read(fst_size)
        if fst != (extracted / "sys/fst.bin").read_bytes():
            raise ValueError("FST differs from disc")
        dol = (extracted / "sys/main.dol").read_bytes()
        parse_dol(dol)
        stream.seek(dol_offset)
        if stream.read(len(dol)) != dol:
            raise ValueError("DOL differs from disc")
        for relative, offset, size in fst_entries(fst):
            target = extracted / "files" / relative
            if offset + size > iso.stat().st_size or target.stat().st_size != size:
                raise ValueError(f"Invalid size or offset: {relative}")
            stream.seek(offset)
            h = hashlib.sha256()
            remaining = size
            with target.open("rb") as candidate:
                while remaining:
                    chunk = stream.read(min(remaining, 1024 * 1024))
                    if not chunk or candidate.read(len(chunk)) != chunk:
                        raise ValueError(f"Extracted bytes differ: {relative}")
                    h.update(chunk)
                    remaining -= len(chunk)
            records.append(dict(path=relative.as_posix(), disc_offset=offset,
                                size=size, sha256=h.hexdigest()))
    return header, records


def scan_code(module, data, sections, symbols=None):
    """Find encoded time-base/DEC instructions, VI base loads and direct calls.

    This is a linear scan, so embedded data can produce false positives.
    REL addresses remain section-relative until a loader assigns a base.
    """
    hits = []
    for section in sections:
        if not (section.get("kind") == "text" or section.get("executable")):
            continue
        if section.get("bss") or not section["offset"]:
            continue
        begin, size = section["offset"], section["size"]
        for relative in range(0, size - 3, 4):
            word = u32(data, begin + relative)
            op, xo = word >> 26, (word >> 1) & 1023
            spr = ((word >> 16) & 31) | (((word >> 11) & 31) << 5)
            reason = None
            if op == 31 and xo in (339, 371) and spr in (22, 268, 269):
                reason = f"read_{ {22: 'decrementer', 268: 'timebase_low', 269: 'timebase_high'}[spr]}"
            elif op == 31 and xo == 467 and spr in (22, 284, 285):
                reason = f"write_timing_spr_{spr}"
            elif op == 15 and ((word >> 16) & 31) == 0 and (word & 0xffff) in (0xcc00, 0xcd00):
                reason = "hardware_base_load_candidate"
            address = section.get("address", 0) + relative
            if op == 18 and word & 1 and symbols:
                displacement = word & 0x3fffffc
                if displacement & 0x2000000:
                    displacement -= 0x4000000
                target = (displacement if word & 2 else address + displacement) & 0xffffffff
                name = symbols.get(target)
                if name and re.search(r"Time|Tick|Alarm|Retrace|VIWait|SISetSampling|PPCMtdec", name):
                    reason = f"call_{name}"
            if reason:
                hits.append(dict(module=module, section=section["index"],
                                 offset=f"0x{relative:08X}",
                                 address=f"0x{address:08X}" if "address" in section else "unloaded",
                                 file_offset=f"0x{begin + relative:08X}",
                                 word=f"0x{word:08X}", reason=reason,
                                 status="static_candidate_not_runtime_proven"))
    return hits


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iso", type=Path, required=True)
    parser.add_argument("--extracted", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--dtk-info", type=Path)
    args = parser.parse_args()
    header, assets = verify_extraction(args.iso, args.extracted)
    symbols = {}
    if args.dtk_info:
        for line in args.dtk_info.read_text(encoding="utf-8-sig").splitlines():
            match = re.match(r"\s*\.\w+\s*\|\s*(0x[0-9A-Fa-f]+)\s*\|[^|]*\|\s*(\S+)", line)
            if match:
                symbols[int(match[1], 16)] = match[2]
    main_dol = args.extracted / "sys/main.dol"
    data = main_dol.read_bytes()
    dol = parse_dol(data)
    hits = scan_code("main.dol", data, dol["sections"], symbols)
    modules = []
    for rel in sorted((args.extracted / "files").rglob("*.rel")):
        data = rel.read_bytes()
        info = parse_rel(data)
        info.update(path=rel.relative_to(args.extracted).as_posix(), sha256=digest(rel))
        modules.append(info)
        hits.extend(scan_code(rel.name, data, info["sections"]))
    known_ids = {0} | {m["module_id"] for m in modules}
    missing = sorted({i["module_id"] for m in modules for i in m["imports"]} - known_ids)
    if missing:
        raise ValueError(f"Unresolved REL module IDs: {missing}")
    args.out.mkdir(parents=True, exist_ok=True)
    report = dict(schema=1, disc_id=header[:6].decode("ascii"), disc_number=header[6],
                  revision=header[7], iso_size=args.iso.stat().st_size,
                  iso_sha256=digest(args.iso), dol_sha256=digest(main_dol), dol=dol,
                  extraction_verified=True, asset_count=len(assets),
                  asset_bytes=sum(a["size"] for a in assets), assets=assets,
                  rel_modules=modules, timing_candidate_count=len(hits),
                  bit_accuracy="unverified: static inventory is not execution parity")
    (args.out / "inventory.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    with (args.out / "timing-candidates.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["module", "section", "offset", "address", "file_offset", "word", "reason", "status"])
        writer.writeheader()
        writer.writerows(hits)
    print(json.dumps({k: report[k] for k in ("disc_id", "revision", "iso_sha256", "dol_sha256", "asset_count", "asset_bytes", "extraction_verified", "timing_candidate_count")}, indent=2))
    print("REL module IDs:", [(Path(m["path"]).name, m["module_id"]) for m in modules])


if __name__ == "__main__":
    main()
