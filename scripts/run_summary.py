"""Summarize host speed/FPS samples from smoke_boot result.json files.

speed < 1 means the host fell behind real time (a host-side slowdown);
fps < 59.9 with speed ~1 means the guest itself presented fewer frames.
Usage: python scripts/run_summary.py <run-dir> [<run-dir> ...]
"""
import json
import sys
from pathlib import Path


def summarize(run: Path) -> dict:
    data = json.loads((run / "result.json").read_text(encoding="utf-8"))
    points = []
    for sample in data["samples"]:
        status = dict(line.split("=", 1) for line in sample["status"].splitlines() if "=" in line)
        if status.get("state") != "running":
            continue
        speed, fps = float(status.get("speed", 0)), float(status.get("fps", 0))
        if 0 < speed < 50:  # discard warm-up/state-load outliers
            points.append((sample["elapsed"], speed, fps))
    points = points[5:]
    if not points:
        return {"run": run.name, "samples": 0}
    slow = [p for p in points if p[1] < 0.97]
    return {
        "run": run.name,
        "settings": data.get("dolphin_settings"),
        "samples": len(points),
        "min_speed": round(min(p[1] for p in points), 3),
        "min_speed_at": min(points, key=lambda p: p[1])[0],
        "slow_samples": len(slow),
        "slow_at": sorted({round(p[0]) for p in slow}),
        "min_fps": round(min(p[2] for p in points), 2),
    }


if __name__ == "__main__":
    for argument in sys.argv[1:]:
        print(json.dumps(summarize(Path(argument))))
