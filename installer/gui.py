"""Installer window (Tkinter): pick the ISO and a folder, then build and install.

Compact by design: prerequisites collapse to one line (details only when something is missing
or on request), the log is hidden until asked for or until an error. Light/dark theme follows
Windows by default; the choice is remembered in %LOCALAPPDATA%/WarioWorldRecomp/installer.json.
Build files always go to an automatic work folder that is deleted when the install finishes
(--work-dir / --keep-build remain as command-line options).
"""
from __future__ import annotations

import ctypes
import json
import os
import queue
import subprocess
import threading
import time
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import pipeline

TITLE = "Wario World Recomp - Installer"
DEFAULT_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Programs" / "Wario World Recomp"
SETTINGS = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "WarioWorldRecomp" / "installer.json"
CHECK = "✓"

THEMES = {
    "light": dict(bg="#f3f3f3", panel="#ffffff", fg="#1b1b1b", muted="#6b6b6b", border="#c8c8c8",
                  accent="#2f6fd6", accent_fg="#ffffff", button="#e6e6e6", button_active="#d8d8d8",
                  ok="#1f7a35", bad="#c42b1c", warn="#9a5b00", trough="#dddddd"),
    "dark": dict(bg="#202020", panel="#2b2b2b", fg="#ececec", muted="#9a9a9a", border="#454545",
                 accent="#4c8dff", accent_fg="#ffffff", button="#333333", button_active="#3d3d3d",
                 ok="#5fd27a", bad="#ff7b72", warn="#e3b341", trough="#3a3a3a"),
}


def windows_prefers_dark():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as key:
            return winreg.QueryValueEx(key, "AppsUseLightTheme")[0] == 0
    except OSError:
        return False


def load_settings():
    try:
        return json.loads(SETTINGS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_settings(values):
    try:
        SETTINGS.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS.write_text(json.dumps(values, indent=2) + "\n", encoding="utf-8")
    except OSError:
        pass


class App:
    def __init__(self, root, args):
        self.root = root
        self.events = queue.Queue()
        self.worker = None
        self.installer = None
        self.iso_ok = False
        self.prereq_items = []
        self.started = None
        self.work_dir, self.keep_build, self.jobs = args.work_dir, bool(args.keep_build), args.jobs
        self.settings = load_settings()
        self.dark = tk.BooleanVar(value=self.settings.get("theme", "dark" if windows_prefers_dark() else "light")
                                  == "dark")
        root.title(TITLE)
        root.resizable(True, True)
        self.scale = root.winfo_fpixels("1i") / 96  # 1.0 at 100 % Windows scaling
        root.minsize(int(560 * self.scale), 0)
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.style = ttk.Style(root)
        self.style.theme_use("clam")

        self.iso = tk.StringVar(value=str(args.iso or ""))
        self.folder = tk.StringVar(value=str(args.install_dir or DEFAULT_DIR))
        self.shortcuts = tk.BooleanVar(value=True)

        outer = ttk.Frame(root, padding=(16, 12, 16, 12))
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(1, weight=1)
        self.outer = outer

        head = ttk.Frame(outer)
        head.grid(row=0, column=0, columnspan=3, sticky="ew")
        ttk.Label(head, text="Wario World Recomp", style="Title.TLabel").pack(side="left")
        ttk.Checkbutton(head, text="Dark mode", variable=self.dark, command=self.toggle_theme,
                        style="Small.TCheckbutton").pack(side="right")
        ttk.Label(outer, text="Turns your Wario World disc (USA, GWWE01 rev 0) into a PC game.",
                  style="Muted.TLabel").grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, 10))

        ttk.Label(outer, text="Disc (.iso)").grid(row=2, column=0, sticky="w", padx=(0, 8))
        ttk.Entry(outer, textvariable=self.iso).grid(row=2, column=1, sticky="ew")
        ttk.Button(outer, text="Browse...", command=self.pick_iso).grid(row=2, column=2, padx=(6, 0))
        self.iso_status = ttk.Label(outer, text="Choose your disc image.", style="Muted.TLabel")
        self.iso_status.grid(row=3, column=1, columnspan=2, sticky="w", pady=(1, 6))

        ttk.Label(outer, text="Install to").grid(row=4, column=0, sticky="w", padx=(0, 8))
        ttk.Entry(outer, textvariable=self.folder).grid(row=4, column=1, sticky="ew")
        ttk.Button(outer, text="Browse...", command=self.pick_folder).grid(row=4, column=2, padx=(6, 0))
        self.folder_status = ttk.Label(outer, text="", style="Muted.TLabel")
        self.folder_status.grid(row=5, column=1, columnspan=2, sticky="w", pady=(1, 6))
        self.folder.trace_add("write", lambda *_: self.refresh_folder())

        ttk.Checkbutton(outer, text="Create shortcuts (desktop and Start menu)", variable=self.shortcuts).grid(
            row=6, column=1, columnspan=2, sticky="w", pady=(0, 6))

        prereq_line = ttk.Frame(outer)
        prereq_line.grid(row=7, column=0, columnspan=3, sticky="ew")
        self.prereq_status = ttk.Label(prereq_line, text="Checking what is needed...")
        self.prereq_status.pack(side="left")
        self.details_button = ttk.Button(prereq_line, text="Details", style="Link.TButton",
                                         command=self.toggle_details)
        self.details_button.pack(side="left", padx=(6, 0))
        self.details = ttk.Frame(outer, style="Panel.TFrame", padding=8)
        self.details.columnconfigure(1, weight=1)
        self.details_shown = False

        buttons = ttk.Frame(outer)
        buttons.grid(row=9, column=0, columnspan=3, sticky="ew", pady=(12, 6))
        self.install_button = ttk.Button(buttons, text="Install", style="Accent.TButton", command=self.start)
        self.install_button.pack(side="left")
        self.stop_button = ttk.Button(buttons, text="Stop", command=self.stop, state="disabled")
        self.stop_button.pack(side="left", padx=6)
        self.play_button = ttk.Button(buttons, text="Play", command=self.play, state="disabled")
        self.play_button.pack(side="left")
        self.log_button = ttk.Button(buttons, text="Show log", style="Link.TButton", command=self.toggle_log)
        self.log_button.pack(side="right")

        self.progress = ttk.Progressbar(outer, maximum=len(pipeline.STAGES))
        self.progress.grid(row=10, column=0, columnspan=3, sticky="ew")
        self.status = ttk.Label(outer, text="", style="Muted.TLabel")
        self.status.grid(row=11, column=0, columnspan=3, sticky="w", pady=(3, 0))

        self.log_frame = ttk.Frame(outer)
        self.log_text = tk.Text(self.log_frame, height=10, wrap="none", state="disabled", font=("Consolas", 9),
                                relief="flat", borderwidth=0, highlightthickness=1)
        scroll = ttk.Scrollbar(self.log_frame, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scroll.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.log_shown = False

        self.apply_theme()
        self.refresh_folder()
        self.check_prereqs()
        if self.iso.get():
            self.check_iso()
        root.after(100, self.poll)

    # ---------------------------------------------------------------- theme
    def apply_theme(self):
        c = THEMES["dark" if self.dark.get() else "light"]
        s = self.style
        self.root.configure(background=c["bg"])
        s.configure(".", background=c["bg"], foreground=c["fg"], bordercolor=c["border"], lightcolor=c["bg"],
                    darkcolor=c["bg"], troughcolor=c["trough"], focuscolor=c["accent"], font=("Segoe UI", 9),
                    fieldbackground=c["panel"], selectbackground=c["accent"], selectforeground=c["accent_fg"],
                    insertcolor=c["fg"])
        s.configure("TFrame", background=c["bg"])
        s.configure("Panel.TFrame", background=c["panel"], relief="solid", borderwidth=1)
        s.configure("TLabel", background=c["bg"], foreground=c["fg"])
        s.configure("Panel.TLabel", background=c["panel"], foreground=c["fg"])
        s.configure("Title.TLabel", font=("Segoe UI Semibold", 13))
        for name, color in (("Muted", c["muted"]), ("Ok", c["ok"]), ("Bad", c["bad"]), ("Warn", c["warn"])):
            s.configure(f"{name}.TLabel", background=c["bg"], foreground=color)
            s.configure(f"Panel{name}.TLabel", background=c["panel"], foreground=color)
        s.configure("TEntry", fieldbackground=c["panel"], foreground=c["fg"], bordercolor=c["border"],
                    lightcolor=c["panel"], darkcolor=c["panel"], padding=4)
        s.map("TEntry", bordercolor=[("focus", c["accent"])], lightcolor=[("focus", c["accent"])])
        s.configure("TButton", background=c["button"], foreground=c["fg"], bordercolor=c["border"],
                    lightcolor=c["button"], darkcolor=c["button"], padding=(10, 4), focusthickness=0)
        s.map("TButton", background=[("disabled", c["bg"]), ("active", c["button_active"])],
              foreground=[("disabled", c["muted"])], lightcolor=[("active", c["button_active"])],
              darkcolor=[("active", c["button_active"])])
        s.configure("Accent.TButton", background=c["accent"], foreground=c["accent_fg"], bordercolor=c["accent"],
                    lightcolor=c["accent"], darkcolor=c["accent"])
        s.map("Accent.TButton", background=[("disabled", c["button"]), ("active", c["accent"])],
              foreground=[("disabled", c["muted"])])
        s.configure("Link.TButton", background=c["bg"], foreground=c["accent"], bordercolor=c["bg"],
                    lightcolor=c["bg"], darkcolor=c["bg"], padding=(2, 0))
        s.map("Link.TButton", background=[("active", c["bg"])], lightcolor=[("active", c["bg"])],
              darkcolor=[("active", c["bg"])])
        s.configure("Small.TButton", padding=(6, 1))
        s.configure("TCheckbutton", background=c["bg"], foreground=c["fg"], indicatorbackground=c["panel"],
                    indicatorforeground=c["fg"], bordercolor=c["border"], upperbordercolor=c["border"],
                    lowerbordercolor=c["border"])
        s.map("TCheckbutton", background=[("active", c["bg"])],
              indicatorbackground=[("selected", c["accent"]), ("active", c["panel"])],
              indicatorforeground=[("selected", c["accent_fg"])])
        s.configure("Small.TCheckbutton", foreground=c["muted"])
        s.configure("Horizontal.TProgressbar", background=c["accent"], troughcolor=c["trough"],
                    bordercolor=c["trough"], lightcolor=c["accent"], darkcolor=c["accent"], thickness=8)
        s.configure("Vertical.TScrollbar", background=c["button"], troughcolor=c["bg"], bordercolor=c["bg"],
                    arrowcolor=c["muted"])
        self.log_text.configure(background=c["panel"], foreground=c["fg"], insertbackground=c["fg"],
                                highlightbackground=c["border"], highlightcolor=c["border"])
        self.dark_title_bar(self.dark.get())

    def dark_title_bar(self, dark):
        """DWMWA_USE_IMMERSIVE_DARK_MODE (20) on the window frame; ignored where unsupported."""
        try:
            self.root.update_idletasks()
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            value = ctypes.c_int(1 if dark else 0)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(value), ctypes.sizeof(value))
            # SWP_NOSIZE | SWP_NOMOVE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED: repaint the frame.
            ctypes.windll.user32.SetWindowPos(hwnd, None, 0, 0, 0, 0, 0x1 | 0x2 | 0x4 | 0x10 | 0x20)
        except (AttributeError, OSError):
            pass

    def toggle_theme(self):
        self.settings["theme"] = "dark" if self.dark.get() else "light"
        save_settings(self.settings)
        self.apply_theme()
        self.render_details()

    # ---------------------------------------------------------------- inputs
    def pick_iso(self):
        path = filedialog.askopenfilename(title="Your Wario World disc image",
                                          filetypes=[("GameCube disc image", "*.iso *.gcm"), ("All files", "*.*")])
        if path:
            self.iso.set(os.path.normpath(path))
            self.check_iso()

    def iso_path(self):
        return self.iso.get().strip().strip('"')

    def check_iso(self):
        path = self.iso_path()
        self.iso_ok = False
        self.iso_status.configure(text="Checking the disc...", style="Muted.TLabel")
        self.update_buttons()

        def work():
            try:
                problem = pipeline.verify_iso(path, progress=lambda f: self.events.put(("iso_progress", f)))
            except OSError as error:
                problem = str(error)
            self.events.put(("iso", (path, problem)))
        threading.Thread(target=work, daemon=True).start()

    def pick_folder(self):
        path = filedialog.askdirectory(title="Install Wario World Recomp to...", mustexist=False)
        if path:
            folder = Path(path)
            # A non-empty folder that is not ours gets its own subfolder.
            if folder.is_dir() and any(folder.iterdir()) and not self.ours(folder):
                folder = folder / "Wario World Recomp"
            self.folder.set(os.path.normpath(folder))

    def folder_path(self):
        return Path(self.folder.get().strip().strip('"') or ".")

    def work_folder(self, folder=None):
        return Path(self.work_dir) if self.work_dir else pipeline.default_work_dir(folder or self.folder_path())

    def ours(self, folder):
        return (folder / "install.json").is_file() or (self.work_folder(folder) / pipeline.STATE_NAME).is_file()

    def resume_state(self):
        try:
            return pipeline.Installer(self.folder_path(), work_dir=self.work_dir).state()
        except (OSError, ValueError):
            return {"done": []}

    def installed(self):
        return (self.folder_path() / "install.json").is_file()

    def refresh_folder(self):
        folder = self.folder_path()
        done = self.resume_state()["done"]
        if done and "cleanup" not in done:
            text = f"Unfinished install here ({len(done)} of {len(pipeline.STAGES)} steps); Install resumes it."
        elif self.installed():
            text = "Installed here. Choose the disc to rebuild it (saves are kept), or Update for the icon."
        elif folder.is_dir() and any(folder.iterdir()):
            text = "This folder is not empty; choose an empty folder."
        else:
            text = "The game, its saves and its settings all go here."
        self.folder_status.configure(text=text)
        self.update_buttons()

    # ---------------------------------------------------------------- prerequisites
    def check_prereqs(self):
        self.prereq_items = pipeline.check_prerequisites(self.work_folder())
        missing = pipeline.missing_required(self.prereq_items)
        if missing:
            self.prereq_status.configure(text="Missing: " + ", ".join(i["name"] for i in missing), style="Bad.TLabel")
            self.set_details(True)
        else:
            self.prereq_status.configure(text=f"Everything needed is installed {CHECK}", style="Ok.TLabel")
            self.render_details()
        self.update_buttons()

    def toggle_details(self):
        self.set_details(not self.details_shown)

    def set_details(self, shown):
        self.details_shown = shown
        self.details_button.configure(text="Hide details" if shown else "Details")
        if shown:
            self.details.grid(row=8, column=0, columnspan=3, sticky="ew", pady=(6, 0))
            self.render_details()
        else:
            self.details.grid_remove()

    def render_details(self):
        for child in self.details.winfo_children():
            child.destroy()
        winget = pipeline.winget_available()
        for row, item in enumerate(self.prereq_items):
            status, style = (CHECK, "PanelOk.TLabel") if item["ok"] else \
                (("Missing", "PanelBad.TLabel") if item["required"] else ("Note", "PanelWarn.TLabel"))
            ttk.Label(self.details, text=status, style=style, width=7).grid(row=row, column=0, sticky="w")
            ttk.Label(self.details, text=f"{item['name']}: {item['detail']}", style="Panel.TLabel",
                      wraplength=int(440 * self.scale)).grid(row=row, column=1, sticky="w")
            if not item["ok"] and item["url"]:
                ttk.Button(self.details, text="Download", style="Small.TButton",
                           command=lambda u=item["url"]: webbrowser.open(u)).grid(row=row, column=2, padx=2)
            if not item["ok"] and item["winget"] and winget:
                ttk.Button(self.details, text="winget", style="Small.TButton",
                           command=lambda i=item: self.winget(i)).grid(row=row, column=3, padx=2)
        ttk.Button(self.details, text="Check again", style="Small.TButton", command=self.check_prereqs).grid(
            row=len(self.prereq_items), column=0, columnspan=2, sticky="w", pady=(6, 0))

    def winget(self, item):
        command = "winget install -e --id " + " ".join(item["winget"])
        if messagebox.askyesno(TITLE, f"Install {item['name']} with winget?\n\n{command}\n\n"
                                      "A console window opens and Windows may ask for permission. "
                                      "Click 'Check again' when it has finished (Python, Git, CMake and "
                                      "LLVM may need this installer to be restarted)."):
            pipeline.run_winget(item["winget"])

    # ---------------------------------------------------------------- run
    def mode(self):
        """'update' (icon + shortcuts of an existing install) when no disc is chosen, else 'install'."""
        return "update" if self.installed() and not self.iso_path() and \
            "extract" not in self.resume_state()["done"] else "install"

    def update_buttons(self):
        if not hasattr(self, "install_button"):
            return
        running = self.worker is not None and self.worker.is_alive()
        state = self.resume_state()["done"]
        resumable = "extract" in state and "cleanup" not in state
        prereqs_ok = bool(self.prereq_items) and not pipeline.missing_required(self.prereq_items)
        if self.mode() == "update":
            self.install_button.configure(text="Update", state="disabled" if running else "normal")
        else:
            ready = prereqs_ok and (self.iso_ok or resumable)
            self.install_button.configure(text="Resume" if state and "cleanup" not in state else "Install",
                                          state="normal" if ready and not running else "disabled")
        self.stop_button.configure(state="normal" if running else "disabled")
        self.play_button.configure(state="normal" if self.installed() and not running else "disabled")

    def start(self):
        folder = self.folder_path()
        common = dict(desktop_shortcut=self.shortcuts.get(), start_menu_shortcut=self.shortcuts.get(),
                      log=lambda line: self.events.put(("log", line)),
                      progress=lambda i, key, title: self.events.put(("stage", (i, key, title))))
        if self.mode() == "update":
            self.installer = pipeline.Installer(folder, **common)
            job, done_event = self.installer.refresh, "refreshed"
        else:
            if folder.is_dir() and any(folder.iterdir()) and not self.ours(folder):
                messagebox.showerror(TITLE, "The install folder is not empty. Choose an empty folder.")
                return
            self.installer = pipeline.Installer(folder, iso=self.iso_path() or None, work_dir=self.work_dir,
                                                jobs=self.jobs, keep_build=self.keep_build, **common)
            job, done_event = self.installer.execute, "finished"
        self.started = time.monotonic()

        def work():
            try:
                job()
                self.events.put((done_event, None))
            except pipeline.Cancelled:
                self.events.put(("stopped", None))
            except pipeline.InstallError as error:
                self.events.put(("failed", str(error)))
            except Exception as error:  # surface anything in the window
                self.events.put(("failed", f"{type(error).__name__}: {error}"))
        self.worker = threading.Thread(target=work, daemon=True)
        self.worker.start()
        self.update_buttons()

    def stop(self):
        if self.installer and messagebox.askyesno(TITLE, "Stop the install? You can resume it later."):
            self.installer.cancel()

    def play(self):
        cmd = self.folder_path() / "Play Wario World.cmd"
        subprocess.Popen(["cmd", "/c", str(cmd)], creationflags=pipeline.NO_WINDOW)

    def close(self):
        if self.worker and self.worker.is_alive():
            if not messagebox.askyesno(TITLE, "The install is still running. Stop it and close? "
                                              "You can resume it later."):
                return
            self.installer.cancel()
        self.root.destroy()

    # ---------------------------------------------------------------- log
    def toggle_log(self):
        self.set_log(not self.log_shown)

    def set_log(self, shown):
        self.log_shown = shown
        self.log_button.configure(text="Hide log" if shown else "Show log")
        if shown:
            self.log_frame.grid(row=12, column=0, columnspan=3, sticky="nsew", pady=(8, 0))
            self.outer.rowconfigure(12, weight=1)
            self.log_text.see("end")
        else:
            self.log_frame.grid_remove()
            self.outer.rowconfigure(12, weight=0)

    def append_log(self, line):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", line + "\n")
        if int(self.log_text.index("end-1c").split(".")[0]) > 5000:
            self.log_text.delete("1.0", "1000.0")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    # ---------------------------------------------------------------- events
    def poll(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "log":
                    self.append_log(value)
                elif kind == "iso_progress":
                    self.iso_status.configure(text=f"Checking the disc... {value:.0%}", style="Muted.TLabel")
                elif kind == "iso":
                    path, problem = value
                    if path != self.iso_path():
                        continue
                    self.iso_ok = problem is None
                    self.iso_status.configure(text=problem or f"Wario World, USA (GWWE01), revision 0 {CHECK}",
                                              style="Bad.TLabel" if problem else "Ok.TLabel")
                    self.update_buttons()
                elif kind == "stage":
                    index, _key, title = value
                    self.progress["value"] = index
                    self.stage_title = f"Step {min(index + 1, len(pipeline.STAGES))} of {len(pipeline.STAGES)}: {title}"
                    self.status.configure(text=self.stage_title, style="TLabel")
                elif kind in ("finished", "refreshed", "stopped", "failed"):
                    self.worker = None
                    self.refresh_folder()
                    if kind == "finished":
                        self.progress["value"] = len(pipeline.STAGES)
                        self.status.configure(text=f"Installed {CHECK}  Start it with the shortcut or Play.",
                                              style="Ok.TLabel")
                    elif kind == "refreshed":
                        self.status.configure(text=f"Icon and shortcuts updated {CHECK}", style="Ok.TLabel")
                    elif kind == "stopped":
                        self.status.configure(text="Stopped. Click Resume to continue.", style="Muted.TLabel")
                    else:
                        self.status.configure(text="Failed: " + value.splitlines()[0][:90], style="Bad.TLabel")
                        self.set_log(True)
                    self.update_buttons()
        except queue.Empty:
            pass
        if self.worker and self.started and getattr(self, "stage_title", None):
            minutes = (time.monotonic() - self.started) / 60
            self.status.configure(text=f"{self.stage_title}  ({minutes:.0f} min)")
        self.root.after(250, self.poll)


def make_root():
    try:  # crisp text on scaled displays (Tk then sizes fonts for the monitor DPI)
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass
    return tk.Tk()


def run_gui(args):
    root = make_root()
    App(root, args)
    root.mainloop()
    return 0
