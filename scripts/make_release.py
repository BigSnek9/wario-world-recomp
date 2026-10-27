"""Build the player release zip (ShadowRecomp style): dist/WarioWorldRecomp-vX.Y.zip.

The zip holds the native starter (WarioWorldRecomp.exe), the runtime (moderngekko-run.exe, its
Sys data and the Visual C++ runtime DLLs it imports, app-local), the compiled game module, licence
notices and a README. The player's own disc supplies every asset: the starter checks and extracts
it on first run. Nothing from the disc, no extracted data, generated C, PDBs, logs or user data is
ever packaged; a final check fails the build if any disc-derived file (by content hash against
original/GWWE01 when present, and by name/extension) or C source got in.

This script only packages existing builds; it never rebuilds the runtime or the game module.

    python scripts/make_release.py --version 1.0 [--build-launcher] [--no-source-zip]

Inputs (defaults):
  runtime   build/moderngekko/Release (moderngekko-run.exe + Sys)
  module    build/module-full-vectors-clang-pgo/gGWWE01_recomp.dll (clang PGO)
  launcher  build/release-launcher/WarioWorldRecomp.exe (release/launcher, CMake)
Outputs: dist/WarioWorldRecomp-v<version>.zip, plus (unless --no-source-zip)
dist/WarioWorldRecomp-v<version>-source.zip (git archive of HEAD: this project's corresponding
source; the pinned upstream sources are fetched by scripts/build.py from config/project.json).
"""
import argparse
import configparser
import glob
import hashlib
import io
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config/project.json").read_text(encoding="utf-8"))
DOLPHIN = ROOT / "third_party/ModernGekko/vendor/dolphin"
CRT_NAMES = ("msvcp140.dll", "msvcp140_1.dll", "msvcp140_2.dll", "msvcp140_atomic_wait.dll",
             "msvcp140_codecvt_ids.dll", "vcruntime140.dll", "vcruntime140_1.dll", "concrt140.dll")
# Never in a release: disc formats, sources, debug data, logs, saves, generated icons.
BLOCKED_EXTS = {".iso", ".gcm", ".rvz", ".wbfs", ".ciso", ".gcz", ".dol", ".rel", ".rsc", ".bnr", ".elf",
                ".c", ".cc", ".cpp", ".s", ".asm", ".o", ".obj", ".lib", ".exp", ".pdb", ".ilk", ".ipdb", ".iobj",
                ".pgd", ".pgc", ".profdata", ".profraw", ".log", ".sav", ".gci", ".raw", ".dtm", ".ico",
                ".samp", ".sdir", ".pool", ".proj", ".bin.partial"}
BLOCKED_DIRS = {"game", "user", "data", "original", "generated", "private", "reports", "captures", "gwwe01"}
# Upstream Dolphin data that legitimately carries the game id in its name (per-game settings).
ALLOWED_GAME_ID_FILES = {"runtime/Sys/GameSettings/GWWE01.ini"}


# ------------------------------------------------------------------------------- PE inspection

def pe_imports(path):
    """DLL names a PE image imports (normal import table)."""
    data = Path(path).read_bytes()
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    if data[pe:pe + 4] != b"PE\0\0":
        raise ValueError(f"{path} is not a PE image")
    sections_count = struct.unpack_from("<H", data, pe + 6)[0]
    opt_size = struct.unpack_from("<H", data, pe + 20)[0]
    opt = pe + 24
    magic = struct.unpack_from("<H", data, opt)[0]
    dirs = opt + (112 if magic == 0x20B else 96)
    import_rva = struct.unpack_from("<I", data, dirs + 8)[0]
    sections = []
    for i in range(sections_count):
        s = opt + opt_size + 40 * i
        vsize, va, rawsize, rawptr = struct.unpack_from("<IIII", data, s + 8)
        sections.append((va, max(vsize, rawsize), rawptr))

    def offset(rva):
        for va, size, raw in sections:
            if va <= rva < va + size:
                return rva - va + raw
        raise ValueError("bad RVA")
    names = []
    if import_rva:
        pos = offset(import_rva)
        while True:
            name_rva = struct.unpack_from("<I", data, pos + 12)[0]
            if not name_rva:
                break
            start = offset(name_rva)
            names.append(data[start:data.index(b"\0", start)].decode("ascii"))
            pos += 20
    return names


def missing_dependencies(image, shipped_dir):
    """Imported DLLs that are neither shipped next to the runner nor part of Windows."""
    system = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32"
    missing = []
    for name in pe_imports(image):
        lower = name.lower()
        if (shipped_dir / name).is_file() or (shipped_dir / lower).is_file():
            continue
        if lower in CRT_NAMES:
            missing.append(name)  # VC++ runtime: must be shipped, never assumed installed
        elif lower.startswith(("api-ms-win-", "ext-ms-win-")) or (system / name).is_file():
            continue
        else:
            missing.append(name)
    return missing


def crt_redist():
    """The newest Visual C++ x64 CRT redistributable folder of the installed Visual Studio."""
    found = []
    for base in (r"C:\Program Files\Microsoft Visual Studio", r"C:\Program Files (x86)\Microsoft Visual Studio"):
        found += glob.glob(base + r"\*\*\VC\Redist\MSVC\*\x64\Microsoft.VC14*.CRT")
    found = [Path(p) for p in found if "onecore" not in p.lower() and "debug" not in p.lower()]
    if not found:
        raise SystemExit("No Visual C++ x64 CRT redistributable found (Visual Studio Build Tools)")
    return max(found, key=lambda p: [int(x) for x in p.parents[1].name.split(".") if x.isdigit()])


# ------------------------------------------------------------------------------------ licences

def externals_built(runtime_build):
    """Dolphin externals compiled into the runner (their CMake build folders next to Release/)."""
    folder = runtime_build.parent / "vendor/dolphin/Externals"
    names = sorted(p.name for p in folder.iterdir() if p.is_dir()) if folder.is_dir() else []
    if not names:
        raise SystemExit(f"Cannot list the runtime's linked components (no {folder})")
    return names


LICENSE_NAMES = ("license", "licence", "copying", "notice")
SKIP_PARTS = {"test", "tests", "examples", "googletest", "docs", "programs", "cli", "build", "licenses"}
NO_LICENSE_FILE = {
    "Bochs_disasm": "Bochs disassembler: GNU LGPL 2.1 or later (see the source file headers); the LGPL-2.1 text "
                    "is included as externals/libusb/COPYING.",
    "FreeSurround": "FreeSurround (C) 2007-2010 Christian Kothe: GNU GPL 2 or later (see the source file headers "
                    "and Dolphin-GPL-2.0-or-later.txt).",
}


def external_licenses(name):
    base = DOLPHIN / "Externals" / name
    best = []
    for path in sorted(base.rglob("*")):
        rel = path.relative_to(base)
        if not path.is_file() or len(rel.parts) > 3 or SKIP_PARTS & {p.lower() for p in rel.parts[:-1]}:
            continue
        if path.name.lower().startswith(LICENSE_NAMES) and path.suffix.lower() in ("", ".txt", ".md"):
            best.append(path)
    if not best:
        return []
    depth = min(len(p.relative_to(base).parts) for p in best)
    return [p for p in best if len(p.relative_to(base).parts) == depth]


def git(*args):
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, check=True).stdout.strip()


# --------------------------------------------------------------------------------------- texts

README = """Wario World Recomp {version}
==========================

A native Windows PC version of Wario World (Nintendo GameCube, 2003), made by static
recompilation: the game's own code was translated to C and compiled for the PC, and runs on
a GameCube-compatible runtime based on Dolphin. Everything in this project (the
recompilation, the runtime fixes, the enhancements and this starter) was made by Claude,
Anthropic's AI, working at the owner's direction. Unofficial fan project, not affiliated
with or endorsed by Nintendo.

YOU NEED YOUR OWN DISC
No game files are included. You need your own dump of Wario World, USA disc (GWWE01,
revision 0), as a plain 1:1 .iso file (not .rvz / .wbfs / .nkit; Dolphin can convert those:
right-click the game > Convert File... > ISO).

REQUIREMENTS
Windows 10 or 11, 64-bit. A graphics card with OpenGL 4 or Vulkan. About 500 MB of disk space.

HOW TO START
1. Unzip this folder anywhere you own (for example Documents or D:\\Games, not Program Files).
2. Double-click WarioWorldRecomp.exe.
3. The first time, pick your .iso. It is checked (the exact USA disc, by its SHA-256) and its
   files are copied into game\\ next to the exe. This takes about half a minute and only
   happens once. Your .iso is only read, never changed, and can be moved afterwards.
4. The game starts. Press Back on the controller (or Tab) for the in-game menu: frame rate,
   widescreen, resolution, HDR, HD textures, audio, controls, cheats and more.

WHERE THINGS ARE
user\\   your saves (memory card) and settings. Keep this folder when you update.
data\\   logs (last-run.log, launcher.log) and bug-report snapshots (F12).
game\\   the game files from your disc. Delete it to set the game up again.

UPDATING
Unzip the new version over the old folder (or copy your user\\ folder into the new one).

LICENCES
The runtime (runtime\\) is based on Dolphin and ModernGekko and is licensed under the GNU GPL
(see LICENSES\\). Source code: see SOURCE.txt. Wario World is (c) Nintendo; this package
contains no Nintendo assets. The game module (module\\) is the game's own code, translated and
compiled; it only runs with the files from your own disc.
"""

SOURCE = """Corresponding source for Wario World Recomp {version}
======================================================

The runtime in runtime\\ (moderngekko-run.exe) is free software under the GNU General Public
License (GPLv3 or later for the combined work; Dolphin's code is GPLv2 or later). You can get
its complete corresponding source:

- this project (build scripts, runtime patches, the starter): {repo} at commit {commit}
  (also attached to the release as WarioWorldRecomp-v{version}-source.zip);
- ModernGekko: {mg_url} at commit {mg_commit}
  (with Dolphin / RecompCore and its pinned submodules, see its PROVENANCE.md);
- DolRecomp: {dr_url} at commit {dr_commit}.
The project's patches are applied to these upstream commits by scripts/build.py and
scripts/apply_tool_fixes.py; README.md and docs/START_HERE.md describe the build.

The Visual C++ runtime DLLs next to moderngekko-run.exe are Microsoft redistributable files
(Visual Studio 2022, version {crt_version}).
"""


# ------------------------------------------------------------------------------------- staging

def check_controller_defaults():
    """The embedded controller profile must equal configure_controls.py's defaults."""
    with tempfile.TemporaryDirectory() as folder:
        subprocess.run([sys.executable, str(ROOT / "scripts/configure_controls.py"), "--user-dir", folder],
                       check=True, capture_output=True)
        expected = (Path(folder) / "Config/GCPadNew.ini").read_bytes().replace(b"\r\n", b"\n")
    embedded = (ROOT / "release/launcher/defaults/GCPadNew.ini").read_bytes().replace(b"\r\n", b"\n")
    if expected != embedded:
        raise SystemExit("release/launcher/defaults/GCPadNew.ini differs from configure_controls.py; "
                         "regenerate it and rebuild the launcher")


def build_launcher():
    vcvars = glob.glob(r"C:\Program Files*\Microsoft Visual Studio\*\*\VC\Auxiliary\Build\vcvars64.bat")
    if not vcvars:
        raise SystemExit("vcvars64.bat not found (Visual Studio Build Tools)")
    script = (f'call "{vcvars[0]}" >nul && cmake -S "{ROOT / "release/launcher"}" -B "{ROOT / "build/release-launcher"}" '
              f'-G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER=cl && '
              f'cmake --build "{ROOT / "build/release-launcher"}"')
    with tempfile.NamedTemporaryFile("w", suffix=".cmd", delete=False) as handle:
        handle.write("@echo off\r\n" + script + "\r\n")
    try:
        subprocess.run(["cmd", "/c", handle.name], check=True)
    finally:
        os.unlink(handle.name)


def stage(args, folder):
    runtime_build = args.runtime
    runner = runtime_build / "moderngekko-run.exe"
    for path in (runner, runtime_build / "Sys", args.module, args.launcher):
        if not path.exists():
            raise SystemExit(f"Missing build output: {path}")
    shutil.copy2(args.launcher, folder / "WarioWorldRecomp.exe")
    (folder / "runtime").mkdir()
    shutil.copy2(runner, folder / "runtime")
    shutil.copytree(runtime_build / "Sys", folder / "runtime/Sys")
    crt = crt_redist()
    needed = {n.lower() for n in pe_imports(runner) + pe_imports(args.module)} & set(CRT_NAMES)
    for name in sorted(needed):
        shutil.copy2(crt / name, folder / "runtime" / name)
    (folder / "module").mkdir()
    shutil.copy2(args.module, folder / "module")
    for image in (folder / "runtime/moderngekko-run.exe", folder / "module/gGWWE01_recomp.dll",
                  folder / "WarioWorldRecomp.exe"):
        missing = missing_dependencies(image, folder / "runtime")
        if missing:
            raise SystemExit(f"{image.name} needs DLLs that are not shipped: {missing}")

    licenses = folder / "LICENSES"
    licenses.mkdir()
    shutil.copy2(ROOT / "LICENSE", licenses / "WarioWorldRecomp-GPL-3.0.txt")
    shutil.copy2(ROOT / "third_party/ModernGekko/LICENSE", licenses / "ModernGekko-GPL-3.0.txt")
    shutil.copy2(ROOT / "third_party/DolRecomp/LICENSE", licenses / "DolRecomp-GPL-3.0.txt")
    shutil.copy2(DOLPHIN / "COPYING", licenses / "Dolphin-COPYING.txt")
    for text in (DOLPHIN / "LICENSES").iterdir():
        shutil.copy2(text, licenses / ("Dolphin-" + text.name))
    notes = []
    for name in externals_built(runtime_build):
        found = external_licenses(name)
        if found:
            target = licenses / "externals" / name
            target.mkdir(parents=True)
            for path in found:
                shutil.copy2(path, target / path.name)
        elif name in NO_LICENSE_FILE:
            notes.append(NO_LICENSE_FILE[name])
        else:
            raise SystemExit(f"No licence file found for the linked component Externals/{name}")
    (licenses / "README.txt").write_text(
        "Licences of the software in this package\r\n\r\n"
        "- WarioWorldRecomp.exe and this project's scripts/patches: GPL-3.0 (WarioWorldRecomp-GPL-3.0.txt)\r\n"
        "- runtime\\moderngekko-run.exe: ModernGekko (GPL-3.0), DolRecomp (GPL-3.0) and Dolphin (GPL-2.0-or-later,\r\n"
        "  Dolphin-COPYING.txt and Dolphin-*.txt), statically linked with the components in externals\\\r\n"
        "- runtime\\Sys: Dolphin data files (GPL-2.0-or-later unless stated otherwise in the file)\r\n"
        "- runtime\\msvcp140*.dll, vcruntime140*.dll: Microsoft Visual C++ redistributable files\r\n\r\n"
        + "".join(f"- {note}\r\n" for note in notes), encoding="utf-8")

    commit = git("rev-parse", "HEAD")
    dirty = bool(git("status", "--porcelain", "--untracked-files=no"))
    repo = "https://github.com/BigSnek9/wario-world-recomp"
    (folder / "README.txt").write_text(README.format(version=args.version).replace("\n", "\r\n"), encoding="utf-8")
    (folder / "SOURCE.txt").write_text(SOURCE.format(
        version=args.version, repo=repo, commit=commit + (" (plus uncommitted changes)" if dirty else ""),
        mg_url=CONFIG["upstream"]["ModernGekko"]["url"], mg_commit=CONFIG["upstream"]["ModernGekko"]["commit"],
        dr_url=CONFIG["upstream"]["DolRecomp"]["url"], dr_commit=CONFIG["upstream"]["DolRecomp"]["commit"],
        crt_version=crt.parents[1].name).replace("\n", "\r\n"), encoding="utf-8")
    return commit, dirty


def check_release(folder):
    """Fail if anything disc-derived, generated or private is in the staged release."""
    disc_hashes = {}
    original = ROOT / "original/GWWE01"
    if original.is_dir():
        for path in original.rglob("*"):
            if path.is_file():
                disc_hashes[hashlib.sha256(path.read_bytes()).hexdigest()] = path.relative_to(original).as_posix()
    problems, manifest = [], []
    for path in sorted(folder.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(folder).as_posix()
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        manifest.append((rel, len(data), digest))
        parts = [p.lower() for p in rel.split("/")]
        if digest in disc_hashes and data:
            problems.append(f"{rel} is the disc file {disc_hashes[digest]}")
        if Path(rel).suffix.lower() in BLOCKED_EXTS:
            problems.append(f"{rel}: blocked file type")
        if BLOCKED_DIRS & set(parts[:-1]):
            problems.append(f"{rel}: blocked folder")
        if "gwwe01" in rel.lower() and rel not in ALLOWED_GAME_ID_FILES and rel != "module/gGWWE01_recomp.dll":
            problems.append(f"{rel}: game-id file")
        if data[:4] in (b"\x00\x20\xaf\x30", b"BNR1", b"BNR2") or data[0x1C:0x20] == b"\xc2\x33\x9f\x3d":
            problems.append(f"{rel}: looks like disc data")
    if not disc_hashes:
        problems.append("original/GWWE01 is not available, so the content-hash check could not run")
    return problems, manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", default="1.0")
    parser.add_argument("--runtime", type=Path, default=ROOT / "build/moderngekko/Release")
    parser.add_argument("--module", type=Path, default=ROOT / "build/module-full-vectors-clang-pgo/gGWWE01_recomp.dll")
    parser.add_argument("--launcher", type=Path, default=ROOT / "build/release-launcher/WarioWorldRecomp.exe")
    parser.add_argument("--build-launcher", action="store_true", help="(re)build release/launcher first (CMake)")
    parser.add_argument("--no-source-zip", action="store_true", help="skip the git-archive source zip")
    parser.add_argument("--out", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    started = time.monotonic()
    check_controller_defaults()
    if args.build_launcher:
        build_launcher()
    name = f"WarioWorldRecomp-v{args.version}"
    stage_root = ROOT / "build/release-stage"
    shutil.rmtree(stage_root, ignore_errors=True)
    folder = stage_root / name
    folder.mkdir(parents=True)
    commit, dirty = stage(args, folder)
    problems, manifest = check_release(folder)
    if problems:
        print("RELEASE CHECK FAILED:\n  " + "\n  ".join(problems))
        raise SystemExit(1)
    args.out.mkdir(parents=True, exist_ok=True)
    zip_path = args.out / f"{name}.zip"
    temp = zip_path.with_suffix(".zip.tmp")
    with zipfile.ZipFile(temp, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for rel, _size, _digest in manifest:
            archive.write(folder / rel, f"{name}/{rel}")
    temp.replace(zip_path)
    with zipfile.ZipFile(zip_path) as archive:  # the zip must hold exactly the checked files
        listed = sorted(i.filename[len(name) + 1:] for i in archive.infolist() if not i.is_dir())
        if listed != sorted(rel for rel, _s, _d in manifest) or archive.testzip() is not None:
            raise SystemExit("The zip does not match the checked release folder")
    report = dict(zip=str(zip_path), zip_bytes=zip_path.stat().st_size, files=len(manifest),
                  unpacked_bytes=sum(size for _r, size, _d in manifest), commit=commit, dirty=dirty,
                  module_sha256=next(d for r, _s, d in manifest if r == "module/gGWWE01_recomp.dll"),
                  runner_sha256=next(d for r, _s, d in manifest if r == "runtime/moderngekko-run.exe"),
                  launcher_sha256=next(d for r, _s, d in manifest if r == "WarioWorldRecomp.exe"))
    if not args.no_source_zip:
        source = args.out / f"{name}-source.zip"
        subprocess.run(["git", "-C", str(ROOT), "archive", "--format=zip", f"--prefix=wario-world-recomp-{commit[:12]}/",
                        "-o", str(source), "HEAD"], check=True)
        report["source_zip"] = str(source)
    (args.out / f"{name}.json").write_text(json.dumps(dict(report, files_list=manifest), indent=1) + "\n",
                                          encoding="utf-8")
    shutil.rmtree(stage_root, ignore_errors=True)
    print(json.dumps(report, indent=2))
    print(f"Release check passed ({len(manifest)} files, no disc data) in {time.monotonic() - started:.0f} s; "
          f"{report['zip_bytes'] / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
