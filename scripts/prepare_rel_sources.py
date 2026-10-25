"""Prepare position-independent C from pinned REL translations for later integration.

Only explicit relocation operands and architectural PC/LR/CIA operands change.
Labels/dispatch tables stay in the translator's private address namespace. This
stage does not build a runnable bundle or establish native REL coverage.
"""
from pathlib import Path
import json
import re
from relocation_model import parse, be32

ROOT = Path(__file__).resolve().parents[1]


def write_changed(path, text):
    if not path.is_file() or path.read_text() != text:
        path.write_text(text)


def transform_chunk(text, model, base):
    module = model["module_id"]
    relocation_by_pc = {}
    code = [s for s in model["sections"] if s["executable"] and s["size"]]
    for relocation in model["records"]:
        section = model["sections"][relocation["section"]]
        if section["executable"]:
            pc = base + section["offset"] + (relocation["offset"] & ~3)
            if pc in relocation_by_pc:
                raise ValueError("Multiple code relocations on one instruction")
            relocation_by_pc[pc] = relocation
    comments = list(re.finditer(r"^    // ([0-9A-Fa-f]{8}): [^\n]*\n", text, re.M))
    rewrites = 0
    pieces = [text[:comments[0].start()]] if comments else [text]
    for index in range(len(comments)):
        match = comments[index]
        end = comments[index + 1].start() if index + 1 < len(comments) else len(text)
        pc = int(match[1], 16)
        record = relocation_by_pc.get(pc)
        if not record or record["kind"] == 10:
            pieces.append(text[match.start():end])
            continue
        if record["kind"] not in (4, 6):
            raise ValueError("Unsupported code relocation")
        section = model["sections"][record["section"]]
        instruction = be32(section["bytes"], record["offset"] & ~3)
        opcode = instruction >> 26
        if record["kind"] == 6 and opcode != 15:
            raise ValueError("HA patch is not addis")
        if record["kind"] == 4 and opcode not in (14, 32, 33, 34, 35, 36, 37, 38, 39, 44, 48, 49, 50, 53):
            raise ValueError(f"Unreviewed LO opcode {opcode}")
        target = record["target_module"]
        symbol = (f"0x{record['addend']:08X}u" if target == 0 else
                  f"wario_rel_symbol(ctx, {target}u, {record['target_section']}u, 0x{record['addend']:08X}u)")
        immediate = (f"(u32)(s32)(s16)(({symbol} + 0x8000u) >> 16)" if record["kind"] == 6 else
                     f"(u32)(s32)(s16)({symbol})")
        body = text[match.end():end]
        body, count = re.subn(r"\(u32\)\(s32\)\(-?\d+\)", lambda _: immediate, body)
        if count != 1:
            raise ValueError(f"Expected one D-form immediate at {pc:08X}, found {count}")
        pieces.append(text[match.start():match.end()] + body)
        rewrites += 1
    text = "".join(pieces)
    # Actual guest addresses must remain in PC/LR and exception arguments.
    output = []
    for line in text.splitlines(keepends=True):
        if line.lstrip().startswith(("case ", "//")):
            output.append(line)
            continue
        def replace_pc(match):
            address = int(match[1], 16)
            if not any(base + s["offset"] <= address <= base + s["offset"] + s["size"] for s in code):
                return match[0]
            return f"wario_rel_to_runtime(ctx, {module}u, {match[0]})"
        if re.search(r"ctx->(?:pc|lr)\s*(?:=|==)", line) or "dolrecomp_call(ctx," in line:
            line = re.sub(r"0x([0-9A-Fa-f]{8})u", replace_pc, line)
        elif "ppc_" in line:
            # CIA is the last argument; raw instruction words remain unchanged.
            line = re.sub(r"0x([0-9A-Fa-f]{8})u(?=\))", replace_pc, line)
        line = line.replace("switch (ctx->pc)", f"switch (wario_rel_to_linked(ctx, {module}u, ctx->pc))")
        output.append(line)
    return "".join(output), rewrites


def prepare():
    from build import check_game
    check_game()
    destination = ROOT / "generated/rel-position-independent"
    destination.mkdir(parents=True, exist_ok=True)
    base = 0x80500000
    report = []
    for path in sorted((ROOT / "original/GWWE01/files/dll").glob("*.rel")):
        data = path.read_bytes()
        model = parse(data)
        name = path.stem + "_" + str(model["module_id"])
        source = ROOT / "generated/rels/generated/rels" / name
        out = destination / "rels" / name
        (out / "chunks").mkdir(parents=True, exist_ok=True)
        total = 0
        covered = set()
        for chunk in sorted((source / "chunks").glob("*.c")):
            original = chunk.read_text()
            covered.update(int(a, 16) for a in re.findall(r"^    // ([0-9A-Fa-f]{8}):", original, re.M))
            text, count = transform_chunk(original, model, base)
            write_changed(out / "chunks" / chunk.name, text)
            total += count
        expected = sum(r["kind"] in (4, 6) and model["sections"][r["section"]]["executable"] for r in model["records"])
        if total < expected:
            raise ValueError(f"Missing rewritten operands in {name}: {total} < {expected}")
        expected_pcs = {base + model["sections"][r["section"]]["offset"] + (r["offset"] & ~3)
                        for r in model["records"] if r["kind"] in (4, 6) and model["sections"][r["section"]]["executable"]}
        if not expected_pcs <= covered:
            raise ValueError(f"Missing relocated instruction sites in {name}")
        header = (source / "generated.h").read_text()
        header = header.replace("#include DOLRECOMP_CPU_HEADER", '#include DOLRECOMP_CPU_HEADER\n#include "../../rel_support.h"')
        header = header.replace("dolrecomp_find_original(address);", f"dolrecomp_find_original(wario_rel_to_linked(ctx, {model['module_id']}u, address));")
        write_changed(out / "generated.h", header)
        report.append(dict(name=name, module_id=model["module_id"], linked_base=f"0x{base:08X}",
                           relocation_operands=expected, emitted_operands=total))
        base = (base + len(data) + be32(data, 0x20) + 0xffff) & ~0xffff
    (ROOT / "reports/position-independent-rel-preparation.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    print("Prepared sources only; runtime support/verification and bundle integration remain required.")


if __name__ == "__main__":
    prepare()
