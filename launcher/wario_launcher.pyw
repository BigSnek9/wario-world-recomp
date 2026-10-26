"""Minimal playtest launcher for the Wario World recomp (Tkinter, no extra installs).

Does what Play-WarioWorld.cmd does - installs default controls if missing,
reapplies the 4:3 / native 1x presentation baseline, then starts the runner
with the human playtest profile (private/playtest-user, saves preserved) - but
from a window with a build choice, a fullscreen toggle and log access.

Texture tools (scripts/texture_tools.py): "Texture dump mode" saves every
texture the game uses while you play and, when the game closes, sorts the new
ones into "Wario World/Texture Dump/<area>/". "Use HD textures" loads
replacements from private/playtest-user/Load/Textures/GWWE01/ (any subfolders).
"""
import configparser
import json
import os
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "build/moderngekko/Release/moderngekko-run.exe"
GAME = ROOT / "original/GWWE01"
USER = ROOT / "private/playtest-user"
LOG = ROOT / "private/playtest-last.log"
SETTINGS = ROOT / "private/launcher.json"
BUILDS = {
    "clang": ("Fast build (Clang, recommended)", ROOT / "build/module-full-vectors-clang/gGWWE01_recomp.dll"),
    "msvc": ("Original build (MSVC, fallback)", ROOT / "build/module-full-vectors/Release/gGWWE01_recomp.dll"),
}
TEXTURE_OUT = ROOT.parent / "Texture Dump"
NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
sys.path.insert(0, str(ROOT / "scripts"))
import texture_tools  # noqa: E402


def python_console():
    # pythonw has no console; helper scripts are run with the console python
    # but without a window.
    exe = Path(sys.executable)
    candidate = exe.with_name("python.exe")
    return str(candidate if candidate.is_file() else exe)


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

        self.fullscreen = tk.BooleanVar(value=settings.get("fullscreen", False))
        tk.Checkbutton(frame, text="Fullscreen", variable=self.fullscreen).pack(anchor="w", pady=(8, 0))
        self.dump = tk.BooleanVar(value=settings.get("dump_textures", False))
        tk.Checkbutton(frame, text="Texture dump mode (saves textures as you play; a bit slower)",
                       variable=self.dump).pack(anchor="w")
        tk.Label(frame, text="Display:").pack(anchor="w", pady=(8, 0))
        self.display = tk.StringVar(value=settings.get("display", "opengl"))
        tk.Radiobutton(frame, text="OpenGL, SDR (default)", variable=self.display, value="opengl").pack(anchor="w")
        tk.Radiobutton(frame, text="Vulkan, SDR", variable=self.display, value="vulkan").pack(anchor="w")
        tk.Radiobutton(frame, text="Vulkan, HDR output (matches Dolphin with HDR on)", variable=self.display,
                       value="vulkan-hdr").pack(anchor="w")
        self.hd = tk.BooleanVar(value=settings.get("hd_textures", False))
        tk.Checkbutton(frame, text="Use HD textures", variable=self.hd).pack(anchor="w")

        self.play = tk.Button(frame, text="PLAY", width=28, height=2, command=self.start)
        self.play.pack(pady=(12, 4))
        row = tk.Frame(frame)
        row.pack(fill="x")
        tk.Button(row, text="Open last log", command=self.open_log).pack(side="left", expand=True, fill="x")
        tk.Button(row, text="Controls help", command=self.controls).pack(side="left", expand=True, fill="x")
        row2 = tk.Frame(frame)
        row2.pack(fill="x")
        tk.Button(row2, text="Open texture dump", command=lambda: self.open_folder(TEXTURE_OUT)).pack(
            side="left", expand=True, fill="x")
        tk.Button(row2, text="Open HD texture folder",
                  command=lambda: self.open_folder(texture_tools.hd_folder(USER))).pack(side="left", expand=True, fill="x")

        self.status = tk.StringVar(value="Ready.")
        tk.Label(frame, textvariable=self.status, anchor="w", justify="left", wraplength=320).pack(fill="x", pady=(10, 0))
        self.protocol("WM_DELETE_WINDOW", self.close)

    def set_status(self, text):
        self.after(0, self.status.set, text)

    def start(self):
        module = BUILDS[self.build.get()][1]
        for path, what in ((RUNNER, "runtime"), (module, "game module"), (GAME / "sys/main.dol", "extracted game")):
            if not path.exists():
                messagebox.showerror("Missing file", f"The {what} is missing:\n{path}")
                return
        save_settings({"build": self.build.get(), "fullscreen": self.fullscreen.get(),
                       "dump_textures": self.dump.get(), "hd_textures": self.hd.get(),
                       "display": self.display.get()})
        self.play.configure(state="disabled", text="Starting...")
        threading.Thread(target=self.run, args=(module, self.fullscreen.get(), self.dump.get(), self.hd.get(),
                                                         self.display.get()),
                         daemon=True).start()

    def run(self, module, fullscreen, dump, hd, display):
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
            config.set("Video", "fullscreen", "true" if fullscreen else "false")
            with (USER / "config.ini").open("w", encoding="utf-8") as stream:
                config.write(stream)

            texture_tools.set_dump_mode(USER, dump)
            texture_tools.set_hd_mode(USER, hd)
            # Same rendered image on every backend; HDR changes how it reaches an HDR display.
            texture_tools._set(USER / "Config/GFX.ini",
                               {"Enhancements": {"HDROutput": "True" if display == "vulkan-hdr" else "False"}})
            backend = "OpenGL" if display == "opengl" else "Vulkan"
            environment = dict(os.environ, MODERNGEKKO_STATICRECOMP="1")
            environment.pop("STATICRECOMP_LOCKSTEP", None)
            environment.pop("MODERNGEKKO_DUMP_TEXTURES", None)
            if dump:
                environment["MODERNGEKKO_DUMP_TEXTURES"] = "1"
                session_start = texture_tools.start_session(USER)
            self.set_status(f"Running ({module.parent.name})... close the game window to return here.")
            self.after(0, self.play.configure, {"text": "Game running"})
            with LOG.open("w", encoding="utf-8") as log:
                self.process = subprocess.Popen(
                    [str(RUNNER), "--game", str(GAME), "--module", str(module), "--user-dir", str(USER),
                     "--graphics", backend, "--no-mods", "--title", "Wario World Recomp - Test Build"],
                    cwd=RUNNER.parent, stdout=log, stderr=subprocess.STDOUT, env=environment,
                    creationflags=NO_WINDOW)
                code = self.process.wait()
            self.process = None
            message = ("Game closed normally." if code == 0 else
                       f"Game exited with code {code}. Use 'Open last log' and send it to Claude.")
            if dump:
                self.set_status(message + "\nSorting dumped textures...")
                moved, duplicates = texture_tools.organize(USER, TEXTURE_OUT, session_start)
                total = sum(1 for _ in TEXTURE_OUT.rglob("*.png"))
                message += f"\nTextures: {moved} new this session, {total} total in 'Texture Dump'."
            self.set_status(message)
        except subprocess.CalledProcessError as error:
            output = (error.stdout or b"").decode(errors="replace") + (error.stderr or b"").decode(errors="replace")
            self.set_status("Setup step failed:\n" + output[-600:])
        except Exception as error:  # surface anything to the window rather than dying silently
            self.set_status(f"Launch failed: {error}")
        finally:
            self.after(0, self.play.configure, {"state": "normal", "text": "PLAY"})

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
            if not messagebox.askyesno("Game running", "The game is still running. Close the launcher anyway?\n"
                                                        "(The game keeps running.)"):
                return
        self.destroy()


if __name__ == "__main__":
    Launcher().mainloop()
