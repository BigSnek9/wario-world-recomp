"""Save source-only diffs for each pinned tool checkout, excluding submodules."""
import hashlib
import json
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[1]
patches = root / "patches"
patches.mkdir(exist_ok=True)
repositories = {
    "DolRecomp": "third_party/DolRecomp",
    "ModernGekko": "third_party/ModernGekko",
    "RecompCore": "third_party/ModernGekko/vendor/dolphin",
    "Bundled-DolRecomp": "third_party/ModernGekko/vendor/dolphin/DolRecomp",
}
manifest = {}
for name, relative in repositories.items():
    repo = root / relative
    diff = subprocess.check_output(["git", "-C", str(repo), "diff", "--no-ext-diff", "--ignore-submodules=all", "HEAD", "--"])
    (patches / (name + ".patch")).write_bytes(diff)
    revision = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
    manifest[name] = dict(path=relative, commit=revision, patch_sha256=hashlib.sha256(diff).hexdigest(), bytes=len(diff))
(patches / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
print(json.dumps(manifest, indent=2))
