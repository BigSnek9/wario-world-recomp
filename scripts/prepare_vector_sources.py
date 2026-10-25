"""Statically compile SDK-installed vectors derived from the pinned original DOL.

These are private derived inputs; actual game memory and original files are
never modified. Code-byte guards must verify the installed copies at runtime.
"""
from pathlib import Path
import json
import struct
import subprocess
from audit_game import parse_dol
from build import check_game

ROOT = Path(__file__).resolve().parents[1]


def vector_images(dol):
    sections = parse_dol(dol)["sections"]
    def original(address, size):
        section = next(s for s in sections if s["address"] <= address and address + size <= s["address"] + s["size"])
        offset = section["offset"] + address - section["address"]
        return dol[offset:offset + size]
    template = original(0x8019CFE4, 0x98)
    if struct.unpack_from(">I", template, 0x68)[0] != 0x38600000:
        raise ValueError("Unexpected OSExceptionVector ID instruction")
    images = []
    vectors = (0x100,0x200,0x300,0x400,0x500,0x600,0x700,0x800,0x900,0xc00,0xd00,0xf00,0x1300,0x1400,0x1700)
    for index, address in enumerate(vectors):
        if address == 0xc00:
            code = original(0x801A2EB4, 0x1c)
        else:
            code = bytearray(template)
            struct.pack_into(">I", code, 0x68, 0x38600000 | index)
        images.append((f"vector_{address:04x}", address, bytes(code)))
    images.append(("config24mb_physical", 0x001A146C, original(0x801A146C, 0x80)))
    return images


def write_changed(path, data):
    if not path.is_file() or path.read_bytes() != data:
        path.write_bytes(data)


def prepare():
    check_game()
    dol = (ROOT / "original/GWWE01/sys/main.dol").read_bytes()
    out = ROOT / "generated/vector-sources"
    out.mkdir(parents=True, exist_ok=True)
    compiler = ROOT / "build/moderngekko/Release/dolrecomp.exe"
    manifest = []
    with (ROOT / "reports/translate-vectors.log").open("w") as log:
        for name, address, code in vector_images(dol):
            folder = out / name
            folder.mkdir(exist_ok=True)
            header = bytearray(0x100)
            for offset, value in ((0,0x100),(0x48,address),(0x90,len(code)),(0xe0,address)):
                struct.pack_into(">I", header, offset, value)
            image = folder / "derived.dol"
            write_changed(image, bytes(header) + code)
            subprocess.run([compiler,"--gamecube","--cpu","gekko","--backend","c","--semantics","exact","-j1",image,folder],
                           check=True, stdout=log, stderr=subprocess.STDOUT)
            manifest.append(dict(name=name,address=address,size=len(code)))
    (out / "manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print("Compiled SDK vector/startup images:",len(manifest),flush=True)


if __name__ == "__main__":
    prepare()
