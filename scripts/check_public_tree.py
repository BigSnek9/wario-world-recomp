"""Reject game-derived paths/binaries in Git's tracked index before publication."""
import pathlib
import subprocess
import sys
import argparse

root = pathlib.Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--source-tree", action="store_true", help="Also inspect untracked, non-ignored source files")
args = parser.parse_args()
command = ["git", "-C", str(root), "ls-files", "-z", "--cached"]
if args.source_tree:
    command += ["--others", "--exclude-standard"]
result = subprocess.run(command, capture_output=True, check=True)
blocked_dirs = {"original", "generated", "reports", "build", "dist", "private", "captures", "third_party"}
blocked_exts = {".iso", ".gcm", ".rvz", ".wbfs", ".dol", ".rel", ".elf", ".rsc", ".samp", ".sdir", ".pool", ".proj", ".dtm", ".sav", ".raw", ".gci", ".dll", ".exe", ".obj", ".o", ".lib", ".pdb"}
# README screenshots published in docs/images/ (2026-10-27); nothing else binary.
screenshot_exts = {".webp", ".png", ".jpg"}
bad = []
checked = 0
for raw in result.stdout.split(b"\0"):
    if not raw:
        continue
    checked += 1
    name = raw.decode("utf-8")
    path = pathlib.PurePosixPath(name)
    local = root / path
    if path.parent == pathlib.PurePosixPath("docs/images") and path.suffix.lower() in screenshot_exts:
        if (root / path).stat().st_size > 1024 * 1024:
            bad.append(name)
        continue
    if path.parts[0].lower() in blocked_dirs or path.suffix.lower() in blocked_exts:
        bad.append(name)
    elif local.is_file() and (local.stat().st_size > 1024 * 1024 or b"\0" in local.read_bytes()[:8192]):
        bad.append(name)
if not checked:
    print("No source files checked. Use --source-tree before staging; an empty index establishes nothing.")
    sys.exit(1)
print("PUBLIC TREE FAILED: " + ", ".join(bad) if bad else f"Public tree check passed: {checked} files (not a legal clearance).")
sys.exit(bool(bad))
