"""Hidden FPS-interpolation sweep over every play-tracker savestate (all worlds seen so far).

For each private/play-sessions/*/states/*.sav: run --seconds with frame interpolation (camera +
objects), dump real/in-between triples, then report min speed, identity collisions
(tag_repeat_diff), tagged share and the eroded "blob" outlier score (see fps_flicker_check.py).
Writes reports/fps-world-sweep.json (private paths only; no game data).

Usage: python scripts/fps_world_sweep.py [--multiplier 2] [--seconds 25] [--limit N]
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from fps_flicker_check import erode  # noqa: E402

SEED = ROOT / "private/runs/20261026T111939310041Z-8d4aab64/user"


def blob_scores(dump):
    scores = []
    for real in sorted(dump.glob("real_*.png")):
        n = int(real.stem[5:])
        mid, after = dump / f"mid_{n + 1:08}.png", dump / f"real_{n + 1:08}.png"
        if not (mid.exists() and after.exists()):
            continue
        a, m, b = (np.asarray(Image.open(p).convert("L"), dtype=np.int16) for p in (real, mid, after))
        mask = (m < np.minimum(a, b) - 40) | (m > np.maximum(a, b) + 40)
        scores.append(float(erode(mask).mean() * 100))
    return scores


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--multiplier", default="2")
    parser.add_argument("--seconds", type=int, default=25)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--module", default=str(ROOT / "build/module-full-vectors-clang-pgo/gGWWE01_recomp.dll"))
    parser.add_argument("--runner", default=str(ROOT / "build/moderngekko-prof/RelWithDebInfo/moderngekko-run.exe"))
    args = parser.parse_args()
    states = sorted(ROOT.glob("private/play-sessions/*/states/*.sav"))
    if args.limit:
        states = states[:args.limit]
    results = []
    for state in states:
        name = f"{state.parent.parent.name}-{state.stem}"
        work = ROOT / "private/fps-sweep" / name
        dump = work / "dump"
        dump.mkdir(parents=True, exist_ok=True)
        for old in dump.glob("*.png"):
            old.unlink()
        stats = work / "stats.txt"
        stats.unlink(missing_ok=True)
        env = dict(os.environ, MODERNGEKKO_WARIO_FPS=args.multiplier, MODERNGEKKO_WARIO_FPS_OBJECTS="1",
                   MODERNGEKKO_WARIO_FPS_STATS=str(stats), MODERNGEKKO_WARIO_FPS_DUMP=str(dump))
        output = subprocess.run([sys.executable, str(ROOT / "scripts/smoke_boot.py"), "--module", args.module,
                                 "--full", "--vectors", "--seconds", str(args.seconds), "--load-state", str(state),
                                 "--seed-user", str(SEED), "--probe-file", str(ROOT / "config/probes/walk_punch.json"),
                                 "--graphics", "OpenGL", "--runner", args.runner],
                                capture_output=True, text=True, env=env).stdout
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
                fields[key] = value
        scores = blob_scores(dump)
        row = {"state": name, "run": run.name if run else None, "min_speed": summary.get("min_speed"),
               "slow_samples": summary.get("slow_samples"), "interpolated": fields.get("interpolated"),
               "tagged_loads": fields.get("tagged_loads"), "matched": fields.get("matrices_matched"),
               "unmatched": fields.get("matrices_unmatched"), "repeat_diff": fields.get("tag_repeat_diff"),
               "blob_mean": round(float(np.mean(scores)), 4) if scores else None,
               "blob_max": round(max(scores), 4) if scores else None}
        results.append(row)
        print(json.dumps(row), flush=True)
    out = ROOT / "reports/fps-world-sweep.json"
    out.write_text(json.dumps(results, indent=1), encoding="utf-8")
    print("->", out)


if __name__ == "__main__":
    main()
