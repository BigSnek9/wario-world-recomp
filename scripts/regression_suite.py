"""Hidden, muted regression suite over the private checkpoints.

Runs smoke_boot.py scenarios and checks objective pass criteria. Each case gets
its own fresh private run folder; nothing touches private/playtest-user.
Writes reports/regression-<UTC>.json (private, ignored) and prints a summary.

Usage: python scripts/regression_suite.py [--quick] [--module DLL] [--twin DLL] [--runner EXE]
--quick skips the two lockstep cases (~3 minutes instead of ~7).

Fixtures (private, created during 2026-10-26 work; see docs/progress):
  stage entry   private/runs/20261026T111939310041Z-8d4aab64 (checkpoint + user)
  river         private/runs/20261026T162519351895Z-ac6873d6
  progress save private/seeds/progress-save (copy of the playtest GCI)
"""
import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from run_summary import summarize  # noqa: E402

ENTRY = ROOT / "private/runs/20261026T111939310041Z-8d4aab64"
RIVER = ROOT / "private/runs/20261026T162519351895Z-ac6873d6"
SAVE_SEED = ROOT / "private/seeds/progress-save"


def smoke(*arguments, timeout=600):
    output = subprocess.run([sys.executable, str(ROOT / "scripts/smoke_boot.py"), *map(str, arguments)],
                            cwd=ROOT, capture_output=True, text=True, timeout=timeout)
    match = re.search(r"Diagnostic output: (.+)", output.stdout)
    if not match:
        raise RuntimeError("smoke_boot gave no run folder:\n" + output.stdout[-2000:] + output.stderr[-2000:])
    run = Path(match.group(1).strip())
    result = json.loads((run / "result.json").read_text(encoding="utf-8"))
    log = (run / "runner.log").read_text(encoding="utf-8", errors="replace")
    return run, result, log


def lockstep_summary(log):
    match = re.search(r"\[lockstep\] summary: checks=(\d+) reports=(\d+)", log)
    return (int(match.group(1)), int(match.group(2))) if match else (0, -1)


def captures(run):
    return sorted((run / "control").glob("diagnostic-*.png"))


def mean_luma(path):
    return float(np.asarray(Image.open(path).convert("L"), dtype=np.float32).mean())


def frame_change(paths):
    frames = [np.asarray(Image.open(p).convert("L"), dtype=np.int16) for p in paths]
    return [float(np.abs(b - a).mean()) for a, b in zip(frames, frames[1:])]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--module", type=Path, default=ROOT / "build/module-full-vectors-clang-pgo/gGWWE01_recomp.dll")
    parser.add_argument("--twin", type=Path, default=ROOT / "build/module-rel-bundle-vectors-clang-pgo/gGWWE01_recomp.dll")
    parser.add_argument("--runner", type=Path)
    args = parser.parse_args()
    common = ["--graphics", "OpenGL"] + (["--runner", args.runner] if args.runner else [])
    cases = []

    def record(name, run, passed, **details):
        cases.append({"case": name, "passed": bool(passed), "run": str(run), **details})
        print(f"[{'PASS' if passed else 'FAIL'}] {name}: {details}", flush=True)

    # 1. Boot, title, load the progressed save, reach the hub.
    run, result, log = smoke("--module", args.module, "--full", "--vectors", "--seconds", 75, "--seed-user", SAVE_SEED,
                             "--probe-file", ROOT / "config/probes/reload_save.json", "--pad-hold", 12,
                             "--capture-cadence", 15, *common)
    stats = summarize(run)
    shots = captures(run)
    last_luma = mean_luma(shots[-1]) if shots else 0.0
    record("boot_to_hub", run, result["exit_code"] == 0 and not result["forced_stop"] and stats.get("min_speed", 0) >= 0.8
           and last_luma > 20, min_speed=stats.get("min_speed"), min_fps=stats.get("min_fps"), last_luma=round(last_luma, 1))
    # Static-only guard: no game instruction may reach Dolphin's interpreter or JIT.
    interp = re.search(r"hook_interp=(\d+)", log)
    jit = re.search(r"fallback_entries=(\d+)", log)
    record("no_interpreter_or_jit", run, bool(interp and jit) and int(interp.group(1)) == 0 and int(jit.group(1)) == 0,
           hook_interp=int(interp.group(1)) if interp else None, jit_entries=int(jit.group(1)) if jit else None)

    # 2. Greenhorn Forest movement and combat inputs hold full speed.
    run, result, log = smoke("--module", args.module, "--full", "--vectors", "--seconds", 110,
                             "--load-state", ENTRY / "control/checkpoint.savestate", "--seed-user", ENTRY / "user",
                             "--probe-file", ROOT / "config/probes/walk_punch.json", "--capture-cadence", 10, *common)
    stats = summarize(run)
    record("greenhorn_walk_punch", run, result["exit_code"] == 0 and result["state_load_complete"]
           and stats.get("min_speed", 0) >= 0.95, min_speed=stats.get("min_speed"), min_fps=stats.get("min_fps"))

    # 3. River and waterfall animate (KI-002 regression guard).
    run, result, log = smoke("--module", args.module, "--full", "--vectors", "--seconds", 16,
                             "--load-state", RIVER / "control/checkpoint.savestate", "--seed-user", RIVER / "user",
                             "--capture-cadence", 1, *common)
    changes = frame_change(captures(run))
    record("river_water_animates", run, len(changes) >= 5 and min(changes) > 3.0,
           frames=len(changes) + 1, min_change=round(min(changes), 2) if changes else None)

    if not args.quick:
        # 4/5. Native code vs interpreter shadow (lockstep) over both routes.
        run, result, log = smoke("--module", args.twin, "--vectors", "--lockstep", "--lockstep-limit", 0, "--seconds", 75,
                                 "--load-state", ENTRY / "control/checkpoint.savestate", "--seed-user", ENTRY / "user",
                                 "--probe-file", ROOT / "config/probes/explore_forward.json", *common)
        checks, reports = lockstep_summary(log)
        record("lockstep_greenhorn_walk", run, checks > 5000 and reports == 0, checks=checks, reports=reports)
        run, result, log = smoke("--module", args.twin, "--vectors", "--lockstep", "--lockstep-limit", 0, "--seconds", 80,
                                 "--seed-user", SAVE_SEED, "--probe-file", ROOT / "config/probes/reload_save.json",
                                 "--pad-hold", 12, *common)
        checks, reports = lockstep_summary(log)
        record("lockstep_title_save_hub", run, checks > 5000 and reports == 0, checks=checks, reports=reports)

    report = {"time": datetime.now(timezone.utc).isoformat(), "module": str(args.module), "twin": str(args.twin),
              "passed": all(c["passed"] for c in cases), "cases": cases}
    out = ROOT / "reports" / ("regression-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + ".json")
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(("ALL PASS" if report["passed"] else "FAILURES") + f" -> {out}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
