"""Bucket a sample_profile.exe CSV over time for one thread.

Usage: python scripts/profile_timeline.py <run-dir> [--thread "CPU-GPU thread"] [--bucket-ms 250] [--top 4]
Each line: bucket start (ms since profile start), sample count, wait/game/other
percentages and the hottest non-wait symbols in that bucket.
"""
import argparse
import collections
import csv
from pathlib import Path

WAITS = ("NtWaitFor", "ZwWaitFor", "ZwDelayExecution", "NtDelayExecution", "MsgWaitFor")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--thread", default="CPU")
    parser.add_argument("--bucket-ms", type=int, default=250)
    parser.add_argument("--top", type=int, default=4)
    parser.add_argument("--from-ms", type=int, default=0)
    parser.add_argument("--to-ms", type=int, default=10**9)
    args = parser.parse_args()
    buckets = collections.defaultdict(collections.Counter)
    kinds = collections.defaultdict(collections.Counter)
    with (args.run_dir / "profile.csv").open(encoding="utf-8", errors="replace") as stream:
        for row in csv.DictReader(stream):
            if args.thread not in row["thread"]:
                continue
            t = int(row["t_ms"])
            if not args.from_ms <= t < args.to_ms:
                continue
            key = t // args.bucket_ms
            if any(w in row["symbol"] for w in WAITS):
                kinds[key]["wait"] += 1
                continue
            kinds[key]["game" if row["module"] == "gGWWE01_recomp" else "other"] += 1
            buckets[key][row["module"] + "!" + row["symbol"]] += 1
    for key in sorted(kinds):
        total = sum(kinds[key].values())
        mix = " ".join(f"{k}={100 * v // total}%" for k, v in sorted(kinds[key].items()))
        hot = ", ".join(f"{name.split('!', 1)[1][:60]}:{n}" for name, n in buckets[key].most_common(args.top))
        print(f"{key * args.bucket_ms:6d} n={total:4d} {mix:32s} {hot}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
