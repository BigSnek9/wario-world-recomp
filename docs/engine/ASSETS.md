# Disc assets: RSC archives and texture banks

Confirmed 2026-10-26 (scripts/extract_textures.py; docstring has full detail).

- `files/rsc/*.RSC` (70 archives, uncompressed, big-endian). Name = A/C prefix
  + code: Fnn stage, Bnn boss, Pnn / Rnn other area kinds, TT title, OP opening,
  PF hub, ED ending, UNIV shared, BOSS shared boss data, IGNITE, UGP, UGR.
  World digits on disc are 1, 2, 4, 5 (= worlds 1-4).
- Texture bank: 4-byte aligned magic 0x0020AF30, u32 count n, n pairs
  (a, rec_off) (a = 0x0C for the first pair, else 0); records at bank+rec_off,
  0x24 bytes each: +0x00 u16 height, +0x02 u16 width, +0x04 u32 GX format,
  +0x08 u32 data offset (bank-relative), +0x0C wrapS, +0x10 wrapT,
  +0x14 min filter (1 or 5 seen), +0x18 mag filter, +0x1C 0,
  +0x20 max LOD 8.8 fixed (0x700 = 7.0; 0 when not mipmapped).
- Data is raw GX tiled texture data, base level first, mips following.
- 345 banks in rsc/ + 2 in sys/main.dol; 2,040 records; 1,701 unique textures:
  CMPR 1494, RGB5A3 78, I4 75, I8 19, IA8 16, RGBA8 12, IA4 7. No paletted
  textures on the disc.
- HD loader names are reproducible offline:
  `tex1_{w}x{h}[_m]_{xxh64(base level)}_{fmt}` with `_m` when min filter is 2..5.
  Verified: 196/204 runtime-dumped names reproduced, all pixel-identical; the
  other 8 are generated at run time (font-rendered menu text, a procedural
  gradient) and are not on the disc.
