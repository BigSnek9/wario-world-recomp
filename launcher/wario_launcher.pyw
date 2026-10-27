"""Windowless starter for the Wario World recomp (no extra installs).

Double-click Launch-WarioWorld.cmd (or Play-WarioWorld.cmd): the game starts straight away with
the human playtest profile (private/playtest-user, saves preserved). Every option lives in the
in-game menu (Back on the controller, or Tab), saved in <user>/Config/WarioWorld.ini.

What this starter still does around the runner:
- installs the default controller profile if missing and reapplies the 4:3 / native presentation
  baseline (the menu then applies the player's own display settings live);
- starts the runner with the clang PGO module and the graphics backend from WarioWorld.ini
  (`backend=opengl|vulkan`; the menu's "Restart now" leaves <user>/Config/WarioWorld.restart and
  quits, and the runner is started again with the new backend);
- gives the menu its tool hooks as environment variables: MODERNGEKKO_WARIO_EXTRACT_CMD (texture
  extraction command line, scripts/extract_textures.py into "Wario World/Extracted Textures"),
  MODERNGEKKO_WARIO_EXTRACTED_DIR and MODERNGEKKO_WARIO_LOG;
- runs the play tracker (stage checkpoints, savestates, performance samples for Claude) and keeps
  the runner output in private/playtest-last.log.
Errors are shown in a message box.
"""
import configparser
import ctypes
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "build/moderngekko/Release/moderngekko-run.exe"
GAME = ROOT / "original/GWWE01"
USER = ROOT / "private/playtest-user"
LOG = ROOT / "private/playtest-last.log"
OLD_SETTINGS = ROOT / "private/launcher.json"
CONTROL = ROOT / "private/launcher-control"
MODULES = (ROOT / "build/module-full-vectors-clang-pgo/gGWWE01_recomp.dll",
           ROOT / "build/module-full-vectors-clang/gGWWE01_recomp.dll")
MENU_SETTINGS = USER / "Config/WarioWorld.ini"
RESTART_MARKER = USER / "Config/WarioWorld.restart"
TEXTURE_OUT = ROOT.parent / "Extracted Textures"
EXTRACTOR = ROOT / "scripts/extract_textures.py"
NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
TITLE = "Wario World Recomp"
sys.path.insert(0, str(ROOT / "scripts"))
import texture_tools  # noqa: E402
sys.path.insert(0, str(ROOT / "launcher"))
from play_tracker import PlayTracker  # noqa: E402

TOOL_MODULES = ("numpy", "PIL", "xxhash")  # needed by scripts/extract_textures.py


def message(text, error=True):
    ctypes.windll.user32.MessageBoxW(None, text, TITLE, 0x10 if error else 0x40)


def python_console():
    # pythonw has no console; helper scripts run with the console python but without a window.
    exe = Path(sys.executable)
    candidate = exe.with_name("python.exe")
    return str(candidate if candidate.is_file() else exe)


def tool_python():
    """A console Python that can import the extractor's packages (several installs may coexist)."""
    candidates = [python_console()]
    try:
        found = subprocess.run(["where", "python"], capture_output=True, text=True, creationflags=NO_WINDOW)
        candidates += [line.strip() for line in found.stdout.splitlines() if line.strip().lower().endswith(".exe")]
    except OSError:
        pass
    probe = "import importlib.util as u, sys; sys.exit(0 if all(u.find_spec(m) for m in %r) else 1)" % (TOOL_MODULES,)
    for candidate in dict.fromkeys(candidates):
        if "WindowsApps" in candidate:  # Microsoft Store alias stub
            continue
        try:
            if subprocess.run([candidate, "-c", probe], capture_output=True, creationflags=NO_WINDOW).returncode == 0:
                return candidate
        except OSError:
            continue
    return None


def read_menu_settings():
    values = {}
    try:
        for line in MENU_SETTINGS.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip()
    except OSError:
        pass
    return values


def migrate_backend(menu):
    """The backend used to be a launcher choice (private/launcher.json); carry it over once."""
    if menu.get("backend") in ("opengl", "vulkan"):
        return menu["backend"]
    try:
        display = json.loads(OLD_SETTINGS.read_text(encoding="utf-8")).get("display", "opengl")
    except (OSError, ValueError):
        display = "opengl"
    backend = "vulkan" if str(display).startswith("vulkan") else "opengl"
    MENU_SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    existing = MENU_SETTINGS.read_text(encoding="utf-8") if MENU_SETTINGS.is_file() else \
        "# Wario World in-game menu settings (Back / Tab in game)\n"
    MENU_SETTINGS.write_text(existing.rstrip("\n") + f"\nbackend={backend}\n", encoding="utf-8")
    return backend


def prepare():
    USER.mkdir(parents=True, exist_ok=True)
    python = python_console()
    if not (USER / "Config/GCPadNew.ini").is_file():
        subprocess.run([python, str(ROOT / "scripts/configure_controls.py"), "--user-dir", str(USER)],
                       check=True, capture_output=True, creationflags=NO_WINDOW)
    subprocess.run([python, str(ROOT / "scripts/configure_baseline.py"), "--user-dir", str(USER)],
                   check=True, capture_output=True, creationflags=NO_WINDOW)
    menu = read_menu_settings()
    config = configparser.ConfigParser(interpolation=None)
    config.read(USER / "config.ini", encoding="utf-8")
    if not config.has_section("Video"):
        config.add_section("Video")
    # Startup only; the in-game menu toggles fullscreen live and applies the rest itself.
    config.set("Video", "fullscreen", "true" if menu.get("fullscreen") == "1" else "false")
    config.set("Video", "resolution", "auto")
    with (USER / "config.ini").open("w", encoding="utf-8") as stream:
        config.write(stream)
    texture_tools.set_dump_mode(USER, False)  # old play-time dump mode is retired
    texture_tools.hd_folder(USER).mkdir(parents=True, exist_ok=True)
    # Interpolated frames are presented between VI swaps; a 60 Hz VSync wait would stall them.
    texture_tools._set(USER / "Config/GFX.ini", {"Hardware": {"VSync": "False"}})


def environment():
    env = dict(os.environ, MODERNGEKKO_STATICRECOMP="1")
    for name in ("STATICRECOMP_LOCKSTEP", "MODERNGEKKO_DUMP_TEXTURES", "MODERNGEKKO_WARIO_ASPECT",
                 "MODERNGEKKO_WARIO_FPS"):
        env.pop(name, None)
    env["MODERNGEKKO_WARIO_LOG"] = str(LOG)
    env["MODERNGEKKO_WARIO_EXTRACTED_DIR"] = str(TEXTURE_OUT)
    python = tool_python() if EXTRACTOR.is_file() else None
    if python:
        env["MODERNGEKKO_WARIO_EXTRACT_CMD"] = subprocess.list2cmdline(
            [python, str(EXTRACTOR), "--game", str(GAME), "--out", str(TEXTURE_OUT)])
    return env


def run_once(module, env):
    menu = read_menu_settings()
    backend = "Vulkan" if migrate_backend(menu) == "vulkan" else "OpenGL"
    # Performance mode (menu, applies after "Restart now"): Dolphin's dual core, the GPU emulation
    # on its own thread. Off = the accurate single-thread default.
    texture_tools._set(USER / "Config/Dolphin.ini",
                       {"Core": {"CPUThread": "True" if menu.get("performance") == "1" else "False"}})
    # Fresh control folder each session so stale commands never replay.
    for sub in ("commands", "processed", "failed"):
        (CONTROL / sub).mkdir(parents=True, exist_ok=True)
        for stale in (CONTROL / sub).glob("*"):
            stale.unlink()
    tracker = PlayTracker(ROOT, USER, CONTROL)
    tracker.start()
    # Frame-timing evidence for Claude in the play-session folder: frame generation stats and a
    # per-event pacing trace (a few MB per hour), so slowdowns on the real screen can be diagnosed.
    env = dict(env, MODERNGEKKO_WARIO_FPS_STATS=str(tracker.folder / "fps-stats.txt"),
               MODERNGEKKO_WARIO_FPS_TRACE=str(tracker.folder / "pacing-trace.txt"))
    try:
        with LOG.open("w", encoding="utf-8") as log:
            process = subprocess.Popen(
                [str(RUNNER), "--game", str(GAME), "--module", str(module), "--user-dir", str(USER),
                 "--graphics", backend, "--no-mods", "--automation-dir", str(CONTROL),
                 "--title", "Wario World Recomp - Test Build"],
                cwd=RUNNER.parent, stdout=log, stderr=subprocess.STDOUT, env=env, creationflags=NO_WINDOW)
            return process.wait()
    finally:
        tracker.stop()


def main():
    # One starter at a time (a second double-click while playing does nothing).
    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "WarioWorldRecompStarter")
    if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        return
    module = next((path for path in MODULES if path.is_file()), MODULES[0])
    for path, what in ((RUNNER, "runtime"), (module, "game module"), (GAME / "sys/main.dol", "extracted game")):
        if not path.exists():
            message(f"The {what} is missing:\n{path}")
            return
    try:
        prepare()
    except subprocess.CalledProcessError as error:
        output = (error.stdout or b"").decode(errors="replace") + (error.stderr or b"").decode(errors="replace")
        message("A setup step failed:\n\n" + output[-800:])
        return
    env = environment()
    while True:
        RESTART_MARKER.unlink(missing_ok=True)
        code = run_once(module, env)
        if RESTART_MARKER.is_file():
            continue  # "Restart now" in the menu (e.g. a new graphics backend)
        if code != 0:
            message(f"The game exited with code {code}.\n\nThe log is in:\n{LOG}\n\nPlease send it to Claude.")
        break
    ctypes.windll.kernel32.CloseHandle(mutex)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:  # no console: surface anything rather than dying silently
        message(f"Starting the game failed:\n\n{error}")
