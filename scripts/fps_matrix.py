"""Hidden FPS-interpolation speed/pacing matrix (multipliers x scenes) on the prof runner.

Usage: python scripts/fps_matrix.py [--multipliers 2 3 4] [--scenes hub boss] [--seconds 30]
Prints min speed, slow samples and the interpolation stats per run. Scenes are private
savestates from earlier hidden runs / the play tracker.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENTRY = ROOT / "private/runs/20261026T111939310041Z-8d4aab64"
HUB = ROOT / "private/runs/20261026T232050303943Z-da9e08f9"
SCENES = {
    "hub": ["--load-state", HUB / "control/checkpoint.savestate", "--seed-user", HUB / "user"],
    "boss": ["--load-state", ROOT / "private/play-sessions/20261026T202756Z/states/205027_CB41.sav",
             "--seed-user", ENTRY / "user", "--probe-file", ROOT / "config/probes/walk_punch.json"],
    "greenhorn": ["--load-state", ENTRY / "control/checkpoint.savestate", "--seed-user", ENTRY / "user",
                  "--probe-file", ROOT / "config/probes/walk_punch.json"],
    # World 4 lava field (heat haze that follows the camera).
    "lava": ["--load-state", ROOT / "private/play-sessions/20261026T235718Z/states/000855_CF43.sav",
             "--seed-user", ENTRY / "user", "--probe-file", ROOT / "config/probes/walk_punch.json"],
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--multipliers", nargs="+", default=["2", "3", "4"])
    parser.add_argument("--scenes", nargs="+", default=["hub", "boss"])
    parser.add_argument("--seconds", type=int, default=30)
    parser.add_argument("--runner", type=Path, default=ROOT / "build/moderngekko-prof/RelWithDebInfo/moderngekko-run.exe")
    args = parser.parse_args()
    for multiplier in args.multipliers:
        for scene in args.scenes:
            stats = ROOT / f"private/fps-matrix/{multiplier}-{scene}.txt"
            stats.parent.mkdir(parents=True, exist_ok=True)
            stats.unlink(missing_ok=True)
            env = dict(os.environ)
            env.pop("MODERNGEKKO_WARIO_FPS", None)
            if multiplier != "off":
                env["MODERNGEKKO_WARIO_FPS"] = multiplier
                env["MODERNGEKKO_WARIO_FPS_STATS"] = str(stats)
            command = [sys.executable, str(ROOT / "scripts/smoke_boot.py"), "--module",
                       str(ROOT / os.environ.get("FPS_MATRIX_MODULE", str(ROOT / "build/module-full-vectors-clang-pgo/gGWWE01_recomp.dll"))), "--full", "--vectors",
                       "--seconds", str(args.seconds), *map(str, SCENES[scene]), "--graphics", "OpenGL",
                       "--runner", str(args.runner)]
            output = subprocess.run(command, capture_output=True, text=True, env=env, timeout=600).stdout
            match = re.search(r"Diagnostic output: (.+)", output)
            run = Path(match.group(1).strip()) if match else None
            summary = {}
            if run and (run / "result.json").is_file():
                summary = json.loads(subprocess.run([sys.executable, str(ROOT / "scripts/run_summary.py"), str(run)],
                                                    capture_output=True, text=True).stdout or "{}")
            fields = {}
            if stats.is_file():
                for line in stats.read_text().splitlines():
                    key, _, value = line.partition("=")
                    if key in ("interpolated", "skipped_late", "gaps_6_10", "gaps_lt4", "gaps_4_6", "gaps_10_12",
                               "gaps_12_15", "gaps_ge15", "matrices_matched", "matrices_unmatched", "tagged_loads", "tag_repeats", "tag_repeat_diff"):
                        fields[key] = value
            print(f"{multiplier}x {scene}: speed={summary.get('min_speed')} slow={summary.get('slow_samples')} "
                  f"run={run.name if run else None} {fields}", flush=True)


if __name__ == "__main__":
    main()
