"""Extract every texture from the Wario World (GWWE01) disc as HD-loader-ready PNGs.

Disc format findings (all big-endian, archives in files/rsc/*.RSC are not
compressed):
- A texture bank starts at a 4-byte aligned offset B with the u32 magic
  0x0020AF30, then u32 count n, then n pairs of u32 (a, rec_off). The first
  pair's `a` is always 0x0C, the rest 0. Record i lives at B + rec_off; the
  records are contiguous, 0x24 bytes each:
    +0x00 u16 width, +0x02 u16 height
    +0x04 u32 GX texture format (0 I4, 1 I8, 2 IA4, 3 IA8, 4 RGB565, 5 RGB5A3,
          6 RGBA8, 8 C4, 9 C8, 10 C14X2, 14 CMPR)
    +0x08 u32 pixel data offset, relative to the bank start B
    +0x0C wrapS, +0x10 wrapT
    +0x14 min filter (GX: 0 near, 1 linear, 2..5 mipmapped modes), +0x18 mag
    +0x1C u32 always 0 on this disc
    +0x20 u32 max LOD in 8.8 fixed point (0x700 = 7.0 -> 8 levels; 0 when the
          min filter has no mipmaps)
  (An earlier guess read the record 4 bytes too early - the "flags" word is
  really the max LOD of the *previous* record.) All 345 magic hits in rsc/
  are real banks, 2037 records; the disc uses no paletted formats (no TLUTs
  appear anywhere), but C4/C8/C14X2 are still handled if a palette offset is
  ever found (they are reported and skipped, since the bank holds no TLUT).
- Pixel data is GameCube tiled: I4/C4/CMPR 8x8 blocks, I8/IA4/C8 8x4, the
  16-bit formats 4x4 (32 bytes per block), RGBA8 4x4 with 64 bytes (AR tile
  then GB tile). Mip levels follow the base level; only the base is exported.

HD texture names (Dolphin TextureInfo, which the runtime uses):
  tex1_{w}x{h}{_m}_{xxh64(base level, seed 0):016x}_{format}.png
  `_m` is present when the sampler's min filter uses mipmaps (min filter 2..5;
  Dolphin: texMode0.mipmap_filter != None). The hashed byte count is the
  tiled base-level size with width/height rounded up to whole blocks.
Decoding mirrors Dolphin's generic decoder (bit expansion, the 3/8 CMPR
blend, RGB5A3 3-bit alpha) so pixels match the runtime's own dumps.

Command line:
  python scripts/extract_textures.py --game original/GWWE01 --out private/texture-extract
  python scripts/extract_textures.py --game original/GWWE01 --out private/texture-extract-test --verify private/texture-test-out
"""
import argparse
import csv
import re
import struct
import sys
import time
from pathlib import Path

import numpy as np
import xxhash
from PIL import Image

MAGIC = b"\x00\x20\xaf\x30"
FORMATS = {0: "I4", 1: "I8", 2: "IA4", 3: "IA8", 4: "RGB565", 5: "RGB5A3", 6: "RGBA8",
           8: "C4", 9: "C8", 10: "C14X2", 14: "CMPR"}
# format -> (block width, block height, bytes per block)
BLOCKS = {0: (8, 8, 32), 1: (8, 4, 32), 2: (8, 4, 32), 3: (4, 4, 32), 4: (4, 4, 32),
          5: (4, 4, 32), 6: (4, 4, 64), 8: (8, 8, 32), 9: (8, 4, 32), 10: (4, 4, 32),
          14: (8, 8, 32)}
PALETTED = {8, 9, 10}

# Same area naming as texture_tools.area_for (kept local so this script stands alone).
WORLDS = {"1": "World1 Excitement Central", "2": "World2 Spooktastic World",
          "4": "World3 Thrillsville", "5": "World4 Sparkle Land"}
KINDS = {"F": "Stage", "B": "Boss", "P": "Area P", "R": "Area R"}
SPECIAL = {"TT": "00 Title", "OP": "01 Opening", "PF": "02 Hub", "UNIV": "03 Shared (UNIV)",
           "ED": "99 Ending", "BOSS": "04 Shared bosses", "IGNITE": "05 IGNITE", "UGP": "06 UGP",
           "UGR": "06 UGR", "MAIN": "07 Main program (main.dol)"}
# Archive priority for deduplication: shared/front-end first, then worlds in play order.
ORDER = ["UNIV", "TT", "OP", "PF", "BOSS", "IGNITE", "UGP", "UGR"]
KIND_ORDER = "FPRB"


def area_for(archive):
    """'AF12.RSC' -> 'World1 Excitement Central/Stage F12'."""
    stem = Path(archive).stem.upper()
    code = stem[1:] if stem[:1] in "AC" and len(stem) > 1 else stem
    if code in SPECIAL:
        return SPECIAL[code]
    match = re.fullmatch(r"([A-Z])(\d)(\d)", code)
    if match and match.group(2) in WORLDS:
        kind = KINDS.get(match.group(1), "Area " + match.group(1))
        return f"{WORLDS[match.group(2)]}/{kind} {code}"
    return "Other " + code


def archive_sort_key(path):
    stem = path.stem.upper()
    code = stem[1:] if stem[:1] in "AC" and len(stem) > 1 else stem
    if code in ORDER:
        rank = (0, ORDER.index(code), 0, 0)
    elif code == "ED":
        rank = (3, 0, 0, 0)
    else:
        match = re.fullmatch(r"([A-Z])(\d)(\d)", code)
        if match:
            rank = (1, int(match.group(2)), int(match.group(3)),
                    KIND_ORDER.find(match.group(1)) % 10)
        else:
            rank = (2, 0, 0, 0)
    in_rsc = 0 if path.parent.name.lower() == "rsc" else 1
    return (in_rsc, rank, stem[:1] != "A", stem)


def texture_size(fmt, w, h):
    bw, bh, bb = BLOCKS[fmt]
    return -(-w // bw) * -(-h // bh) * bb


# ---------------------------------------------------------------- decoding

def _untile(blocks, w, h, bw, bh):
    """blocks: (nby*nbx, bh, bw, C) in block order -> (h, w, C) image."""
    nbx, nby = -(-w // bw), -(-h // bh)
    img = blocks.reshape(nby, nbx, bh, bw, -1).transpose(0, 2, 1, 3, 4)
    return img.reshape(nby * bh, nbx * bw, -1)[:h, :w]


def _c5(v):
    return ((v << 3) | (v >> 2)).astype(np.uint8)


def _c6(v):
    return ((v << 2) | (v >> 4)).astype(np.uint8)


def _c4(v):
    return (v * 17).astype(np.uint8)


def _c3(v):
    return ((v << 5) | (v << 2) | (v >> 1)).astype(np.uint8)


def _rgb565(v):
    return np.stack([_c5((v >> 11) & 31), _c6((v >> 5) & 63), _c5(v & 31),
                     np.full(v.shape, 255, np.uint8)], -1)


def _rgb5a3(v):
    opaque = (v & 0x8000) != 0
    r = np.where(opaque, _c5((v >> 10) & 31), _c4((v >> 8) & 15))
    g = np.where(opaque, _c5((v >> 5) & 31), _c4((v >> 4) & 15))
    b = np.where(opaque, _c5(v & 31), _c4(v & 15))
    a = np.where(opaque, 255, _c3((v >> 12) & 7))
    return np.stack([r, g, b, a], -1).astype(np.uint8)


def _ia8(v):
    i, a = (v & 0xFF).astype(np.uint8), (v >> 8).astype(np.uint8)
    return np.stack([i, i, i, a], -1)


def _palette(tlut, tlut_fmt):
    v = np.frombuffer(tlut, ">u2").astype(np.uint32)
    return {0: _ia8, 1: _rgb565, 2: _rgb5a3}[tlut_fmt](v)


def decode(fmt, w, h, data, tlut=None, tlut_fmt=0):
    """Decode one base level to an (h, w, 4) uint8 RGBA array."""
    bw, bh, bb = BLOCKS[fmt]
    nblocks = -(-w // bw) * -(-h // bh)
    raw = np.frombuffer(data, np.uint8, nblocks * bb).reshape(nblocks, bb)
    if fmt in (0, 8):  # I4 / C4: nibbles, high first
        px = np.stack([raw >> 4, raw & 15], -1).reshape(nblocks, bh, bw)
        if fmt == 0:
            i = _c4(px)
            return _untile(np.stack([i, i, i, i], -1), w, h, bw, bh)
        return _untile(_palette(tlut, tlut_fmt)[px], w, h, bw, bh)
    if fmt in (1, 9):  # I8 / C8
        px = raw.reshape(nblocks, bh, bw)
        if fmt == 1:
            return _untile(np.stack([px] * 4, -1), w, h, bw, bh)
        return _untile(_palette(tlut, tlut_fmt)[px], w, h, bw, bh)
    if fmt == 2:  # IA4: high nibble alpha, low intensity
        px = raw.reshape(nblocks, bh, bw)
        i, a = _c4(px & 15), _c4(px >> 4)
        return _untile(np.stack([i, i, i, a], -1), w, h, bw, bh)
    if fmt in (3, 4, 5, 10):
        v = raw.view(">u2").astype(np.uint32).reshape(nblocks, bh, bw)
        if fmt == 3:
            rgba = _ia8(v)
        elif fmt == 4:
            rgba = _rgb565(v)
        elif fmt == 5:
            rgba = _rgb5a3(v)
        else:
            rgba = _palette(tlut, tlut_fmt)[v & 0x3FFF]
        return _untile(rgba, w, h, bw, bh)
    if fmt == 6:  # RGBA8: 32 bytes AR pairs then 32 bytes GB pairs
        ar, gb = raw[:, :32].reshape(nblocks, 16, 2), raw[:, 32:].reshape(nblocks, 16, 2)
        rgba = np.stack([ar[..., 1], gb[..., 0], gb[..., 1], ar[..., 0]], -1)
        return _untile(rgba.reshape(nblocks, 4, 4, 4), w, h, bw, bh)
    if fmt == 14:  # CMPR: 8x8 block = 2x2 DXT1 sub-blocks
        sub = raw.reshape(nblocks * 4, 8)
        c = sub[:, :4].copy().view(">u2").astype(np.int32)
        c1, c2 = c[:, 0], c[:, 1]
        col1 = np.stack([_c5((c1 >> 11) & 31), _c6((c1 >> 5) & 63), _c5(c1 & 31)], -1).astype(np.int32)
        col2 = np.stack([_c5((c2 >> 11) & 31), _c6((c2 >> 5) & 63), _c5(c2 & 31)], -1).astype(np.int32)
        gt = (c1 > c2)[:, None]
        col3 = np.where(gt, (col2 * 3 + col1 * 5) >> 3, (col1 + col2) // 2)
        col4 = np.where(gt, (col1 * 3 + col2 * 5) >> 3, (col1 + col2) // 2)
        pal = np.zeros((len(sub), 4, 4), np.uint8)
        pal[:, 0, :3], pal[:, 1, :3], pal[:, 2, :3], pal[:, 3, :3] = col1, col2, col3, col4
        pal[:, :3, 3] = 255
        pal[:, 3, 3] = np.where(gt[:, 0], 255, 0)
        lines = sub[:, 4:8]
        idx = np.stack([(lines >> s) & 3 for s in (6, 4, 2, 0)], -1)  # (n, 4 rows, 4 cols)
        px = pal[np.arange(len(sub))[:, None, None], idx]  # (n, 4, 4, 4)
        px = px.reshape(nblocks, 2, 2, 4, 4, 4).transpose(0, 1, 3, 2, 4, 5).reshape(nblocks, 8, 8, 4)
        return _untile(px, w, h, bw, bh)
    raise ValueError(f"unsupported format {fmt}")


def tlut_range_hash(fmt, data, tlut):
    """Dolphin hashes only the used palette range (including its C14X2 quirk)."""
    arr = np.frombuffer(data, np.uint8)
    if fmt == 8:
        vals = np.concatenate([arr >> 4, arr & 15])
    elif fmt == 9:
        vals = arr
    else:  # Dolphin swaps a single byte here, so only the even byte's low 6 bits count
        vals = (arr[0::2].astype(np.uint32) << 8) & 0x3FFF
    lo, hi = int(vals.min()), int(vals.max())
    return xxhash.xxh64(tlut[2 * lo:2 * (hi + 1)], seed=0).hexdigest()


# ---------------------------------------------------------------- parsing

def find_banks(data):
    """Yield (bank_offset, [record dicts]) for every valid texture bank."""
    size = len(data)
    pos = data.find(MAGIC)
    while pos >= 0:
        bank = pos
        pos = data.find(MAGIC, pos + 1)
        if bank % 4 or bank + 8 > size:
            continue
        count = struct.unpack_from(">I", data, bank + 4)[0]
        if not 0 < count < 10000 or bank + 8 + count * 8 > size:
            continue
        records = []
        for k in range(count):
            first, rec_off = struct.unpack_from(">II", data, bank + 8 + k * 8)
            rec = bank + rec_off
            if first != (0x0C if k == 0 else 0) or rec + 0x24 > size:
                break
            h, w, fmt, off, wrap_s, wrap_t, min_f, mag_f, _zero, max_lod = \
                struct.unpack_from(">HHIIIIIIII", data, rec)
            if fmt not in BLOCKS or not (0 < w <= 1024 and 0 < h <= 1024) or min_f > 5:
                break
            start = bank + off
            if start + texture_size(fmt, w, h) > size:
                break
            records.append(dict(record=rec, width=w, height=h, fmt=fmt, data=start,
                                min_filter=min_f, mag_filter=mag_f, wrap=(wrap_s, wrap_t),
                                max_lod=max_lod))
        else:
            yield bank, records


def texture_name(rec, base, tlut_hash=None):
    mips = "_m" if rec["min_filter"] >= 2 else ""
    tl = f"_{tlut_hash}" if tlut_hash else ""
    h = xxhash.xxh64(base, seed=0).hexdigest()
    return f"tex1_{rec['width']}x{rec['height']}{mips}_{h}{tl}_{rec['fmt']}.png"


def archives(game):
    game = Path(game)
    found = [p for p in (game / "files").rglob("*") if p.is_file()]
    found += sorted((game / "sys").glob("*.dol"))
    return sorted(found, key=archive_sort_key)


README = """Wario World (GWWE01) - every texture on the disc ({total} unique)

Extracted straight from the disc archives by scripts/extract_textures.py,
sorted into one folder per area (the archive a texture first appears in;
manifest.csv lists every archive that contains it).

Upscaling / replacing:
- Do NOT rename files. The name (size, hash, format) is how the game finds
  the replacement; a renamed file is silently ignored.
- Upscale by a whole factor (2x, 4x, ...) keeping the aspect ratio.
- Keep the alpha channel (transparent pixels must stay transparent).
- Names with "_m" are mipmapped; the runtime builds the smaller levels
  itself from your upscaled image.
- Put the results (any subfolders are fine, this tree can be copied as is) in
  Recomp/private/playtest-user/Load/Textures/GWWE01/
  and enable HD textures (texture_tools / launcher HD mode).
- You only need to ship the textures you changed.
"""


def extract(game, out_dir, log=print):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    entries, stats = {}, {"banks": 0, "records": 0, "skipped": 0}
    for path in archives(game):
        data = path.read_bytes()
        if MAGIC not in data:
            continue
        rel = path.relative_to(Path(game)).as_posix()
        for bank, records in find_banks(data):
            stats["banks"] += 1
            for rec in records:
                stats["records"] += 1
                if rec["fmt"] in PALETTED:  # no TLUT stored in the bank on this disc
                    stats["skipped"] += 1
                    log(f"  skip paletted texture at {rel}:{rec['record']:#x} (no TLUT)")
                    continue
                base = data[rec["data"]:rec["data"] + texture_size(rec["fmt"], rec["width"], rec["height"])]
                name = texture_name(rec, base)
                entry = entries.get(name)
                if entry:
                    if path.name not in entry["archives"]:
                        entry["archives"].append(path.name)
                    continue
                area = area_for(path.name)
                folder = out_dir / area
                folder.mkdir(parents=True, exist_ok=True)
                rgba = decode(rec["fmt"], rec["width"], rec["height"], base)
                Image.fromarray(np.ascontiguousarray(rgba), "RGBA").save(folder / name, compress_level=6)
                entries[name] = dict(file=name, area=area, archives=[path.name], width=rec["width"],
                                     height=rec["height"], format=FORMATS[rec["fmt"]],
                                     mipmaps="yes" if rec["min_filter"] >= 2 else "no",
                                     source=f"{rel}:{rec['data']:#x}")
        log(f"{rel}: {len(entries)} unique so far")
    with (out_dir / "manifest.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["file", "area", "archives", "width", "height", "format", "mipmaps", "source"])
        for e in sorted(entries.values(), key=lambda e: (e["area"], e["file"])):
            writer.writerow([e["file"], e["area"], " ".join(e["archives"]), e["width"], e["height"],
                             e["format"], e["mipmaps"], e["source"]])
    (out_dir / "README.txt").write_text(README.format(total=len(entries)), encoding="utf-8")
    return entries, stats


def verify(entries, out_dir, reference, sample=40):
    reference = Path(reference)
    refs = {p.name: p for p in reference.rglob("tex1_*.png")}
    produced = [n for n in refs if n in entries]
    missing = sorted(set(refs) - set(produced))
    print(f"verify: {len(produced)}/{len(refs)} reference names produced")
    for name in missing:
        print("  missing:", name)
    step = max(1, len(produced) // sample)
    checked, exact, worst = 0, 0, 0
    for name in sorted(produced)[::step]:
        mine = np.asarray(Image.open(Path(out_dir) / entries[name]["area"] / name).convert("RGBA"), np.int16)
        ref = np.asarray(Image.open(refs[name]).convert("RGBA"), np.int16)
        checked += 1
        if mine.shape != ref.shape:
            print(f"  size mismatch {name}: {mine.shape} vs {ref.shape}")
            worst = 255
            continue
        diff = int(np.abs(mine - ref).max())
        exact += diff == 0
        worst = max(worst, diff)
        if diff:
            print(f"  pixel diff {name}: max {diff}")
    print(f"verify: pixel-compared {checked}, identical {exact}, worst channel diff {worst}")
    return not missing and worst == 0


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--game", default="original/GWWE01", help="extracted disc folder (contains files/)")
    parser.add_argument("--out", required=True, help="output folder (keep it under private/)")
    parser.add_argument("--verify", help="folder of runtime-dumped reference textures to compare against")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    started = time.time()
    entries, stats = extract(args.game, args.out, log=(lambda *_: None) if args.quiet else print)
    counts = {}
    for e in entries.values():
        counts[e["format"]] = counts.get(e["format"], 0) + 1
    print(f"{stats['banks']} banks, {stats['records']} records, {len(entries)} unique textures "
          f"({stats['skipped']} skipped) in {time.time() - started:.1f}s")
    print("formats:", ", ".join(f"{k} {v}" for k, v in sorted(counts.items(), key=lambda kv: -kv[1])))
    if args.verify:
        return 0 if verify(entries, args.out, args.verify) else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
