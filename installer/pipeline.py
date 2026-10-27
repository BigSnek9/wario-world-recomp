"""Install pipeline for the Wario World recomp: the user's GWWE01 rev 0 ISO -> a playable PC install.

Everything is built in a private work folder (default: <install>/build-files) that holds its own
copy of this project's scripts, so ROOT-relative scripts (scripts/build.py, build_rel_bundle.py...)
run there unchanged and never touch the checkout's own build/, generated/ or private/ folders.
Each finished stage is recorded in <work>/installer-state.json; running again resumes.

Nothing is installed system-wide. The only downloads are the pinned DolRecomp / ModernGekko
sources (config/project.json) fetched by `scripts/build.py fetch`.
"""
from __future__ import annotations

import ctypes
import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CONFIG = json.loads((REPO / "config/project.json").read_text(encoding="utf-8"))
DISC_ID = CONFIG["disc_id"]
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
BELOW_NORMAL = getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0)
STATE_NAME = "installer-state.json"
# Copied into the work folder; everything the build scripts read from their ROOT.
SOURCE_ITEMS = ("config", "launcher", "patches", "runtime", "scripts", "tools", "requirements.txt", "LICENSE")
# What the windowless starter imports or runs (launcher/wario_launcher.pyw).
STARTER_SCRIPTS = ("texture_tools.py", "configure_controls.py", "configure_baseline.py", "extract_textures.py")
MODULE_BUILD = "module-full-vectors-clang"  # build_rel_bundle.py --vectors --clean --clang (no PGO)
NEEDED_GB = 5.0  # build files (3.5 GB measured) plus the install (0.4 GB), with some headroom
REGIONS = {"E": "USA", "P": "Europe", "J": "Japan"}


class InstallError(Exception):
    pass


class Cancelled(InstallError):
    pass


# ---------------------------------------------------------------- disc check

def disc_header(path):
    """(game id, revision) from a GameCube disc header, or (None, None)."""
    try:
        with open(path, "rb") as stream:
            header = stream.read(0x20)
    except OSError:
        return None, None
    if len(header) < 0x20 or header[0x1C:0x20] != b"\xC2\x33\x9F\x3D":  # GameCube magic word
        return None, None
    return header[:6].decode("ascii", "replace"), header[7]


def sha256_file(path, progress=None, cancel=None):
    digest = hashlib.sha256()
    size = max(1, os.path.getsize(path))
    done = 0
    with open(path, "rb") as stream:
        while chunk := stream.read(8 << 20):
            if cancel is not None and cancel.is_set():
                raise Cancelled("Cancelled")
            digest.update(chunk)
            done += len(chunk)
            if progress:
                progress(done / size)
    return digest.hexdigest()


def verify_iso(path, progress=None, cancel=None):
    """Return None if the file is the pinned GWWE01 rev 0 disc, else a message for the user."""
    path = Path(path)
    if not path.is_file():
        return "The file does not exist."
    if path.suffix.lower() in (".rvz", ".wbfs", ".ciso", ".gcz", ".wia", ".nkit"):
        return ("This is a compressed disc image. Convert it to a plain .iso first "
                "(Dolphin: right-click the game > Convert File... > ISO).")
    game_id, revision = disc_header(path)
    if game_id is None:
        return "This is not a GameCube disc image (.iso)."
    if game_id[:3] != DISC_ID[:3]:
        return f"This disc is a different game ({game_id}). The installer needs Wario World, USA ({DISC_ID})."
    if game_id != DISC_ID:
        region = REGIONS.get(game_id[3], "another region")
        return (f"This is the {region} version of Wario World ({game_id}). "
                f"Only the USA version ({DISC_ID}, revision 0) is supported.")
    if revision != CONFIG["revision"]:
        return f"This is revision {revision} of {DISC_ID}. Only revision {CONFIG['revision']} is supported."
    if sha256_file(path, progress, cancel) != CONFIG["iso_sha256"]:
        return (f"This is {DISC_ID} revision 0, but the file differs from a clean dump "
                "(trimmed, modified, compressed or damaged). Please make a fresh 1:1 dump of your disc.")
    return None


# ---------------------------------------------------------------- prerequisites

def _program_files_x86():
    return Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))


def find_vcvars():
    """vcvars64.bat of a Visual Studio 2022 install with the x64 C++ tools (any edition)."""
    vswhere = _program_files_x86() / "Microsoft Visual Studio/Installer/vswhere.exe"
    candidates = []
    if vswhere.is_file():
        try:
            out = subprocess.run([str(vswhere), "-version", "[17.0,18.0)", "-products", "*", "-requires",
                                  "Microsoft.VisualStudio.Component.VC.Tools.x86.x64", "-property",
                                  "installationPath"], capture_output=True, text=True, creationflags=NO_WINDOW)
            candidates += [Path(line.strip()) for line in out.stdout.splitlines() if line.strip()]
        except OSError:
            pass
    # scripts/build_rel_bundle.py looks in these folders, so prefer them.
    for base in (_program_files_x86(), Path(os.environ.get("ProgramFiles", r"C:\Program Files"))):
        candidates += sorted((base / "Microsoft Visual Studio/2022").glob("*"))
    for folder in candidates:
        bat = folder / "VC/Auxiliary/Build/vcvars64.bat"
        if bat.is_file():
            return bat
    return None


_VS_ENV = {}


def vs_environment(vcvars):
    """The process environment after vcvars64.bat (cl, link, VS's bundled cmake/ninja on PATH)."""
    key = str(vcvars)
    if key not in _VS_ENV:
        out = subprocess.run(f'cmd /s /c ""{vcvars}" >nul 2>nul && set"', capture_output=True, text=True,
                             creationflags=NO_WINDOW, shell=False)
        env = {}
        for line in out.stdout.splitlines():
            name, sep, value = line.partition("=")
            if sep and name:
                env[name] = value
        if "VCToolsInstallDir" not in env:
            raise InstallError(f"Could not load the Visual Studio environment from {vcvars}")
        _VS_ENV[key] = env
    return dict(_VS_ENV[key])


def find_clang(env_path=None):
    candidates = [Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "LLVM/bin/clang-cl.exe"]
    found = shutil.which("clang-cl", path=env_path)
    if found:
        candidates.append(Path(found))
    for clang in candidates:
        if clang.is_file() and clang.with_name("lld-link.exe").is_file():
            return clang
    return None


def long_paths_enabled():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\FileSystem") as key:
            return winreg.QueryValueEx(key, "LongPathsEnabled")[0] == 1
    except OSError:
        return False


VS_WINGET = ("Microsoft.VisualStudio.2022.BuildTools", "--override",
             "--wait --passive --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended")


def check_prerequisites(work_dir=None):
    """List of dicts: name, ok, detail, url, winget (package arguments), required."""
    items = []

    def add(name, ok, detail, url=None, winget=None, required=True):
        items.append(dict(name=name, ok=bool(ok), detail=detail, url=url, winget=winget, required=required))

    version = ".".join(map(str, sys.version_info[:3]))
    add("Python 3.11 or newer", sys.version_info >= (3, 11), f"Python {version} ({sys.executable})",
        "https://www.python.org/downloads/windows/", ("Python.Python.3.12",))
    vcvars = find_vcvars()
    add("Visual Studio 2022 C++ build tools", vcvars,
        str(vcvars.parents[3]) if vcvars else "Not found (needs the 'Desktop development with C++' workload)",
        "https://visualstudio.microsoft.com/downloads/#build-tools-for-visual-studio-2022", VS_WINGET)
    env_path = os.environ.get("PATH", "")
    if vcvars:
        try:
            env_path = vs_environment(vcvars).get("Path") or vs_environment(vcvars).get("PATH") or env_path
        except InstallError:
            pass
    for name, label, url, package in (
            ("git", "Git", "https://git-scm.com/download/win", "Git.Git"),
            ("cmake", "CMake", "https://cmake.org/download/", "Kitware.CMake"),
            ("ninja", "Ninja", "https://github.com/ninja-build/ninja/releases", "Ninja-build.Ninja")):
        found = shutil.which(name, path=env_path)
        add(label, found, found or "Not found on PATH", url, (package,))
    clang = find_clang(env_path)
    add("LLVM / clang (clang-cl, lld-link)", clang, str(clang.parent) if clang else "Not found",
        "https://github.com/llvm/llvm-project/releases", ("LLVM.LLVM",))
    try:
        import tkinter  # noqa: F401  (only the window needs it)
        tk_ok = True
    except ImportError:
        tk_ok = False
    add("Tkinter (installer window)", tk_ok, "Included with the python.org installer" if tk_ok else
        "Missing; reinstall Python from python.org with 'tcl/tk and IDLE' ticked", required=False)
    texture_ok = all(_has_module(m) for m in ("numpy", "PIL", "xxhash"))
    add("numpy, pillow, xxhash (optional)", texture_ok,
        "Only for the in-game 'extract textures' tool" + ("" if texture_ok else
        f": {Path(sys.executable).name} -m pip install -r requirements.txt"), required=False)
    if work_dir:
        probe = Path(work_dir).resolve()
        while not probe.exists() and probe.parent != probe:
            probe = probe.parent
        free = shutil.disk_usage(probe).free / 1e9
        add(f"Free disk space ({NEEDED_GB:.0f} GB)", free >= NEEDED_GB, f"{free:.1f} GB free on {probe.anchor}",
            required=False)
        limit, length = max_work_path(), len(str(Path(work_dir).resolve()))
        add("Build folder path length", length <= limit, f"{length} characters (at most {limit}"
            + ("" if long_paths_enabled() else " because Windows long paths are off")
            + ")" + ("" if length <= limit else "; choose a short build folder such as C:\\WWBuild"))
    return items


def max_work_path():
    """Longest allowed build folder path. ModernGekko's MSVC objects reach ~150 characters below it and
    cl.exe stays limited to 260 even with Windows long paths on; with them off, the clang module's
    objects (which repeat the build path, ~2x+152) and Ninja also need to stay under 260."""
    return 100 if long_paths_enabled() else 50


def default_work_dir(install):
    """<install>/build-files, or a short folder in AppData when that path would be too long."""
    candidate = Path(install).resolve() / "build-files"
    if len(str(candidate)) <= max_work_path():
        return candidate
    return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "WWRecomp-build"


def _has_module(name):
    import importlib.util
    return importlib.util.find_spec(name) is not None


def missing_required(items):
    return [item for item in items if item["required"] and not item["ok"]]


def winget_available():
    return shutil.which("winget") is not None


def run_winget(package_args):
    """Open a visible console running winget for one package (only when the user asks for it)."""
    command = subprocess.list2cmdline(["winget", "install", "-e", "--id", *package_args])
    subprocess.Popen(f'start "winget" cmd /k {command}', shell=True)


# ---------------------------------------------------------------- pipeline

STAGES = (
    ("workspace", "Copy the build scripts"),
    ("fetch", "Download the pinned DolRecomp and ModernGekko sources"),
    ("toolfix", "Apply the project's tool fixes"),
    ("tools", "Build DolRecomp and the ModernGekko runtime"),
    ("extract", "Extract the game disc"),
    ("translate", "Translate the game code to C"),
    ("module-main", "Prepare the main game sources"),
    ("prepare", "Prepare the REL and vector sources"),
    ("module", "Build the game module (clang)"),
    ("install", "Copy the game into the install folder"),
    ("shortcuts", "Create shortcuts"),
    ("cleanup", "Remove the build files"),
)
STAGE_KEYS = [key for key, _ in STAGES]


class Installer:
    """Runs the stages. log(text) and progress(stage_index, stage_key, title) are callbacks."""

    def __init__(self, install_dir, iso=None, work_dir=None, extracted_game=None, jobs=None,
                 desktop_shortcut=False, start_menu_shortcut=False, shortcut_dir=None, keep_build=False,
                 log=print, progress=None):
        self.install = Path(install_dir).resolve()
        self.work = Path(work_dir).resolve() if work_dir else default_work_dir(self.install)
        self.iso = Path(iso).resolve() if iso else None
        self.extracted_game = Path(extracted_game).resolve() if extracted_game else None
        self.jobs = jobs or max(1, min(os.cpu_count() or 4, 8))
        self.desktop_shortcut, self.start_menu_shortcut = desktop_shortcut, start_menu_shortcut
        self.shortcut_dir = Path(shortcut_dir).resolve() if shortcut_dir else None
        self.keep_build = keep_build
        self._log, self._progress = log, progress or (lambda *a: None)
        self.cancel_event = threading.Event()
        self.process = None
        self.log_file = None
        self.clang = None
        self.vcvars = None

    # -- helpers
    def log(self, text):
        line = text.rstrip("\n")
        self._log(line)
        if self.log_file:
            self.log_file.write(line + "\n")
            self.log_file.flush()

    def state(self):
        try:
            return json.loads((self.work / STATE_NAME).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {"done": []}

    def save_state(self, state):
        self.work.mkdir(parents=True, exist_ok=True)
        temp = self.work / (STATE_NAME + ".tmp")
        temp.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        temp.replace(self.work / STATE_NAME)

    def cancel(self):
        self.cancel_event.set()
        process = self.process
        if process and process.poll() is None:
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(process.pid)], capture_output=True,
                           creationflags=NO_WINDOW)

    def env(self, vs=False):
        env = vs_environment(self.vcvars) if vs else dict(os.environ)
        if vs and self.clang:  # moderngekko-port's clang toolchain runs `clang` from PATH
            name = "Path" if "Path" in env else "PATH"
            env[name] = str(self.clang.parent) + os.pathsep + env.get(name, "")
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        return env

    def run(self, args, vs=False, cwd=None):
        if self.cancel_event.is_set():
            raise Cancelled("Cancelled")
        args = [str(a) for a in args]
        self.log("> " + subprocess.list2cmdline(args))
        self.process = subprocess.Popen(args, cwd=str(cwd or self.work), env=self.env(vs),
                                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                        creationflags=NO_WINDOW | BELOW_NORMAL)
        for raw in self.process.stdout:
            self.log("  " + raw.decode("utf-8", "replace").rstrip())
        code = self.process.wait()
        self.process = None
        if self.cancel_event.is_set():
            raise Cancelled("Cancelled")
        if code:
            raise InstallError(f"Command failed with exit code {code}. Logs: {self.work / 'reports'}")

    def python(self, script, *args, vs=False):
        self.run([python_console(), "-u", self.work / script, *args], vs=vs)

    # -- validation
    def validate(self):
        inside_repo = self.install == REPO or REPO in self.install.parents
        if inside_repo and (REPO / "private") not in self.install.parents:  # private/ is ignored scratch
            raise InstallError("Choose an install folder outside the project's source folder.")
        state = self.state()
        ours = (self.install / "install.json").is_file() or (self.work / STATE_NAME).is_file()
        if self.install.is_dir() and any(self.install.iterdir()) and not ours:
            raise InstallError(f"{self.install} is not empty. Choose an empty folder (or a previous install).")
        if "extract" not in state["done"] and not (self.iso or self.extracted_game):
            raise InstallError("The game disc (.iso) is needed.")
        missing = missing_required(check_prerequisites())
        if len(str(self.work)) > max_work_path():
            raise InstallError(f"The build files folder path is too long ({len(str(self.work))} characters, at most "
                               f"{max_work_path()}): {self.work}\nChoose a short build folder such as C:\\WWBuild.")
        if missing:
            raise InstallError("Missing prerequisites: " + ", ".join(item["name"] for item in missing))
        self.vcvars = find_vcvars()
        self.clang = find_clang(self.env(vs=True).get("Path") or self.env(vs=True).get("PATH"))

    # -- main
    def execute(self, restart_from=None):
        self.validate()
        self.work.mkdir(parents=True, exist_ok=True)
        (self.work / "reports").mkdir(exist_ok=True)
        self.log_file = (self.work / "reports/installer.log").open("a", encoding="utf-8")
        state = self.state()
        if restart_from:
            state["done"] = [k for k in state["done"] if STAGE_KEYS.index(k) < STAGE_KEYS.index(restart_from)]
        state.update(install=str(self.install), started=state.get("started") or _now())
        self.save_state(state)
        self.log(f"=== {_now()} install to {self.install} (build files: {self.work}, {self.jobs} jobs)")
        started = time.monotonic()
        try:
            for index, (key, title) in enumerate(STAGES):
                always = key in ("workspace",)
                if key in state["done"] and not always:
                    self.log(f"[{index + 1}/{len(STAGES)}] {title}: already done")
                    continue
                self._progress(index, key, title)
                self.log(f"[{index + 1}/{len(STAGES)}] {title}")
                stage_start = time.monotonic()
                getattr(self, "stage_" + key.replace("-", "_"))()
                if key == "cleanup":
                    break  # the state file went with the work folder
                state = self.state()
                if key not in state["done"]:
                    state["done"].append(key)
                state.setdefault("seconds", {})[key] = round(time.monotonic() - stage_start)
                self.save_state(state)
            self._progress(len(STAGES), "done", "Finished")
            self.log(f"=== Finished in {(time.monotonic() - started) / 60:.1f} min. Start the game with "
                     f"'{self.install / 'Play Wario World.cmd'}' or the shortcut.")
        finally:
            if self.log_file:
                self.log_file.close()
                self.log_file = None

    # -- stages
    def stage_workspace(self):
        for item in SOURCE_ITEMS:
            source = REPO / item
            target = self.work / item
            if source.is_dir():
                shutil.copytree(source, target, dirs_exist_ok=True,
                                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            elif source.is_file():
                shutil.copy2(source, target)
        commit = _git_commit(REPO)
        state = self.state()
        state["source_commit"] = commit
        self.save_state(state)
        self.log(f"  scripts from {REPO}" + (f" (commit {commit[:12]})" if commit else ""))

    def stage_fetch(self):
        # A clone interrupted before its pinned checkout is ours to redo (build.py refuses to reset it).
        for name, spec in CONFIG["upstream"].items():
            clone = self.work / "third_party" / name
            if clone.exists():
                head = subprocess.run(["git", "-C", str(clone), "rev-parse", "HEAD"], capture_output=True,
                                      text=True, creationflags=NO_WINDOW).stdout.strip()
                if head != spec["commit"]:
                    self.log(f"  removing incomplete clone {clone}")
                    _rmtree(clone)
        self.python("scripts/build.py", "fetch")

    def stage_toolfix(self):
        self.python("scripts/apply_tool_fixes.py")

    def stage_tools(self):
        self.python("scripts/build.py", "tools", "--jobs", self.jobs, vs=True)

    def stage_extract(self):
        target = self.work / "original" / DISC_ID
        if target.exists():
            _rmtree(target)  # a partial extraction from an interrupted run
        if self.extracted_game:
            self.log(f"  copying the extracted game from {self.extracted_game}")
            shutil.copytree(self.extracted_game, target)
        else:
            self.log("  checking the disc image (SHA-256)")
            problem = verify_iso(self.iso, cancel=self.cancel_event)
            if problem:
                raise InstallError(problem)
            self.python("scripts/build.py", "extract", "--iso", self.iso, vs=True)
        self.run([python_console(), "-c", "import sys; sys.path.insert(0, 'scripts'); import build; "
                  "build.check_game(); print('Extracted game matches the pinned GWWE01 rev 0 hashes')"])

    def stage_translate(self):
        self.python("scripts/build.py", "translate", "--jobs", self.jobs)

    def stage_module_main(self):
        # moderngekko-port translates the patched DOL (GameSettings patches applied) and compiles a
        # main-only module with Ninja.
        # Only its generated sources are used; clang (unlike cl.exe) copes with its long object paths.
        self.python("scripts/build.py", "module-main", "--jobs", self.jobs, "--toolchain", "clang", vs=True)

    def stage_prepare(self):
        self.python("scripts/prepare_rel_sources.py")
        self.python("scripts/prepare_vector_sources.py")

    def stage_module(self):
        self.python("scripts/build_rel_bundle.py", "--vectors", "--clean", "--clang", "--clang-cl",
                    self.clang.as_posix(), "--jobs", self.jobs, vs=True)

    def stage_install(self):
        work, dest = self.work, self.install
        runtime = work / "build/moderngekko/Release"
        module = work / "build" / MODULE_BUILD / "gGWWE01_recomp.dll"
        game = work / "original" / DISC_ID
        for path in (runtime / "moderngekko-run.exe", runtime / "Sys", module, game / "sys/main.dol"):
            if not path.exists():
                raise InstallError(f"Build output missing: {path}")
        dest.mkdir(parents=True, exist_ok=True)
        # Replace the program parts; user/ (saves, settings) and data/ are never removed.
        for name in ("runtime", "module", "game", "launcher", "scripts"):
            if (dest / name).exists():
                _rmtree(dest / name)
        self.log("  runtime")
        (dest / "runtime").mkdir()
        shutil.copy2(runtime / "moderngekko-run.exe", dest / "runtime")
        shutil.copytree(runtime / "Sys", dest / "runtime/Sys")
        self.log("  game module")
        (dest / "module").mkdir()
        shutil.copy2(module, dest / "module")
        self.log("  game files")
        shutil.copytree(game, dest / "game" / DISC_ID)
        self.log("  starter")
        shutil.copytree(work / "launcher", dest / "launcher", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        (dest / "scripts").mkdir()
        for name in STARTER_SCRIPTS:
            shutil.copy2(work / "scripts" / name, dest / "scripts")
        for name in ("LICENSE", "requirements.txt"):
            shutil.copy2(work / name, dest / name)
        (dest / "user").mkdir(exist_ok=True)
        (dest / "data").mkdir(exist_ok=True)
        pythonw = _pythonw()
        (dest / "Play Wario World.cmd").write_text(
            "@echo off\r\nrem Starts Wario World Recomp (options are in the in-game menu: Back / Tab).\r\n"
            f'set "PYW={pythonw}"\r\nif not exist "%PYW%" set "PYW=pythonw"\r\n'
            'start "" "%PYW%" "%~dp0launcher\\wario_launcher.pyw"\r\n', encoding="utf-8")
        state = self.state()
        (dest / "install.json").write_text(json.dumps(dict(
            layout="install", disc_id=DISC_ID, revision=CONFIG["revision"], dol_sha256=CONFIG["dol_sha256"],
            module=MODULE_BUILD + " (clang, no PGO)", source_commit=state.get("source_commit"),
            installed_utc=_now(), pythonw=str(pythonw),
            module_sha256=sha256_file(dest / "module/gGWWE01_recomp.dll")), indent=2) + "\n", encoding="utf-8")
        self.log(f"  installed {_size(dest, exclude=self.work):.2f} GB to {dest}")

    def stage_shortcuts(self):
        targets = []
        if self.shortcut_dir:
            targets.append(self.shortcut_dir)
        if self.desktop_shortcut:
            targets.append(Path(_known_folder("Desktop")))
        if self.start_menu_shortcut:
            targets.append(Path(_known_folder("Programs")))
        for folder in targets:
            link = folder / "Wario World Recomp.lnk"
            create_shortcut(link, _pythonw(), f'"{self.install / "launcher/wario_launcher.pyw"}"',
                            self.install, self.install / "runtime/moderngekko-run.exe")
            self.log(f"  {link}")
        if not targets:
            self.log("  none requested")

    def stage_cleanup(self):
        if self.keep_build:
            self.log(f"  kept {self.work} (delete it to free {_size(self.work):.1f} GB)")
            state = self.state()
            state["done"].append("cleanup")
            self.save_state(state)
            return
        if not (self.work / STATE_NAME).is_file() or self.work in (REPO, self.install) or self.work in REPO.parents:
            raise InstallError(f"Refusing to delete {self.work}")
        self.log(f"  deleting {self.work} ({_size(self.work):.1f} GB)")
        self.log_file.close()
        self.log_file = None
        shutil.copy2(self.work / "reports/installer.log", self.install / "data/installer.log")
        _rmtree(self.work)


# ---------------------------------------------------------------- utilities

def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _git_commit(folder):
    try:
        out = subprocess.run(["git", "-C", str(folder), "rev-parse", "HEAD"], capture_output=True, text=True,
                             creationflags=NO_WINDOW)
        return out.stdout.strip() or None
    except OSError:
        return None


def python_console():
    """python.exe even when the window runs under pythonw.exe. Build steps run in a hidden console
    (CREATE_NO_WINDOW) that the compilers inherit, so no console windows flash up."""
    exe = Path(sys.executable)
    candidate = exe.with_name("python.exe")
    return candidate if candidate.is_file() else exe


def _pythonw():
    exe = Path(sys.executable)
    candidate = exe.with_name("pythonw.exe")
    return candidate if candidate.is_file() else exe


def _rmtree(path):
    def retry(function, name, _info):
        os.chmod(name, 0o700)  # git objects are read-only
        function(name)
    shutil.rmtree(path, onexc=retry) if sys.version_info >= (3, 12) else shutil.rmtree(path, onerror=retry)


def _size(folder, exclude=None):
    total = 0
    for root, dirs, files in os.walk(folder):
        if exclude and Path(root) == Path(exclude).parent:
            dirs[:] = [d for d in dirs if Path(root, d) != Path(exclude)]
        for name in files:
            try:
                total += os.path.getsize(os.path.join(root, name))
            except OSError:
                pass
    return total / 1e9


def _known_folder(name):
    out = subprocess.run(["powershell", "-NoProfile", "-Command", f"[Environment]::GetFolderPath('{name}')"],
                         capture_output=True, text=True, creationflags=NO_WINDOW)
    path = out.stdout.strip()
    if not path:
        raise InstallError(f"Could not find the {name} folder")
    return path


def create_shortcut(link, target, arguments, working_dir, icon):
    link.parent.mkdir(parents=True, exist_ok=True)
    script = ("$s = (New-Object -ComObject WScript.Shell).CreateShortcut($env:WW_LINK); "
              "$s.TargetPath = $env:WW_TARGET; $s.Arguments = $env:WW_ARGS; $s.WorkingDirectory = $env:WW_DIR; "
              "$s.IconLocation = $env:WW_ICON + ',0'; $s.Description = 'Wario World Recomp'; $s.Save()")
    env = dict(os.environ, WW_LINK=str(link), WW_TARGET=str(target), WW_ARGS=arguments, WW_DIR=str(working_dir),
               WW_ICON=str(icon))
    result = subprocess.run(["powershell", "-NoProfile", "-Command", script], env=env, capture_output=True,
                            text=True, creationflags=NO_WINDOW)
    if result.returncode or not link.is_file():
        raise InstallError(f"Could not create the shortcut {link}: {result.stderr.strip()}")


def message_box(text, error=True):
    ctypes.windll.user32.MessageBoxW(None, text, "Wario World Recomp installer", 0x10 if error else 0x40)


# ---------------------------------------------------------------- command line

def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description="Build and install Wario World Recomp from your GWWE01 rev 0 ISO.")
    parser.add_argument("--no-gui", action="store_true", help="Run in this console instead of the window")
    parser.add_argument("--iso", type=Path, help="Your Wario World (USA, GWWE01 revision 0) .iso")
    parser.add_argument("--install-dir", type=Path, help="Where to install the game (any folder)")
    parser.add_argument("--work-dir", type=Path, help="Build files folder (default: <install>/build-files)")
    parser.add_argument("--extracted-game", type=Path,
                        help="Use an already extracted GWWE01 folder (hash-checked) instead of the ISO")
    parser.add_argument("--jobs", type=int, help="Parallel compile jobs (default: CPU count, at most 8)")
    parser.add_argument("--desktop-shortcut", action="store_true")
    parser.add_argument("--start-menu-shortcut", action="store_true")
    parser.add_argument("--shortcut-dir", type=Path, help="Also put a shortcut in this folder")
    parser.add_argument("--keep-build", action="store_true", help="Keep the build files (faster reinstall)")
    parser.add_argument("--restart-from", choices=STAGE_KEYS, help="Redo this stage and the ones after it")
    parser.add_argument("--check", action="store_true", help="Only check the prerequisites (and the ISO, if given)")
    args = parser.parse_args(argv)
    if not args.no_gui and not args.check:
        from gui import run_gui
        return run_gui(args)
    items = check_prerequisites(args.work_dir or (default_work_dir(args.install_dir) if args.install_dir else None))
    for item in items:
        print(f"{'OK     ' if item['ok'] else ('MISSING' if item['required'] else 'note   ')} {item['name']}: "
              f"{item['detail']}" + ("" if item["ok"] or not item["url"] else f"  -> {item['url']}"))
    if args.iso:
        problem = verify_iso(args.iso)
        print("ISO: " + (problem or f"OK, {DISC_ID} revision 0"))
        if problem:
            return 2
    if args.check:
        return 1 if missing_required(items) else 0
    if not args.install_dir:
        parser.error("--install-dir is required")
    if args.iso and args.extracted_game:
        parser.error("use --iso or --extracted-game, not both")
    installer = Installer(args.install_dir, args.iso, args.work_dir, args.extracted_game, args.jobs,
                          args.desktop_shortcut, args.start_menu_shortcut, args.shortcut_dir, args.keep_build)
    try:
        installer.execute(args.restart_from)
    except KeyboardInterrupt:
        installer.cancel()
        print("Stopped. Run the same command again to resume.")
        return 1
    except InstallError as error:
        print(f"ERROR: {error}\nRun the same command again to resume after fixing it.")
        return 1
    return 0
