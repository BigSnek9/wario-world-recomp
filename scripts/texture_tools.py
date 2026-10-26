"""Texture dump / organize / HD-load helpers for the playtest profile.

How it works
- Dump mode turns on the runtime's texture dumper (environment variable
  MODERNGEKKO_DUMP_TEXTURES=1 at launch - Dolphin forces the GFX.ini
  DumpTextures setting off on every start) and the
  disc file monitor log (Logger.ini FileMon -> User/Logs/dolphin.log). Each
  texture is written once, the first time the game uses it, as
  User/Dump/Textures/GWWE01/tex1_<w>x<h>_<hash>..._<fmt>.png - exactly the name
  the HD loader looks for, so upscaled copies with the same names load back in.
- organize() sorts newly dumped files into <out>/<area>/ using the disc log:
  a texture belongs to the stage archive (.RSC) most recently read before the
  texture file appeared. Files keep their names; the loader searches folders
  recursively, so the tidy tree can be copied straight into the HD folder.
- HD mode (GFX.ini HiresTextures) loads PNGs from
  User/Load/Textures/GWWE01/ (any subfolders).

Areas are named from the archive codes on the disc (rsc/*.RSC). Area names
in AREA_NAMES are best guesses from the file names; see the README written
into the output folder. Textures first seen in title/menus land in their own
areas. Command line:
  python scripts/texture_tools.py organize --user-dir private/playtest-user --out "../Texture Dump" --since <unix-time>
"""
import argparse
import configparser
import csv
import os
import re
import shutil
import time
from datetime import datetime
from pathlib import Path

GAME_ID = "GWWE01"
FORMATS = {0: "I4", 1: "I8", 2: "IA4", 3: "IA8", 4: "RGB565", 5: "RGB5A3", 6: "RGBA8",
           8: "C4", 9: "C8", 10: "C14X2", 14: "CMPR"}
# Archive code (without the leading A/C prefix) -> folder name. Worlds on the disc
# are numbered 1, 2, 4, 5. Names other than the code are best guesses.
WORLDS = {"1": "World1 Excitement Central", "2": "World2 Spooktastic World",
          "4": "World3 Thrillsville", "5": "World4 Sparkle Land"}
KINDS = {"F": "Stage", "B": "Boss", "P": "Area P", "R": "Area R"}
SPECIAL = {"TT": "00 Title", "OP": "01 Opening", "PF": "02 Hub", "UNIV": "03 Shared (UNIV)",
           "ED": "99 Ending", "BOSS": "04 Shared bosses", "IGNITE": "05 IGNITE", "UGP": "06 UGP", "UGR": "06 UGR"}
TEX_NAME = re.compile(r"^tex1_(\d+)x(\d+)_.*?_(\d+)(_mip\d+)?\.png$", re.I)
LOG_LINE = re.compile(r"^(\d+):(\d+):(\d+) .*?kB (\S+)")


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


def _ini(path):
    config = configparser.ConfigParser(interpolation=None, strict=False)
    config.optionxform = str
    if path.is_file():
        config.read(path, encoding="utf-8")
    return config


def _set(path, values):
    config = _ini(path)
    for section, items in values.items():
        if not config.has_section(section):
            config.add_section(section)
        for key, value in items.items():
            config.set(section, key, value)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as stream:
        config.write(stream)


def set_dump_mode(user_dir, enabled):
    user_dir = Path(user_dir)
    on = "True" if enabled else "False"
    _set(user_dir / "Config/GFX.ini", {"Settings": {"DumpTextures": on, "DumpMipTextures": "False"}})
    _set(user_dir / "Config/Logger.ini", {"Logs": {"FileMon": on},
                                           "Options": {"WriteToFile": on, "Verbosity": "3"}})
    # The file logger does not create its folder.
    (user_dir / "Logs").mkdir(parents=True, exist_ok=True)


def set_hd_mode(user_dir, enabled):
    _set(Path(user_dir) / "Config/GFX.ini",
         {"Settings": {"HiresTextures": "True" if enabled else "False", "CacheHiresTextures": "False"}})
    hd_folder(user_dir).mkdir(parents=True, exist_ok=True)


def start_session(user_dir):
    """Call just before launching in dump mode; returns the session start time.

    The log only stores minutes:seconds, so stale lines from older sessions
    would be misplaced - start each session with a fresh log."""
    log = Path(user_dir) / "Logs/dolphin.log"
    try:
        log.unlink()
    except FileNotFoundError:
        pass
    return time.time()


def dump_folder(user_dir):
    return Path(user_dir) / "Dump/Textures" / GAME_ID


def hd_folder(user_dir):
    return Path(user_dir) / "Load/Textures" / GAME_ID


def archive_events(user_dir, since):
    """[(unix_time, archive_name)] for .RSC reads in the disc log after `since`.

    Log lines carry only minutes:seconds:millis of wall-clock time; they are
    turned back into absolute times by walking forward from `since`."""
    log = Path(user_dir) / "Logs/dolphin.log"
    if not log.is_file():
        return []
    events, cursor = [], since
    for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
        match = LOG_LINE.match(line)
        if not match or not match.group(4).upper().endswith(".RSC"):
            continue
        minute, second, millis = int(match.group(1)), int(match.group(2)), int(match.group(3))
        base = datetime.fromtimestamp(cursor).replace(minute=minute, second=second, microsecond=millis * 1000).timestamp()
        while base < cursor - 1:  # minute wrapped into the next hour
            base += 3600
        cursor = base
        events.append((base, match.group(4).rsplit("/", 1)[-1]))
    return events


def organize(user_dir, out_dir, since=0.0):
    """Move newly dumped textures into <out_dir>/<area>/ and update manifest.csv.

    Returns (moved, duplicates). Already-organized names are not duplicated."""
    source, out_dir = dump_folder(user_dir), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "manifest.csv"
    known = {}
    if manifest_path.is_file():
        with manifest_path.open(encoding="utf-8", newline="") as stream:
            known = {row["file"]: row for row in csv.DictReader(stream)}
    events = sorted(archive_events(user_dir, since))
    files = sorted((p for p in source.rglob("*.png")), key=lambda p: p.stat().st_mtime) if source.is_dir() else []
    moved = duplicates = 0
    for path in files:
        if path.name in known:
            path.unlink()
            duplicates += 1
            continue
        stamp = path.stat().st_mtime
        archive = next((name for when, name in reversed(events) if when <= stamp), None)
        area = area_for(archive) if archive else "00 Title" if not events else "Unsorted"
        match = TEX_NAME.match(path.name)
        width, height, fmt = (int(match.group(1)), int(match.group(2)), int(match.group(3))) if match else (0, 0, -1)
        target = out_dir / area / path.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(path), target)
        known[path.name] = {"file": path.name, "area": area, "archive": archive or "",
                            "width": width, "height": height, "format": FORMATS.get(fmt, str(fmt)),
                            "first_seen": datetime.fromtimestamp(stamp).isoformat(timespec="seconds")}
        moved += 1
    with manifest_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["file", "area", "archive", "width", "height", "format", "first_seen"])
        writer.writeheader()
        writer.writerows(sorted(known.values(), key=lambda row: (row["area"], row["file"])))
    write_readme(out_dir, len(known))
    return moved, duplicates


def write_readme(out_dir, total):
    (Path(out_dir) / "README.txt").write_text(f"""Wario World texture dump ({total} textures)

Folders: one per area, chosen automatically from the stage archive the game had
just loaded when the texture first appeared. Shared textures sit in the area
where they were first seen. World numbering follows the disc archives
(1, 2, 4, 5 = worlds 1-4); folder names after the code are best guesses.
manifest.csv lists every file with its area, size, GameCube format and the time
it was first seen. Formats: I4/I8/IA4/IA8 are greyscale/fonts/masks, CMPR is
compressed colour, RGB5A3/RGBA8/C4/C8 may carry alpha - keep alpha when upscaling.

Upscaling: keep every file name exactly as it is (the name is the texture's
hash). Upscale by a whole factor (2x/4x) and keep the aspect ratio. Put the
results anywhere under
  Recomp/private/playtest-user/Load/Textures/GWWE01/
(subfolders are fine), then tick "Use HD textures" in the launcher.
Do not distribute these files: they are game assets.
""", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("dump-on", "dump-off", "hd-on", "hd-off", "organize"):
        command = sub.add_parser(name)
        command.add_argument("--user-dir", type=Path, required=True)
        if name == "organize":
            command.add_argument("--out", type=Path, required=True)
            command.add_argument("--since", type=float, default=time.time() - 24 * 3600)
    args = parser.parse_args()
    if args.command == "organize":
        moved, duplicates = organize(args.user_dir, args.out, args.since)
        print(f"organized {moved} new textures ({duplicates} duplicates removed) into {args.out}")
    elif args.command.startswith("dump"):
        set_dump_mode(args.user_dir, args.command == "dump-on")
    else:
        set_hd_mode(args.user_dir, args.command == "hd-on")


if __name__ == "__main__":
    main()
