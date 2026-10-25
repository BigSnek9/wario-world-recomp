"""Classify private diagnostic screenshots against labeled references.

Read-only grayscale comparison of the banner text region. Prints a timeline of
each capture's nearest labeled state and distance; optional --csv output.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "private/runs"
REFERENCES = {
    "banner": RUNS / "20261025T125052430561Z/control/diagnostic.png",
    "create": RUNS / "20261025T125921154456Z/control/diagnostic-05.png",
    "cannot_save": RUNS / "20261025T130337737328Z/control/diagnostic-09.png",
    "press_start": RUNS / "20261025T130337737328Z/control/diagnostic-14.png",
}


def banner_thumb(path: Path) -> np.ndarray:
    image = Image.open(path).convert("L")
    width, height = image.size
    # Tight crop of the two text lines inside the parchment banner.
    box = (int(width * 0.26), int(height * 0.165), int(width * 0.74), int(height * 0.265))
    crop = image.crop(box).resize((128, 24))
    return np.asarray(crop, dtype=np.float64).ravel()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", type=Path, help="Directory containing diagnostic-*.png captures")
    parser.add_argument("--csv", type=Path)
    args = parser.parse_args()
    refs = {name: banner_thumb(path) for name, path in REFERENCES.items() if path.is_file()}
    rows = []
    for capture in sorted(args.target.glob("diagnostic-*.png")):
        thumb = banner_thumb(capture)
        distances = {name: float(np.mean(np.abs(thumb - ref))) for name, ref in refs.items()}
        state = min(distances, key=distances.get)
        rows.append((capture.name, state, round(distances[state], 2),
                     {k: round(v, 1) for k, v in distances.items()}))
    for name, state, distance, all_distances in rows:
        print(f"{name}  {state:12s}  d={distance:6.2f}  {all_distances}")
    if args.csv:
        args.csv.write_text("\n".join(f"{n},{s},{d}" for n, s, d, _ in rows), encoding="utf-8")


if __name__ == "__main__":
    main()
