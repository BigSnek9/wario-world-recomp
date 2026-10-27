"""Installer window (Tkinter): pick the ISO and a folder, check prerequisites, build and install."""
from __future__ import annotations

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


class App:
    def __init__(self, root, args):
        self.root = root
        self.events = queue.Queue()
        self.worker = None
        self.installer = None
        self.iso_ok = False
        self.prereqs_ok = False
        self.started = None
        root.title(TITLE)
        root.minsize(760, 640)
        root.protocol("WM_DELETE_WINDOW", self.close)

        self.iso = tk.StringVar(value=str(args.iso or ""))
        self.folder = tk.StringVar(value=str(args.install_dir or DEFAULT_DIR))
        self.desktop = tk.BooleanVar(value=True)
        self.start_menu = tk.BooleanVar(value=True)
        self.keep = tk.BooleanVar(value=bool(args.keep_build))
        self.work = tk.StringVar(value=str(args.work_dir or ""))
        self.jobs = args.jobs

        pad = dict(padx=10, pady=4)
        frame = ttk.Frame(root, padding=10)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(1, weight=1)
        ttk.Label(frame, text="Turns your Wario World disc into a PC game. You need your own dump of the "
                              "USA disc (GWWE01, revision 0) as an .iso.", wraplength=720).grid(
            row=0, column=0, columnspan=3, sticky="w", **pad)

        ttk.Label(frame, text="Game disc (.iso)").grid(row=1, column=0, sticky="w", **pad)
        ttk.Entry(frame, textvariable=self.iso).grid(row=1, column=1, sticky="ew", **pad)
        ttk.Button(frame, text="Browse...", command=self.pick_iso).grid(row=1, column=2, **pad)
        self.iso_status = ttk.Label(frame, text="Choose your .iso file.", foreground="gray")
        self.iso_status.grid(row=2, column=1, columnspan=2, sticky="w", padx=10)

        ttk.Label(frame, text="Install folder").grid(row=3, column=0, sticky="w", **pad)
        ttk.Entry(frame, textvariable=self.folder).grid(row=3, column=1, sticky="ew", **pad)
        ttk.Button(frame, text="Browse...", command=self.pick_folder).grid(row=3, column=2, **pad)
        self.folder_status = ttk.Label(frame, text="", foreground="gray")
        self.folder_status.grid(row=4, column=1, columnspan=2, sticky="w", padx=10)
        self.folder.trace_add("write", lambda *_: self.refresh_folder())

        options = ttk.Frame(frame)
        options.grid(row=5, column=1, columnspan=2, sticky="w", padx=6)
        ttk.Checkbutton(options, text="Desktop shortcut", variable=self.desktop).pack(side="left", padx=4)
        ttk.Checkbutton(options, text="Start menu shortcut", variable=self.start_menu).pack(side="left", padx=4)
        ttk.Checkbutton(options, text="Keep build files (about 3.5 GB; faster reinstall)",
                        variable=self.keep).pack(side="left", padx=4)

        ttk.Label(frame, text="Build files (optional)").grid(row=6, column=0, sticky="w", **pad)
        ttk.Entry(frame, textvariable=self.work).grid(row=6, column=1, sticky="ew", **pad)
        ttk.Button(frame, text="Browse...", command=self.pick_work).grid(row=6, column=2, **pad)
        ttk.Label(frame, text="Empty = automatic (build-files inside the install folder, or a short folder in "
                              "AppData if that path is too long); deleted when done unless kept.",
                  foreground="gray", wraplength=560).grid(row=7, column=1, columnspan=2, sticky="w", padx=10)
        self.work.trace_add("write", lambda *_: self.refresh_folder())

        self.prereq_box = ttk.LabelFrame(frame, text="Needed on this PC", padding=6)
        self.prereq_box.grid(row=8, column=0, columnspan=3, sticky="ew", **pad)
        self.prereq_box.columnconfigure(1, weight=1)

        buttons = ttk.Frame(frame)
        buttons.grid(row=9, column=0, columnspan=3, sticky="ew", **pad)
        self.install_button = ttk.Button(buttons, text="Install", command=self.start)
        self.install_button.pack(side="left")
        self.stop_button = ttk.Button(buttons, text="Stop", command=self.stop, state="disabled")
        self.stop_button.pack(side="left", padx=6)
        self.play_button = ttk.Button(buttons, text="Play", command=self.play, state="disabled")
        self.play_button.pack(side="left")
        self.open_button = ttk.Button(buttons, text="Open folder", command=self.open_folder)
        self.open_button.pack(side="left", padx=6)
        self.stage_label = ttk.Label(buttons, text="")
        self.stage_label.pack(side="left", padx=10)

        self.progress = ttk.Progressbar(frame, maximum=len(pipeline.STAGES))
        self.progress.grid(row=10, column=0, columnspan=3, sticky="ew", **pad)
        self.busy = ttk.Progressbar(frame, mode="indeterminate")
        self.busy.grid(row=11, column=0, columnspan=3, sticky="ew", padx=10)

        log_frame = ttk.Frame(frame)
        log_frame.grid(row=12, column=0, columnspan=3, sticky="nsew", **pad)
        frame.rowconfigure(12, weight=1)
        self.log_text = tk.Text(log_frame, height=14, wrap="none", state="disabled", font=("Consolas", 9))
        scroll = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scroll.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        ttk.Label(frame, text="Building takes 20-60 minutes. You can stop at any time and resume later "
                              "with the same install folder.", foreground="gray").grid(
            row=13, column=0, columnspan=3, sticky="w", padx=10)

        self.refresh_folder()
        self.check_prereqs()
        if self.iso.get():
            self.check_iso()
        root.after(100, self.poll)

    # ---------------------------------------------------------------- inputs
    def pick_iso(self):
        path = filedialog.askopenfilename(title="Your Wario World disc image",
                                          filetypes=[("GameCube disc image", "*.iso *.gcm"), ("All files", "*.*")])
        if path:
            self.iso.set(os.path.normpath(path))
            self.check_iso()

    def check_iso(self):
        path = self.iso.get().strip().strip('"')
        self.iso_ok = False
        self.iso_status.configure(text="Checking the disc...", foreground="gray")
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

    @property
    def work_dir(self):
        return self.work.get().strip().strip('"') or None

    def pick_work(self):
        path = filedialog.askdirectory(title="Folder for the build files", mustexist=False)
        if path:
            self.work.set(os.path.normpath(path))

    def work_folder(self):
        return Path(self.work_dir) if self.work_dir else pipeline.default_work_dir(self.folder.get().strip() or ".")

    def ours(self, folder):
        work = Path(self.work_dir) if self.work_dir else pipeline.default_work_dir(folder)
        return (folder / "install.json").is_file() or (work / pipeline.STATE_NAME).is_file()

    def resume_state(self):
        try:
            return pipeline.Installer(self.folder.get(), work_dir=self.work_dir).state()
        except (OSError, ValueError):
            return {"done": []}

    def refresh_folder(self):
        folder = Path(self.folder.get().strip() or ".")
        done = self.resume_state()["done"]
        if done and "cleanup" not in done:
            text = f"An unfinished install is here ({len(done)} of {len(pipeline.STAGES)} steps done); Install resumes it."
        elif (folder / "install.json").is_file():
            text = "Wario World Recomp is installed here; Install rebuilds it (your saves and settings are kept)."
        elif folder.is_dir() and any(folder.iterdir()):
            text = "This folder is not empty; choose an empty folder."
        else:
            text = "The game, its saves and settings all go in this folder."
        self.folder_status.configure(text=text)
        self.install_button.configure(text="Resume" if done and "cleanup" not in done else "Install")
        self.update_buttons()

    # ---------------------------------------------------------------- prerequisites
    def check_prereqs(self):
        for child in self.prereq_box.winfo_children():
            child.destroy()
        items = pipeline.check_prerequisites(self.work_folder())
        winget = pipeline.winget_available()
        for row, item in enumerate(items):
            status = "OK" if item["ok"] else ("Missing" if item["required"] else "Note")
            color = "green" if item["ok"] else ("red" if item["required"] else "darkorange")
            ttk.Label(self.prereq_box, text=status, foreground=color, width=8).grid(row=row, column=0, sticky="w")
            ttk.Label(self.prereq_box, text=f"{item['name']}: {item['detail']}", wraplength=470).grid(
                row=row, column=1, sticky="w")
            if not item["ok"] and item["url"]:
                ttk.Button(self.prereq_box, text="Download page",
                           command=lambda u=item["url"]: webbrowser.open(u)).grid(row=row, column=2, padx=2)
            if not item["ok"] and item["winget"] and winget:
                ttk.Button(self.prereq_box, text="Install with winget",
                           command=lambda i=item: self.winget(i)).grid(row=row, column=3, padx=2)
        ttk.Button(self.prereq_box, text="Check again", command=self.check_prereqs).grid(
            row=len(items), column=0, columnspan=2, sticky="w", pady=(6, 0))
        self.prereqs_ok = not pipeline.missing_required(items)
        self.update_buttons()

    def winget(self, item):
        command = "winget install -e --id " + " ".join(item["winget"])
        if messagebox.askyesno(TITLE, f"Install {item['name']} with winget?\n\n{command}\n\n"
                                      "A console window opens and Windows may ask for permission. "
                                      "Click 'Check again' when it has finished (Python, Git, CMake and "
                                      "LLVM may need this installer to be restarted)."):
            pipeline.run_winget(item["winget"])

    # ---------------------------------------------------------------- run
    def update_buttons(self):
        running = self.worker is not None and self.worker.is_alive()
        resumable = "extract" in self.resume_state()["done"]
        ready = self.prereqs_ok and (self.iso_ok or resumable) and self.folder.get().strip()
        self.install_button.configure(state="normal" if ready and not running else "disabled")
        self.stop_button.configure(state="normal" if running else "disabled")
        installed = (Path(self.folder.get()) / "install.json").is_file()
        self.play_button.configure(state="normal" if installed and not running else "disabled")

    def start(self):
        folder = Path(self.folder.get().strip())
        if folder.is_dir() and any(folder.iterdir()) and not self.ours(folder) and not self.work_dir:
            messagebox.showerror(TITLE, "The install folder is not empty. Choose an empty folder.")
            return
        self.installer = pipeline.Installer(
            folder, iso=self.iso.get().strip().strip('"') or None, work_dir=self.work_dir, jobs=self.jobs,
            desktop_shortcut=self.desktop.get(), start_menu_shortcut=self.start_menu.get(),
            keep_build=self.keep.get(), log=lambda line: self.events.put(("log", line)),
            progress=lambda i, key, title: self.events.put(("stage", (i, key, title))))
        self.started = time.monotonic()
        self.busy.start(12)

        def work():
            try:
                self.installer.execute()
                self.events.put(("finished", None))
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
        cmd = Path(self.folder.get()) / "Play Wario World.cmd"
        subprocess.Popen(["cmd", "/c", str(cmd)], creationflags=pipeline.NO_WINDOW)

    def open_folder(self):
        folder = Path(self.folder.get())
        if folder.is_dir():
            os.startfile(folder)

    def close(self):
        if self.worker and self.worker.is_alive():
            if not messagebox.askyesno(TITLE, "The install is still running. Stop it and close? "
                                              "You can resume it later."):
                return
            self.installer.cancel()
        self.root.destroy()

    # ---------------------------------------------------------------- events
    def append_log(self, line):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", line + "\n")
        if int(self.log_text.index("end-1c").split(".")[0]) > 5000:
            self.log_text.delete("1.0", "1000.0")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def poll(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "log":
                    self.append_log(value)
                elif kind == "iso_progress":
                    self.iso_status.configure(text=f"Checking the disc... {value:.0%}", foreground="gray")
                elif kind == "iso":
                    path, problem = value
                    if path != self.iso.get().strip().strip('"'):
                        continue
                    self.iso_ok = problem is None
                    self.iso_status.configure(text=problem or "OK: Wario World, USA (GWWE01), revision 0.",
                                              foreground="red" if problem else "green")
                    self.update_buttons()
                elif kind == "stage":
                    index, _key, title = value
                    self.progress["value"] = index
                    self.stage_label.configure(text=f"Step {min(index + 1, len(pipeline.STAGES))} of "
                                                    f"{len(pipeline.STAGES)}: {title}")
                elif kind in ("finished", "stopped", "failed"):
                    self.busy.stop()
                    self.worker = None
                    self.refresh_folder()
                    if kind == "finished":
                        self.progress["value"] = len(pipeline.STAGES)
                        self.stage_label.configure(text="Installed.")
                        messagebox.showinfo(TITLE, "Wario World Recomp is installed.\n\nStart it with the shortcut "
                                                   "or 'Play Wario World.cmd' in the install folder. Options are in "
                                                   "the in-game menu (Back on the controller, or Tab).")
                    elif kind == "stopped":
                        self.stage_label.configure(text="Stopped. Click Resume to continue.")
                    else:
                        self.stage_label.configure(text="Failed. Fix the problem, then click Resume.")
                        messagebox.showerror(TITLE, value + "\n\nThe full log is "
                                                            f"{self.work_folder() / 'reports/installer.log'}")
                    self.update_buttons()
        except queue.Empty:
            pass
        if self.worker and self.started:
            minutes = (time.monotonic() - self.started) / 60
            self.root.title(f"{TITLE} - {minutes:.0f} min")
        self.root.after(100, self.poll)


def run_gui(args):
    root = tk.Tk()
    try:
        ttk.Style().theme_use("vista")
    except tk.TclError:
        pass
    App(root, args)
    root.mainloop()
    return 0
