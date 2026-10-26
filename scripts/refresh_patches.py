"""Save source-only diffs for each pinned tool checkout, excluding submodules."""
import argparse
import difflib
import hashlib
import json
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source-root', type=Path, help='Read pinned checkouts elsewhere; write patches beside this script')
parser.add_argument('--lockstep-overlay', type=Path, help='Include the verified canonical-MSR source overlay')
args = parser.parse_args()
source_root = args.source_root.resolve() if args.source_root else root
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
    repo = source_root / relative
    diff = subprocess.check_output(["git", "-C", str(repo), "diff", "--no-ext-diff", "--ignore-submodules=all", "HEAD", "--"])
    if name == "RecompCore" and args.lockstep_overlay:
        source_path = "Source/Core/Core/PowerPC/StaticRecomp/StaticRecompLockstep_Check.cpp"
        base = subprocess.check_output(["git", "-C", str(repo), "show", "HEAD:" + source_path]).decode("utf-8")
        current = (repo / source_path).read_text(encoding="utf-8")
        overlay = args.lockstep_overlay.read_text(encoding="utf-8")
        expected = current.replace("  ppc.msr.Hex = saved_msr;\n  power_pc.MSRUpdated();",
            "  StaticRecompCore::SetPPCStateFromGuestState(m_core.m_guest, ppc);\n  ppc.msr.Hex = m_core.m_guest.msr;\n  power_pc.MSRUpdated();").replace("  const u64 saved_msr = ppc.msr.Hex;\n", "")
        if overlay != expected:
            raise RuntimeError("Overlay differs from current source beyond the reviewed MSR restoration")
        marker = "diff --git a/" + source_path + " b/" + source_path + "\n"
        blocks = diff.decode("utf-8").split("diff --git ")
        retained = [blocks[0]] + ["diff --git " + block for block in blocks[1:] if not block.startswith("a/" + source_path + " ")]
        replacement = marker + "".join(difflib.unified_diff(base.splitlines(True), overlay.splitlines(True),
            fromfile="a/" + source_path, tofile="b/" + source_path))
        diff = ("".join(retained) + replacement).encode("utf-8")
    (patches / (name + ".patch")).write_bytes(diff)
    revision = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
    manifest[name] = dict(path=relative, commit=revision, patch_sha256=hashlib.sha256(diff).hexdigest(), bytes=len(diff))
(patches / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
print(json.dumps(manifest, indent=2))
