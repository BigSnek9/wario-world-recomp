"""Independent model of the four relocation kinds present in the pinned game.

This constructs expected section bytes for verification; it never writes guest
memory or original files. Unsupported kinds fail explicitly.
"""
import struct


def be32(data, offset):
    return struct.unpack_from(">I", data, offset)[0]


def parse(data):
    module_id, count, table = (be32(data, x) for x in (0, 12, 16))
    sections = []
    for index in range(count):
        raw, size = struct.unpack_from(">II", data, table + index * 8)
        offset = raw & ~3
        if offset and offset + size > len(data):
            raise ValueError("Section exceeds REL file")
        sections.append(dict(index=index, offset=offset, size=size, executable=bool(raw & 1),
                             bytes=data[offset:offset + size] if offset else bytes(size)))
    records = []
    imports, size = be32(data, 0x28), be32(data, 0x2c)
    if size % 8:
        raise ValueError("Invalid import table size")
    for entry in range(imports, imports + size, 8):
        target_module, cursor = struct.unpack_from(">II", data, entry)
        write_section, write_offset = None, 0
        while True:
            delta, kind, target_section, addend = struct.unpack_from(">HBBI", data, cursor)
            cursor += 8
            if kind == 203:
                break
            if kind == 202:
                if target_section >= count:
                    raise ValueError("Invalid relocation write section")
                write_section, write_offset = target_section, 0
                continue
            write_offset += delta
            if kind == 201:
                continue
            if kind not in (1, 4, 6, 10):
                raise ValueError(f"Unsupported relocation type {kind}")
            width = 2 if kind in (4, 6) else 4
            if write_section is None or write_offset + width > sections[write_section]["size"]:
                raise ValueError("Relocation write exceeds section")
            records.append(dict(section=write_section, offset=write_offset, kind=kind,
                                target_module=target_module, target_section=target_section, addend=addend))
    return dict(module_id=module_id, version=be32(data, 28), table_offset=table,
                file_size=len(data), sections=sections, records=records)


def apply(model, addresses):
    """addresses maps module IDs to original-section-index -> actual base address."""
    output = [bytearray(section["bytes"]) for section in model["sections"]]
    for record in model["records"]:
        module, section, addend = (record[k] for k in ("target_module", "target_section", "addend"))
        symbol = addend if module == 0 else (addresses[module][section] + addend) & 0xffffffff
        destination = output[record["section"]]
        offset, kind = record["offset"], record["kind"]
        if kind == 1:
            struct.pack_into(">I", destination, offset, symbol)
        elif kind == 4:
            struct.pack_into(">H", destination, offset, symbol & 0xffff)
        elif kind == 6:
            struct.pack_into(">H", destination, offset, ((symbol + 0x8000) >> 16) & 0xffff)
        else:
            place = addresses[model["module_id"]][record["section"]] + offset
            displacement = symbol - place
            if displacement % 4 or not -0x2000000 <= displacement < 0x2000000:
                raise ValueError("REL24 target out of range or unaligned")
            original = be32(destination, offset)
            struct.pack_into(">I", destination, offset, (original & ~0x03fffffc) | (displacement & 0x03fffffc))
    return output
