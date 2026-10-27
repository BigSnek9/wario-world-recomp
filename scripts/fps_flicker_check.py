"""Hidden flicker check for FPS interpolation (docs/modding/FPS_UNLOCK.md).

Runs a scene with the dump option, then for every (real N-1, in-between, real N) triple counts
"blob" outliers: pixels of the in-between frame far outside both neighbours, after a 3x3 erosion
so thin texture edges (sub-pixel foliage shimmer) do not count. Whole objects drawn in the wrong
place survive the erosion. Compare --objects against camera-only (which cannot flicker).

Usage: python scripts/fps_flicker_check.py --scene boss [--objects] [--module DLL] [--seconds 40]
"""
import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from fps_matrix import SCENES  # noqa: E402


def erode(mask):
    out = mask.copy()
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            out &= np.roll(np.roll(mask, dy, 0), dx, 1)
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene", default="boss", choices=sorted(SCENES))
    parser.add_argument("--objects", action="store_true")
    parser.add_argument("--module", default=str(ROOT / "build/module-full-vectors-clang-pgo/gGWWE01_recomp.dll"))
    parser.add_argument("--seconds", type=int, default=40)
    parser.add_argument("--runner", default=str(ROOT / "build/moderngekko-prof/RelWithDebInfo/moderngekko-run.exe"))
    args = parser.parse_args()
    label = f"{args.scene}-{'objects' if args.objects else 'camera'}"
    dump = ROOT / f"private/fps-flicker/{label}"
    if dump.exists():
        for old in dump.glob("*.png"):
            old.unlink()
    dump.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, MODERNGEKKO_WARIO_FPS="2", MODERNGEKKO_WARIO_FPS_DUMP=str(dump),
               MODERNGEKKO_WARIO_FPS_OBJECTS="1" if args.objects else "0")
    output = subprocess.run([sys.executable, str(ROOT / "scripts/smoke_boot.py"), "--module", args.module, "--full",
                             "--vectors", "--seconds", str(args.seconds), *map(str, SCENES[args.scene]),
                             "--graphics", "OpenGL", "--runner", args.runner],
                            capture_output=True, text=True, env=env).stdout
    run = re.search(r"Diagnostic output: (.+)", output)
    scores = []
    for real in sorted(dump.glob("real_*.png")):
        n = int(real.stem[5:])
        mid, after = dump / f"mid_{n + 1:08}.png", dump / f"real_{n + 1:08}.png"
        if not (mid.exists() and after.exists()):
            continue
        a, m, b = (np.asarray(Image.open(p).convert("L"), dtype=np.int16) for p in (real, mid, after))
        mask = (m < np.minimum(a, b) - 40) | (m > np.maximum(a, b) + 40)
        scores.append((round(float(erode(mask).mean() * 100), 3), n))
    worst = sorted(scores, reverse=True)[:3]
    print(f"{label}: run={run.group(1).strip() if run else None} triples={len(scores)} "
          f"blob%_mean={np.mean([s for s, _ in scores]) if scores else 0:.3f} worst={worst}")


if __name__ == "__main__":
    main()
