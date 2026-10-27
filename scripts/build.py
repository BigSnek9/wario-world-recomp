"""Reproducible local build stages. Downloads happen only with the fetch stage."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config/project.json").read_text())
REPORTS = ROOT / "reports"
ORIGINAL = ROOT / "original/GWWE01"


def run(args, name, cwd=ROOT, env=None, allow_failure=False):
    REPORTS.mkdir(exist_ok=True)
    print(f"{name}: {' '.join(str(a) for a in args)}", flush=True)
    with (REPORTS / (name + ".log")).open("w", encoding="utf-8") as log:
        result = subprocess.run([str(a) for a in args], cwd=cwd, env=env,
                                stdout=log, stderr=subprocess.STDOUT)
    if result.returncode and not allow_failure:
        print((REPORTS / (name + ".log")).read_text(encoding="utf-8", errors="replace")[-10000:])
        raise SystemExit(f"{name} failed ({result.returncode}); see reports/{name}.log")
    return result.returncode


def executable(build, name):
    for path in (ROOT / "build" / build / "Release" / (name + ".exe"),
                 ROOT / "build" / build / (name + ".exe")):
        if path.is_file():
            return path
    raise SystemExit(f"Missing {name}; build the corresponding tool first")


def check_game():
    dol = ORIGINAL / "sys/main.dol"
    if not dol.is_file() or hashlib.sha256(dol.read_bytes()).hexdigest() != CONFIG["dol_sha256"]:
        raise SystemExit("Expected GWWE01 revision 0 DOL is absent or differs; run extract and audit")
    for relative, expected in CONFIG["rel_sha256"].items():
        path = ORIGINAL / relative
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise SystemExit(f"Original module differs or is absent: {relative}")


def fetch():
    for name, spec in CONFIG["upstream"].items():
        destination = ROOT / "third_party" / name
        if not (destination / ".git").exists():
            run(["git", "-c", "core.longpaths=true", "clone", "--no-checkout", spec["url"], destination], "fetch-" + name)
            run(["git", "checkout", "--detach", spec["commit"]], "checkout-" + name, cwd=destination)
        current = subprocess.check_output(["git", "-C", str(destination), "rev-parse", "HEAD"], text=True).strip()
        if current != spec["commit"]:
            raise SystemExit(f"{name}: found {current}, expected {spec['commit']}; refusing to reset existing work")
        run(["git", "-c", "core.longpaths=true", "submodule", "update", "--init", "--recursive", "--depth", "1"], "submodules-" + name, cwd=destination)
    run([sys.executable, ROOT / "scripts/apply_tool_fixes.py"], "apply-tool-fixes")


def configure(name, source, extra=()):
    build = ROOT / "build" / name
    build.mkdir(parents=True, exist_ok=True)
    if name == "moderngekko":
        (build / "Release").mkdir(exist_ok=True)
    run(["cmake", "-S", source, "-B", build, "-G", "Visual Studio 17 2022", "-A", "x64",
         "-DDOLRECOMP_ENABLE_LLVM=OFF", *extra], "configure-" + name)


def tools(jobs):
    run([sys.executable, ROOT / "scripts/apply_tool_fixes.py"], "apply-tool-fixes")
    run([sys.executable, ROOT / "scripts/verify_lockstep_boundary.py"], "test-lockstep-boundary")
    run([sys.executable, ROOT / "scripts/verify_float_compare.py"], "test-reference-float-compare")
    run([sys.executable, ROOT / "scripts/verify_fma.py"], "test-runtime-fma")
    configure("dolrecomp", ROOT / "third_party/DolRecomp")
    run(["cmake", "--build", ROOT / "build/dolrecomp", "--config", "Release", "--parallel", jobs], "build-dolrecomp")
    run(["ctest", "--test-dir", ROOT / "build/dolrecomp", "-C", "Release", "--output-on-failure"], "test-dolrecomp")
    configure("moderngekko", ROOT / "third_party/ModernGekko", [
        "-DBUILD_TESTING=OFF", "-DMODERNGEKKO_REQUIRED_DISC_ID=" + CONFIG["disc_id"],
        "-DMODERNGEKKO_REQUIRED_DOL_SHA256=" + CONFIG["dol_sha256"],
        "-DMODERNGEKKO_GAMECUBE_CONTROLLERS=ON",
        "-DMODERNGEKKO_DEFAULT_WINDOW_TITLE=Wario World Recomp"])
    run(["cmake", "--build", ROOT / "build/moderngekko", "--config", "Release", "--target",
         "moderngekko-port", "moderngekko-run", "--parallel", jobs], "build-runtime")


def extract(iso):
    if ORIGINAL.exists():
        raise SystemExit("original/GWWE01 already exists; refusing to overwrite original inputs")
    with iso.open("rb") as stream:
        actual = hashlib.file_digest(stream, "sha256").hexdigest()
    if actual != CONFIG["iso_sha256"]:
        raise SystemExit("Disc hash differs from pinned revision; audit the new dump before supporting it")
    run([executable("dolrecomp", "dolrecomp"), "extract", "--native-only", iso, ORIGINAL], "extract")


def audit(iso):
    args = [sys.executable, ROOT / "scripts/audit_game.py", "--iso", iso,
            "--extracted", ORIGINAL, "--out", REPORTS]
    if (REPORTS / "dtk-main-info.txt").is_file():
        args += ["--dtk-info", REPORTS / "dtk-main-info.txt"]
    run(args, "audit-game")


def translate(jobs):
    check_game()
    compiler = executable("dolrecomp", "dolrecomp")
    common = [compiler, "--gamecube", "--cpu", "gekko", "--backend", "c", "--semantics", "exact", "-j" + str(jobs)]
    run([*common, ORIGINAL / "sys/main.dol", ROOT / "generated/main"], "translate-main")
    run([*common, ORIGINAL / "files/dll", ROOT / "generated/rels"], "translate-rels")
    print("Translation complete. REL virtual bases are analysis assignments, not proven runtime load addresses.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["check", "fetch", "tools", "extract", "audit", "translate", "module-main"])
    parser.add_argument("--iso", type=Path)
    parser.add_argument("--jobs", type=int, default=8)
    parser.add_argument("--toolchain", choices=("msvc", "clang"), default="msvc",
                        help="module-main compiler (clang tolerates build paths over 260 characters; "
                             "needs clang on PATH and the MSVC x64 environment)")
    args = parser.parse_args()
    if args.jobs < 1:
        parser.error("--jobs must be positive")
    if args.stage == "check":
        for name in ("git", "cmake", "ctest", "ninja"):
            print(name, shutil.which(name) or "NOT FOUND")
        print("Python", sys.version.split()[0])
        print("Windows builds need Visual Studio 2022 C++ tools. Use an x64 developer prompt for module-main.")
    elif args.stage == "fetch":
        fetch()
    elif args.stage == "tools":
        tools(args.jobs)
    elif args.stage in ("extract", "audit"):
        if not args.iso:
            parser.error("--iso is required")
        (extract if args.stage == "extract" else audit)(args.iso.resolve())
    elif args.stage == "translate":
        translate(args.jobs)
    else:
        check_game()
        run([executable("moderngekko", "moderngekko-port"), "build", ORIGINAL,
             "--backend", "c", "--toolchain", args.toolchain, "--output", ROOT / "build/modules"], "build-module-main")
        # The upstream cache key omits local CPU-runtime source edits. Always let
        # CMake refresh those dependencies, then publish the newly linked DLL.
        for module_build in (ROOT / "build/modules" / CONFIG["disc_id"]).glob("*/module-build"):
            run(["cmake", "--build", module_build, "--parallel", str(args.jobs)], "refresh-module-main")
            linked = module_build / ("g" + CONFIG["disc_id"] + "_recomp.dll")
            if not linked.is_file():
                raise SystemExit("Expected linked Windows module is absent")
            shutil.copy2(linked, module_build.parent / linked.name)
        print("Main module compiled. This stage alone does not establish full REL coverage or accuracy.")


if __name__ == "__main__":
    main()
