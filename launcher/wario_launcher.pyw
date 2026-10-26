"""Minimal playtest launcher for the Wario World recomp (Tkinter, no extra installs).

Does what Play-WarioWorld.cmd does - installs default controls if missing,
reapplies the 4:3 / native 1x presentation baseline, then starts the runner
with the human playtest profile (private/playtest-user, saves preserved) - but
from a window with build/display choices, a live volume slider and log access.

Volume: the runner is started with --automation-dir private/launcher-control;
moving the slider while the game runs drops a `command=set_volume` file there
(scripts/tool_fix_volume_command.py adds that command to the runtime).

Textures: "Extract all textures" runs scripts/extract_textures.py, which reads
every texture straight from the extracted disc archives into
"Wario World/Extracted Textures/<area>/" with the names the HD loader expects.
"Use HD textures" loads replacements from
private/playtest-user/Load/Textures/GWWE01/ (any subfolders).
"""
import configparser
import json
import os
import subprocess
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "build/moderngekko/Release/moderngekko-run.exe"
GAME = ROOT / "original/GWWE01"
USER = ROOT / "private/playtest-user"
LOG = ROOT / "private/playtest-last.log"
SETTINGS = ROOT / "private/launcher.json"
CONTROL = ROOT / "private/launcher-control"
BUILDS = {
    # Clang + profile-guided optimisation; lockstep-validated 2026-10-26 (falls back to plain clang).
    "clang": ("Fast build (Clang, recommended)",
              next((p for p in (ROOT / "build/module-full-vectors-clang-pgo/gGWWE01_recomp.dll",
                                ROOT / "build/module-full-vectors-clang/gGWWE01_recomp.dll") if p.is_file()),
                   ROOT / "build/module-full-vectors-clang/gGWWE01_recomp.dll")),
    "msvc": ("Original build (MSVC, fallback)", ROOT / "build/module-full-vectors/Release/gGWWE01_recomp.dll"),
}
TEXTURE_OUT = ROOT.parent / "Extracted Textures"
EXTRACTOR = ROOT / "scripts/extract_textures.py"
NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
sys.path.insert(0, str(ROOT / "scripts"))
import texture_tools  # noqa: E402
sys.path.insert(0, str(ROOT / "launcher"))
from play_tracker import PlayTracker  # noqa: E402
import enhancements  # noqa: E402

AUTO = "Auto (match window) - default"
ORIGINAL_RES = "Original native 1x (accurate)"
ORIGINAL_ASPECT = "Original 4:3 (accurate)"
RESOLUTION_CHOICES = [AUTO, ORIGINAL_RES] + [label for label, _, scale in enhancements.RESOLUTIONS if scale > 1]
ASPECT_CHOICES = [AUTO, ORIGINAL_ASPECT] + [label for label, ratio in enhancements.ASPECTS if ratio]


def runner_supports_display_enhancements():
    """The aspect/auto-resolution support is a runtime change; older runners lack it."""
    try:
        return b"MODERNGEKKO_WARIO_ASPECT" in RUNNER.read_bytes()
    except OSError:
        return False


def python_console():
    # pythonw has no console; helper scripts are run with the console python
    # but without a window.
    exe = Path(sys.executable)
    candidate = exe.with_name("python.exe")
    return str(candidate if candidate.is_file() else exe)


TOOL_MODULES = ("numpy", "PIL", "xxhash")  # needed by scripts/extract_textures.py
_tool_python = None


def tool_python():
    """A console Python that can import the extractor's packages.

    Several Python installs can coexist; the one that started this launcher may
    lack them. Tries this interpreter first, then every python.exe on PATH."""
    global _tool_python
    if _tool_python:
        return _tool_python
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
                _tool_python = candidate
                return candidate
        except OSError:
            continue
    return None


def load_settings():
    try:
        return json.loads(SETTINGS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_settings(data):
    try:
        SETTINGS.parent.mkdir(exist_ok=True)
        SETTINGS.write_text(json.dumps(data, indent=1), encoding="utf-8")
    except OSError:
        pass


class Launcher(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Wario World Recomp - Launcher")
        self.resizable(False, False)
        settings = load_settings()
        self.process = None
        self.volume_job = None
        self.volume_serial = 0

        frame = tk.Frame(self, padx=14, pady=12)
        frame.pack()
        tk.Label(frame, text="Wario World Recomp (playtest)", font=("Segoe UI", 13, "bold")).pack(anchor="w")
        tk.Label(frame, text="Saves and controller settings: private/playtest-user", fg="gray").pack(anchor="w")

        tk.Label(frame, text="Build:").pack(anchor="w", pady=(10, 0))
        self.build = tk.StringVar(value=settings.get("build", "clang"))
        for key, (label, path) in BUILDS.items():
            button = tk.Radiobutton(frame, text=label, variable=self.build, value=key)
            if not path.is_file():
                button.configure(state="disabled", text=label + "  [not built]")
            button.pack(anchor="w")
        if not BUILDS[self.build.get()][1].is_file():
            self.build.set(next((k for k, (_, p) in BUILDS.items() if p.is_file()), "clang"))

        tk.Label(frame, text="Display:").pack(anchor="w", pady=(8, 0))
        self.display = tk.StringVar(value=settings.get("display", "opengl"))
        tk.Radiobutton(frame, text="OpenGL, SDR (default)", variable=self.display, value="opengl").pack(anchor="w")
        tk.Radiobutton(frame, text="Vulkan, SDR", variable=self.display, value="vulkan").pack(anchor="w")
        tk.Radiobutton(frame, text="Vulkan, HDR output (matches Dolphin with HDR on)", variable=self.display,
                       value="vulkan-hdr").pack(anchor="w")
        self.fullscreen = tk.BooleanVar(value=settings.get("fullscreen", False))
        tk.Checkbutton(frame, text="Fullscreen", variable=self.fullscreen).pack(anchor="w")
        tk.Label(frame, text="Resolution / aspect ratio (Auto follows the window or screen; "
                             "Original = accurate):", wraplength=340, justify="left").pack(anchor="w", pady=(8, 0))
        picker = tk.Frame(frame)
        picker.pack(anchor="w")
        self.resolution = tk.StringVar(value=settings.get("resolution", AUTO))
        if self.resolution.get() not in RESOLUTION_CHOICES:
            self.resolution.set(AUTO)
        self.aspect = tk.StringVar(value=settings.get("aspect", AUTO))
        if self.aspect.get() not in ASPECT_CHOICES:
            self.aspect.set(AUTO)
        tk.OptionMenu(picker, self.resolution, *RESOLUTION_CHOICES).pack(side="left")
        tk.OptionMenu(picker, self.aspect, *ASPECT_CHOICES).pack(side="left")
        self.hd = tk.BooleanVar(value=settings.get("hd_textures", False))
        tk.Checkbutton(frame, text="Use HD textures", variable=self.hd).pack(anchor="w")

        tk.Label(frame, text="Volume (changes live while playing):").pack(anchor="w", pady=(8, 0))
        self.volume = tk.IntVar(value=settings.get("volume", 100))
        tk.Scale(frame, from_=0, to=100, orient="horizontal", length=320, variable=self.volume,
                 command=self.volume_changed).pack(anchor="w")

        self.play = tk.Button(frame, text="PLAY", width=28, height=2, command=self.start)
        self.play.pack(pady=(12, 4))
        row = tk.Frame(frame)
        row.pack(fill="x")
        tk.Button(row, text="Open last log", command=self.open_log).pack(side="left", expand=True, fill="x")
        tk.Button(row, text="Controls help", command=self.controls).pack(side="left", expand=True, fill="x")
        row2 = tk.Frame(frame)
        row2.pack(fill="x")
        self.extract_button = tk.Button(row2, text="Extract all textures", command=self.extract)
        self.extract_button.pack(side="left", expand=True, fill="x")
        tk.Button(row2, text="Open extracted", command=lambda: self.open_folder(TEXTURE_OUT)).pack(
            side="left", expand=True, fill="x")
        tk.Button(row2, text="Open HD folder",
                  command=lambda: self.open_folder(texture_tools.hd_folder(USER))).pack(side="left", expand=True, fill="x")

        self.status = tk.StringVar(value="Ready.")
        tk.Label(frame, textvariable=self.status, anchor="w", justify="left", wraplength=340).pack(fill="x", pady=(10, 0))
        self.protocol("WM_DELETE_WINDOW", self.close)

    def set_status(self, text):
        self.after(0, self.status.set, text)

    def current_settings(self):
        return {"build": self.build.get(), "fullscreen": self.fullscreen.get(), "hd_textures": self.hd.get(),
                "display": self.display.get(), "volume": self.volume.get(),
                "resolution": self.resolution.get(), "aspect": self.aspect.get()}

    def volume_changed(self, _value):
        # Debounce slider drags; only the last value is sent.
        if self.volume_job:
            self.after_cancel(self.volume_job)
        self.volume_job = self.after(120, self.send_volume)

    def send_volume(self):
        self.volume_job = None
        save_settings(self.current_settings())
        if not (self.process and self.process.poll() is None):
            return
        self.volume_serial += 1
        commands = CONTROL / "commands"
        commands.mkdir(parents=True, exist_ok=True)
        pending = CONTROL / "volume.tmp"
        pending.write_text(f"command=set_volume\nvolume={self.volume.get()}\n", encoding="utf-8")
        # Command files run in name order; keep names unique and increasing.
        pending.replace(commands / f"{int(time.time() * 1000):016d}-{self.volume_serial:06d}-volume.txt")

    def start(self):
        module = BUILDS[self.build.get()][1]
        for path, what in ((RUNNER, "runtime"), (module, "game module"), (GAME / "sys/main.dol", "extracted game")):
            if not path.exists():
                messagebox.showerror("Missing file", f"The {what} is missing:\n{path}")
                return
        settings = self.current_settings()
        save_settings(settings)
        self.play.configure(state="disabled", text="Starting...")
        self.run_thread = threading.Thread(target=self.run, args=(module, settings), daemon=True)
        self.run_thread.start()

    def run(self, module, settings):
        try:
            USER.mkdir(parents=True, exist_ok=True)
            python = python_console()
            if not (USER / "Config/GCPadNew.ini").is_file():
                self.set_status("Installing default controller profile...")
                subprocess.run([python, str(ROOT / "scripts/configure_controls.py"), "--user-dir", str(USER)],
                               check=True, capture_output=True, creationflags=NO_WINDOW)
            self.set_status("Applying 4:3 / native presentation baseline...")
            subprocess.run([python, str(ROOT / "scripts/configure_baseline.py"), "--user-dir", str(USER)],
                           check=True, capture_output=True, creationflags=NO_WINDOW)
            config = configparser.ConfigParser(interpolation=None)
            config.read(USER / "config.ini", encoding="utf-8")
            if not config.has_section("Video"):
                config.add_section("Video")
            config.set("Video", "fullscreen", "true" if settings["fullscreen"] else "false")
            with (USER / "config.ini").open("w", encoding="utf-8") as stream:
                config.write(stream)

            # Resolution and aspect (enhancements.py). Original = the accurate baseline.
            if not runner_supports_display_enhancements():
                settings = dict(settings, resolution=ORIGINAL_RES, aspect=ORIGINAL_ASPECT)
            resolution_label, scale = "640x528", 1
            if settings["resolution"] == AUTO:
                resolution_label, scale = "auto", 0
            else:
                for label, text, value in enhancements.RESOLUTIONS:
                    if label == settings["resolution"]:
                        resolution_label, scale = text, value
            config.set("Video", "resolution", resolution_label)
            with (USER / "config.ini").open("w", encoding="utf-8") as stream:
                config.write(stream)
            texture_tools._set(USER / "Config/GFX.ini", {"Settings": {"InternalResolution": str(scale)}})
            aspect_env = None
            if settings["aspect"] == AUTO:
                aspect_env = "auto"
                texture_tools._set(USER / "Config/GFX.ini", {"Settings": {"AspectRatio": "3", "wideScreenHack": "False"}})
            elif settings["aspect"] == ORIGINAL_ASPECT:
                enhancements.apply_host_aspect(texture_tools._set, USER, None)
            else:
                ratio = dict(enhancements.ASPECTS)[settings["aspect"]]
                aspect_env = "%d:%d" % ratio
                enhancements.apply_host_aspect(texture_tools._set, USER, ratio)

            texture_tools.set_dump_mode(USER, False)  # old play-time dump mode is retired
            texture_tools.set_hd_mode(USER, settings["hd_textures"])
            # Same rendered image on every backend; HDR changes how it reaches an HDR display.
            texture_tools._set(USER / "Config/GFX.ini",
                               {"Enhancements": {"HDROutput": "True" if settings["display"] == "vulkan-hdr" else "False"}})
            texture_tools._set(USER / "Config/Dolphin.ini", {"DSP": {"Volume": str(settings["volume"])}})
            backend = "OpenGL" if settings["display"] == "opengl" else "Vulkan"

            # Fresh control folder each session so stale commands never replay.
            for sub in ("commands", "processed", "failed"):
                (CONTROL / sub).mkdir(parents=True, exist_ok=True)
                for stale in (CONTROL / sub).glob("*"):
                    stale.unlink()

            environment = dict(os.environ, MODERNGEKKO_STATICRECOMP="1")
            for name in ("STATICRECOMP_LOCKSTEP", "MODERNGEKKO_DUMP_TEXTURES", "MODERNGEKKO_WARIO_ASPECT"):
                environment.pop(name, None)
            if aspect_env:
                environment["MODERNGEKKO_WARIO_ASPECT"] = aspect_env
            tracker = PlayTracker(ROOT, USER, CONTROL)
            tracker.start()
            self.set_status(f"Running ({module.parent.name})... close the game window to return here.\n"
                            "Recording stage checkpoints and performance for Claude.")
            self.after(0, self.play.configure, {"text": "Game running"})
            with LOG.open("w", encoding="utf-8") as log:
                self.process = subprocess.Popen(
                    [str(RUNNER), "--game", str(GAME), "--module", str(module), "--user-dir", str(USER),
                     "--graphics", backend, "--no-mods", "--automation-dir", str(CONTROL),
                     "--title", "Wario World Recomp - Test Build"],
                    cwd=RUNNER.parent, stdout=log, stderr=subprocess.STDOUT, env=environment,
                    creationflags=NO_WINDOW)
                code = self.process.wait()
            if code != 0 and resolution_label == "auto" and "unsupported Dolphin internal resolution" in                     LOG.read_text(encoding="utf-8", errors="replace"):
                # Runtime built before auto-resolution support: retry at native.
                config.set("Video", "resolution", "640x528")
                with (USER / "config.ini").open("w", encoding="utf-8") as stream:
                    config.write(stream)
                with LOG.open("w", encoding="utf-8") as log:
                    self.process = subprocess.Popen(self.process.args, cwd=RUNNER.parent, stdout=log,
                                                    stderr=subprocess.STDOUT, env=environment,
                                                    creationflags=NO_WINDOW)
                    code = self.process.wait()
            self.process = None
            tracker.stop()
            self.set_status("Game closed normally." if code == 0 else
                            f"Game exited with code {code}. Use 'Open last log' and send it to Claude.")
        except subprocess.CalledProcessError as error:
            output = (error.stdout or b"").decode(errors="replace") + (error.stderr or b"").decode(errors="replace")
            self.set_status("Setup step failed:\n" + output[-600:])
        except Exception as error:  # surface anything to the window rather than dying silently
            self.set_status(f"Launch failed: {error}")
        finally:
            self.after(0, self.play.configure, {"state": "normal", "text": "PLAY"})

    def extract(self):
        if not EXTRACTOR.is_file():
            messagebox.showinfo("Not ready", "The texture extractor has not been installed yet.")
            return
        self.extract_button.configure(state="disabled", text="Extracting...")
        self.set_status("Extracting every texture from the game files (this takes a minute or two)...")
        threading.Thread(target=self.run_extract, daemon=True).start()

    def run_extract(self):
        try:
            python = tool_python()
            if python is None:
                self.set_status("Extraction needs the Python packages numpy, Pillow and xxhash. Install them with:\n"
                                "python -m pip install numpy pillow xxhash")
                return
            result = subprocess.run([python, str(EXTRACTOR), "--game", str(GAME), "--out", str(TEXTURE_OUT)],
                                    capture_output=True, text=True, creationflags=NO_WINDOW)
            tail = (result.stdout + result.stderr).strip().splitlines()[-3:]
            self.set_status(("Extraction finished: " if result.returncode == 0 else "Extraction failed: ")
                            + " | ".join(tail))
        except Exception as error:
            self.set_status(f"Extraction failed: {error}")
        finally:
            self.after(0, self.extract_button.configure, {"state": "normal", "text": "Extract all textures"})

    def open_folder(self, folder):
        Path(folder).mkdir(parents=True, exist_ok=True)
        os.startfile(folder)

    def open_log(self):
        if LOG.is_file():
            os.startfile(LOG)
        else:
            messagebox.showinfo("No log", "No game has been launched yet.")

    def controls(self):
        messagebox.showinfo("Controls", (
            "Xbox controller: A/B/X/Y as labelled, left stick = move, right stick = C-stick,\n"
            "Menu = Start, RB = Z, LT/RT = L/R.\n\n"
            "Keyboard: arrows = move, Enter = Start, X/Z = A/B, C/S/D = X/Y/Z,\n"
            "Q/W = L/R, I/J/K/L = C-stick, T/F/G/H = D-pad.\n\n"
            "Yes/No menus use the stick, not the D-pad."))

    def close(self):
        if self.process and self.process.poll() is None:
            if not messagebox.askyesno("Game running", "The game is still running.\n\n"
                                                        "Closing the launcher will also close the game.\n"
                                                        "Close both?"):
                return
            self.stop_game()
            # Let the session tracker finish (save-history copy, logs) before exiting.
            if getattr(self, "run_thread", None):
                self.run_thread.join(timeout=10)
        self.destroy()

    def stop_game(self):
        """Ask the runner to stop cleanly (saves/logs flush), then force it if needed."""
        process = self.process
        try:
            commands = CONTROL / "commands"
            commands.mkdir(parents=True, exist_ok=True)
            pending = CONTROL / "stop.tmp"
            pending.write_text("command=stop\n", encoding="utf-8")
            pending.replace(commands / f"{int(time.time() * 1000):016d}-999-stop.txt")
            process.wait(timeout=10)
        except Exception:
            pass
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except Exception:
                pass


if __name__ == "__main__":
    Launcher().mainloop()
