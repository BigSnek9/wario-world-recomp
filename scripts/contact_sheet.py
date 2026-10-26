"""Tile a run's private diagnostic screenshots into one labelled contact sheet.

Usage: python scripts/contact_sheet.py <run-dir> [--cols 4] [--width 320] [--out path]
The sheet is written beside the captures (private) unless --out is given.
"""
import argparse
from pathlib import Path

from PIL import Image, ImageDraw


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--cols", type=int, default=4)
    parser.add_argument("--width", type=int, default=320)
    parser.add_argument("--glob", default="diagnostic-*.png")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    control = args.run_dir / "control"
    folder = control if control.is_dir() else args.run_dir
    images = sorted(folder.glob(args.glob))
    if not images:
        print(f"no images matching {args.glob} in {folder}")
        return 1
    tiles = []
    for path in images:
        image = Image.open(path).convert("RGB")
        height = round(image.height * args.width / image.width)
        tiles.append((path.stem, image.resize((args.width, height))))
    tile_h = max(t.height for _, t in tiles)
    rows = (len(tiles) + args.cols - 1) // args.cols
    sheet = Image.new("RGB", (args.cols * args.width, rows * tile_h), "black")
    draw = ImageDraw.Draw(sheet)
    for index, (name, tile) in enumerate(tiles):
        x, y = (index % args.cols) * args.width, (index // args.cols) * tile_h
        sheet.paste(tile, (x, y))
        draw.rectangle((x, y, x + 8 * len(name) + 4, y + 14), fill="black")
        draw.text((x + 2, y + 1), name, fill="yellow")
    out = args.out or folder / "contact-sheet.png"
    sheet.save(out)
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
