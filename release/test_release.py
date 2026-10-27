"""Clean-folder test of the release zip (hidden and muted; read-only on the player's disc image).

1. Unzips dist/WarioWorldRecomp-v<version>.zip into a fresh private/release-test/ folder.
2. Runs the first-run setup non-interactively: WarioWorldRecomp.exe --iso <iso> --setup-only --quiet
   (timed). The .iso is only read.
3. Checks the extracted game against the pinned hashes (config/project.json) and, file by file,
   against original/GWWE01 when present (byte equality, `dolrecomp extract --native-only` layout).
4. Checks the coin icon equals release/coin_icon.py's output for the same disc (C++ vs Python),
   and the written configuration equals what the Python starter's prepare() produces.
5. Boots the release hidden and muted through the starter itself (--hidden-test: headless runner,
   screenshots every 5 s from 10 s), and optionally with scripts/smoke_boot.py on the release runner,
   module and game (--smoke).
The report and captures go to private/runs/<stamp>-release-test/; the test folder is deleted
afterwards unless --keep.

    python release/test_release.py --iso "<your.iso>" [--version 1.0] [--seconds 30] [--smoke] [--keep]
"""
import argparse
import configparser
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "release"), str(ROOT / "scripts")]
CONFIG = json.loads((ROOT / "config/project.json").read_text(encoding="utf-8"))


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        while chunk := stream.read(8 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def ini(path, lower_keys=True):
    config = configparser.ConfigParser(interpolation=None, strict=False)
    if not lower_keys:
        config.optionxform = str
    config.read(path, encoding="utf-8-sig")
    return {section: dict(config[section]) for section in config.sections()}


def python_reference(user):
    """What launcher/wario_launcher.pyw prepare() + run_once() write into a fresh user folder."""
    import configure_baseline
    import configure_controls
    import texture_tools
    configure_controls.install(user)
    configure_baseline.install(user)
    config = configparser.ConfigParser(interpolation=None)
    config.read(user / "config.ini", encoding="utf-8")
    config.set("Video", "fullscreen", "false")
    config.set("Video", "resolution", "auto")
    with (user / "config.ini").open("w", encoding="utf-8") as stream:
        config.write(stream)
    texture_tools.set_dump_mode(user, False)
    texture_tools.hd_folder(user).mkdir(parents=True, exist_ok=True)
    texture_tools._set(user / "Config/GFX.ini", {"Hardware": {"VSync": "False"}})
    (user / "Config/WarioWorld.ini").write_text(
        "# Wario World in-game menu settings (Back / Tab in game)\nbackend=opengl\n", encoding="utf-8")
    texture_tools._set(user / "Config/Dolphin.ini", {"Core": {"CPUThread": "False"}})


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--iso", type=Path, required=True)
    parser.add_argument("--version", default="1.0")
    parser.add_argument("--seconds", type=int, default=30)
    parser.add_argument("--smoke", action="store_true", help="also run scripts/smoke_boot.py on the release files")
    parser.add_argument("--keep", action="store_true", help="keep private/release-test afterwards")
    args = parser.parse_args()
    name = f"WarioWorldRecomp-v{args.version}"
    zip_path = ROOT / "dist" / f"{name}.zip"
    test_root = ROOT / "private/release-test"
    out = ROOT / "private/runs" / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid4().hex[:8]
                                   + "-release-test")
    out.mkdir(parents=True)
    shutil.rmtree(test_root, ignore_errors=True)
    test_root.mkdir(parents=True)
    report = dict(zip=str(zip_path), zip_bytes=zip_path.stat().st_size, iso=str(args.iso), checks={})
    checks = report["checks"]
    try:
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(test_root)
        folder = test_root / name
        exe = folder / "WarioWorldRecomp.exe"
        iso_before = (args.iso.stat().st_size, args.iso.stat().st_mtime_ns)

        started = time.monotonic()
        result = subprocess.run([str(exe), "--iso", str(args.iso), "--setup-only", "--quiet"], timeout=600)
        report["first_run_seconds"] = round(time.monotonic() - started, 2)
        report["setup_exit_code"] = result.returncode
        report["launcher_log"] = (folder / "data/launcher.log").read_text(encoding="utf-8", errors="replace")
        checks["setup exit code 0"] = result.returncode == 0
        checks["iso untouched (size, mtime)"] = (args.iso.stat().st_size, args.iso.stat().st_mtime_ns) == iso_before

        game = folder / "game/GWWE01"
        checks["main.dol pinned hash"] = sha256(game / "sys/main.dol") == CONFIG["dol_sha256"]
        checks["REL pinned hashes"] = all(sha256(game / rel) == digest for rel, digest in CONFIG["rel_sha256"].items())
        original = ROOT / "original/GWWE01"
        if original.is_dir():
            ours = {p.relative_to(game).as_posix() for p in game.rglob("*") if p.is_file()}
            theirs = {p.relative_to(original).as_posix() for p in original.rglob("*") if p.is_file()} - {"audit.yml"}
            different = [rel for rel in sorted(ours & theirs) if sha256(game / rel) != sha256(original / rel)]
            report["extracted_files"] = len(ours)
            report["extract_mismatch"] = dict(only_release=sorted(ours - theirs), only_original=sorted(theirs - ours),
                                              different=different)
            checks["extraction byte-equal to original/GWWE01"] = ours == theirs and not different
        checks["no partial folder left"] = not (folder / "game/GWWE01.partial").exists()

        import coin_icon
        icon = folder / "WarioWorld.ico"
        checks["coin icon written"] = icon.is_file()
        if icon.is_file():
            expected = coin_icon.ico_bytes(coin_icon.icon_images(coin_icon.read_coin(game)))
            checks["coin icon identical to release/coin_icon.py"] = icon.read_bytes() == expected

        with tempfile.TemporaryDirectory() as temp:
            reference = Path(temp) / "user"
            python_reference(reference)
            user = folder / "user"
            for rel in ("config.ini", "Config/GFX.ini", "Config/Logger.ini", "Config/Dolphin.ini",
                        "Config/GCPadNew.ini"):
                checks[f"{rel} matches the Python starter"] = ini(user / rel) == ini(reference / rel)
                if not checks[f"{rel} matches the Python starter"]:
                    report.setdefault("config_diff", {})[rel] = dict(release=ini(user / rel),
                                                                     python=ini(reference / rel))
            checks["WarioWorld.ini backend default"] = "backend=opengl" in (
                user / "Config/WarioWorld.ini").read_text(encoding="utf-8")
            checks["HD texture folder"] = (user / "Load/Textures/GWWE01").is_dir()

        # Hidden, muted boot through the starter itself.
        started = time.monotonic()
        result = subprocess.run([str(exe), "--hidden-test", str(args.seconds)], timeout=args.seconds + 120)
        report["hidden_boot_seconds"] = round(time.monotonic() - started, 2)
        report["hidden_boot_exit_code"] = result.returncode
        captures = sorted((folder / "data").rglob("launcher-*.png"))
        (out / "captures").mkdir()
        for capture in captures:
            shutil.copy2(capture, out / "captures" / capture.name)
        report["captures"] = [str(out / "captures" / c.name) for c in captures]
        for log in ("last-run.log", "launcher.log"):
            if (folder / "data" / log).is_file():
                shutil.copy2(folder / "data" / log, out / log)
        checks["hidden boot exit code 0"] = result.returncode == 0
        checks["hidden boot captures"] = len(captures) >= max(1, (args.seconds - 10) // 5 - 1)

        if args.smoke:
            started = time.monotonic()
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts/smoke_boot.py"), "--graphics", "OpenGL", "--seconds",
                 str(args.seconds), "--capture-cadence", "5", "--runner", str(folder / "runtime/moderngekko-run.exe"),
                 "--module", str(folder / "module/gGWWE01_recomp.dll"), "--game", str(game)],
                capture_output=True, text=True, timeout=args.seconds + 180)
            report["smoke_boot_seconds"] = round(time.monotonic() - started, 2)
            report["smoke_boot_exit_code"] = result.returncode
            report["smoke_boot_tail"] = result.stdout[-1500:]
            checks["smoke_boot exit code 0"] = result.returncode == 0
    finally:
        report["passed"] = bool(checks) and all(checks.values())
        (out / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        if not args.keep:
            shutil.rmtree(test_root, ignore_errors=True)
    print(json.dumps({k: v for k, v in report.items() if k != "launcher_log"}, indent=2))
    print("Report:", out / "report.json")
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
