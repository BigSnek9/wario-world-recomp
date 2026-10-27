"""Draw the launcher's own file icon: an original gold coin with a bold "W" (simple shapes only).

The exe ships before any disc is read, so its embedded icon cannot come from the game. This is a
drawing made from circles and line strokes (no game or Nintendo art). After the first run the game
window uses the coin texture from the player's own disc instead (release/coin_icon.py).
Pure Python; CMake runs it at build time and embeds the .ico in WarioWorldRecomp.exe.

    python release/launcher/make_exe_icon.py --out build/WarioWorldRecomp.ico [--preview icon.png]
"""
import argparse
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from coin_icon import ICON_SIZES, ico_bytes, png_bytes, preview_strip  # noqa: E402

# Unit square coordinates, y down.
CENTRE = 0.5
OUTER = 0.48        # coin edge
RIM_IN = 0.405      # inner edge of the raised rim
GROOVE = 0.385      # thin dark groove inside the rim
W_POINTS = ((0.255, 0.335), (0.355, 0.665), (0.5, 0.42), (0.645, 0.665), (0.745, 0.335))


def mix(a, b, t):
    t = min(1.0, max(0.0, t))
    return tuple(x + (y - x) * t for x, y in zip(a, b))


def segment_distance(px, py, ax, ay, bx, by):
    vx, vy, wx, wy = bx - ax, by - ay, px - ax, py - ay
    t = max(0.0, min(1.0, (wx * vx + wy * vy) / (vx * vx + vy * vy)))
    dx, dy = wx - vx * t, wy - vy * t
    return math.sqrt(dx * dx + dy * dy)


def w_distance(x, y):
    return min(segment_distance(x, y, *W_POINTS[i], *W_POINTS[i + 1]) for i in range(len(W_POINTS) - 1))


def shade(x, y, size):
    """Straight RGBA (floats 0..1) of the drawing at unit position (x, y)."""
    dx, dy = x - CENTRE, y - CENTRE
    r = math.sqrt(dx * dx + dy * dy)
    if r > OUTER:
        return (0.0, 0.0, 0.0, 0.0)
    light = (-dx - dy) / (2 * OUTER)  # -0.7 .. 0.7, brighter towards the top left
    face = mix((0.80, 0.52, 0.04), (1.0, 0.86, 0.30), 0.5 + light)
    if r > RIM_IN:  # raised rim: lit on the top left, shadowed on the bottom right
        colour = mix((0.62, 0.36, 0.0), (1.0, 0.93, 0.55), 0.5 + 1.2 * light)
    elif r > GROOVE:
        colour = mix((0.55, 0.30, 0.0), (0.75, 0.48, 0.05), 0.5 + light)
    else:
        colour = face
    # Bold W, a little thicker at small sizes so it stays readable: a dark stamped letter with a
    # light lower-right edge (pressed into the coin).
    half = 0.066 + 0.5 / size
    if r <= GROOVE:
        if w_distance(x - 0.010, y - 0.013) < half:
            colour = mix(colour, (1.0, 0.95, 0.65), 0.7)
        if w_distance(x, y) < half:
            colour = mix((0.42, 0.22, 0.0), (0.66, 0.38, 0.02), 0.5 + light)
    return colour + (1.0,)


def render(size, samples=4):
    image = []
    for oy in range(size):
        row = []
        for ox in range(size):
            r = g = b = a = 0.0
            for sy in range(samples):
                for sx in range(samples):
                    cr, cg, cb, ca = shade((ox + (sx + 0.5) / samples) / size,
                                           (oy + (sy + 0.5) / samples) / size, size)
                    r += cr * ca
                    g += cg * ca
                    b += cb * ca
                    a += ca
            n = samples * samples
            if a == 0.0:
                row.append((0, 0, 0, 0))
            else:
                row.append(tuple(min(255, int(c / a * 255 + 0.5)) for c in (r, g, b)) + (int(a / n * 255 + 0.5),))
        image.append(row)
    return image


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--preview", type=Path, help="also write a PNG with every size")
    args = parser.parse_args()
    images = [render(size) for size in ICON_SIZES]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(ico_bytes(images))
    if args.preview:
        args.preview.write_bytes(png_bytes(preview_strip(images, (40, 40, 48, 255))))


if __name__ == "__main__":
    main()
