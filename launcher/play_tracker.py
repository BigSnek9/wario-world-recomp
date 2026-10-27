"""Background telemetry for manual playtest sessions (all private, no network).

While the game runs, PlayTracker:
- watches the disc file log (Logs/dolphin.log, FileMon channel) and records
  every stage archive (.RSC) load with its time -> stages.csv;
- ~25 s after an area's archive first loads in a session, asks the runner for a
  savestate through the automation folder -> states/<time>_<archive>.sav
  (one per area per session; used as hidden-test checkpoints);
- samples control/status.txt once a second -> perf.csv (speed, fps, vps);
- after the session, copies the memory-card save if it changed ->
  private/save-history/<time>.gci (the original is never modified).
Output: private/play-sessions/<UTC time>/.
"""
import csv
import hashlib
import shutil
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import texture_tools

STATE_DELAY = 25.0
SKIP_AREAS = {"03 Shared (UNIV)", "04 Shared bosses", "05 IGNITE", "06 UGP", "06 UGR"}


def _digest(path):
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


class PlayTracker:
    def __init__(self, root, user_dir, control_dir, data_dir=None, checkpoint_states=True):
        # data_dir holds play-sessions/ and save-history/ (default <root>/private). An installed copy
        # passes its own data folder and turns the per-area checkpoint savestates off.
        self.root, self.user, self.control = Path(root), Path(user_dir), Path(control_dir)
        self.data = Path(data_dir) if data_dir else self.root / "private"
        self.checkpoint_states = checkpoint_states
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.folder = self.data / "play-sessions" / stamp
        self.stop_event = threading.Event()
        self.thread = None
        self.save_before = {}

    def card_files(self):
        return sorted((self.user / "GC").rglob("*.gci"))

    def start(self):
        (self.folder / "states").mkdir(parents=True, exist_ok=True)
        texture_tools.set_disc_log(self.user, True)
        self.since = texture_tools.start_session(self.user)
        self.save_before = {p: _digest(p) for p in self.card_files()}
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=5)
        self._archive_saves()

    def _loop(self):
        log = self.user / "Logs/dolphin.log"
        seen_lines, areas_done, pending = 0, set(), []
        perf_path, stage_path = self.folder / "perf.csv", self.folder / "stages.csv"
        with perf_path.open("w", newline="", encoding="utf-8") as perf_file, \
                stage_path.open("w", newline="", encoding="utf-8") as stage_file:
            perf = csv.writer(perf_file)
            perf.writerow(["time", "state", "speed", "fps", "vps", "frame_count", "stage"])
            stages = csv.writer(stage_file)
            stages.writerow(["time", "archive", "area"])
            current = ""
            while not self.stop_event.wait(1.0):
                now = time.time()
                # Stage archive loads.
                for when, archive in texture_tools.archive_events(self.user, self.since)[seen_lines:]:
                    seen_lines += 1
                    area = texture_tools.area_for(archive)
                    stages.writerow([datetime.fromtimestamp(when).isoformat(timespec="seconds"), archive, area])
                    stage_file.flush()
                    if area not in SKIP_AREAS:
                        current = area
                        if self.checkpoint_states and area not in areas_done:
                            areas_done.add(area)
                            pending.append((now + STATE_DELAY, archive))
                # Delayed checkpoint savestates.
                for item in [p for p in pending if p[0] <= now]:
                    pending.remove(item)
                    self._request_state(item[1])
                # Performance sample.
                try:
                    status = dict(line.split("=", 1) for line in
                                  (self.control / "status.txt").read_text(encoding="utf-8").splitlines() if "=" in line)
                except (OSError, ValueError):
                    continue
                perf.writerow([datetime.fromtimestamp(now).isoformat(timespec="seconds"), status.get("state"),
                               status.get("speed"), status.get("fps"), status.get("vps"),
                               status.get("frame_count"), current])
                perf_file.flush()

    def _request_state(self, archive):
        name = datetime.now().strftime("%H%M%S") + "_" + Path(archive).stem
        target = self.folder / "states" / (name + ".sav")
        commands = self.control / "commands"
        commands.mkdir(parents=True, exist_ok=True)
        pending = self.control / "state.tmp"
        pending.write_text(f"command=save_state\npath={target}\n", encoding="utf-8")
        pending.replace(commands / f"{int(time.time() * 1000):016d}-state-{Path(archive).stem}.txt")

    def _archive_saves(self):
        history = self.data / "save-history"
        for path in self.card_files():
            if _digest(path) != self.save_before.get(path):
                history.mkdir(parents=True, exist_ok=True)
                stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
                shutil.copy2(path, history / f"{stamp}_{path.name}")
