"""Emit private immutable REL code and relocation metadata, without load guesses."""


def emit(models):
    lines = ['#include "rel_support.h"']
    for model in models:
        mid = model["module_id"]
        for section in model["sections"]:
            index = section["index"]
            if not section["executable"] or not section["size"]:
                continue
            name = f"code_{mid}_{index}"
            lines.append(f"static const u8 {name}[] = {{")
            raw = section["bytes"]
            for start in range(0, len(raw), 24):
                lines.append(",".join(f"0x{b:02X}" for b in raw[start:start + 24]) + ",")
            lines.append("};")
            fixes = [r for r in model["records"] if r["section"] == index]
            lines.append(f"static const WarioRelFixup fixes_{mid}_{index}[] = {{")
            for fix in fixes:
                values = [fix[k] for k in ("offset", "kind", "target_module", "target_section", "addend")]
                lines.append("{" + ",".join(f"0x{v:X}u" for v in values) + "},")
            if not fixes:
                lines.append("{0,0,0,0,0},")
            lines.append("};")
        lines.append(f"static const WarioRelSection sections_{mid}[] = {{")
        for section in model["sections"]:
            index = section["index"]
            if section["executable"] and section["size"]:
                count = sum(r["section"] == index for r in model["records"])
                start = model["linked_base"] + section["offset"]
                lines.append(f"{{0x{start:08X}u,{section['size']}u,1u,code_{mid}_{index},fixes_{mid}_{index},{count}u}},")
            else:
                lines.append(f"{{0u,{section['size']}u,0u,0,0,0u}},")
        lines.append("};")
    lines.append("const WarioRelModule wario_rel_modules[] = {")
    for model in models:
        mid = model["module_id"]
        lines.append(f"{{{mid}u,{model['version']}u,{len(model['sections'])}u,{model['table_offset']}u,{model['file_size']}u,sections_{mid}}},")
    lines.append("};")
    lines.append(f"const u32 wario_rel_module_count = {len(models)}u;")
    return "\n".join(lines) + "\n"
