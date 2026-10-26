"""Tiny live cheats window (temporary; to be folded into the launcher later).

Moon jump: while the jump button (Xbox A on any controller, or keyboard X which
the default profile maps to GameCube A) is held, Wario's height is raised
through the running game's automation folder (write_memory) about 20 times a
second. Uses the player pointer 0x801FDA00 and position +0x14 (x, y, z)
documented in docs/research/FUNCTION_DATABASE.json (G-0001). Works on a game
started by the launcher (which passes --automation-dir private/launcher-control);
no restart needed. Changes game memory - not for accuracy testing.

Usage: double-click, or `pythonw launcher/cheats.pyw [--control DIR]`.
Test hook: --simulate-hold START SECONDS presses "jump" without a controller.
"""
import argparse
import ctypes
import struct
import threading
import time
import tkinter as tk
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAYER_POINTER = 0x801C5820  # live player actor (found 2026-10-26; 0x801FDA00 is a follower copy)
POSITION_Y = 0x18          # player + 0x14 = x, +0x18 = y (up), +0x1C = z
RISE_PER_TICK = 2.0        # default world units per ~50 ms command poll (~40 units/s); slider in the window
XINPUT_A = 0x1000
VK_X = 0x58


class XInputGamepad(ctypes.Structure):
    _fields_ = [("buttons", ctypes.c_ushort), ("lt", ctypes.c_ubyte), ("rt", ctypes.c_ubyte),
                ("lx", ctypes.c_short), ("ly", ctypes.c_short), ("rx", ctypes.c_short), ("ry", ctypes.c_short)]


class XInputState(ctypes.Structure):
    _fields_ = [("packet", ctypes.c_uint), ("gamepad", XInputGamepad)]


def load_xinput():
    for name in ("xinput1_4", "xinput1_3", "xinput9_1_0"):
        try:
            return getattr(ctypes.windll, name)
        except OSError:
            continue
    return None


class Cheats:
    def __init__(self, control, simulate=None):
        self.control = Path(control)
        self.xinput = load_xinput()
        self.simulate = simulate
        self.started = time.time()
        self.serial = 0
        self.enabled = True
        self.rise = RISE_PER_TICK
        self.status = "Waiting for jump..."

    def jump_held(self):
        if self.simulate:
            start, seconds = self.simulate
            return start <= time.time() - self.started < start + seconds
        if ctypes.windll.user32.GetAsyncKeyState(VK_X) & 0x8000:
            return True
        if self.xinput:
            state = XInputState()
            for pad in range(4):
                if self.xinput.XInputGetState(pad, ctypes.byref(state)) == 0 and state.gamepad.buttons & XINPUT_A:
                    return True
        return False

    def send(self, text, tag):
        self.serial += 1
        commands = self.control / "commands"
        commands.mkdir(parents=True, exist_ok=True)
        name = f"{int(time.time() * 1000):016d}-{self.serial:06d}-cheat-{tag}.txt"
        pending = self.control / f"cheat-{tag}.tmp"
        pending.write_text(text, encoding="utf-8")
        pending.replace(commands / name)
        return name

    def read(self, address, size, timeout=1.0):
        out = self.control / f"cheat-read-{self.serial + 1}.bin"
        name = self.send(f"command=read_memory\naddress=0x{address:08X}\nsize={size}\npath={out.name}\n", "read")
        deadline = time.time() + timeout
        while time.time() < deadline:
            if (self.control / "processed" / name).exists() and out.exists():
                data = out.read_bytes()
                out.unlink(missing_ok=True)
                return data if len(data) == size else None
            if (self.control / "failed" / name).exists():
                return None
            time.sleep(0.01)
        return None

    def write_float(self, address, value):
        data = struct.pack(">f", value).hex()
        self.send(f"command=write_memory\naddress=0x{address:08X}\ndata={data}\n", "write")

    def loop(self):
        target, player = None, None
        while True:
            time.sleep(0.05)
            if not self.enabled or not self.jump_held():
                if target is not None:
                    self.status = "Waiting for jump..."
                target = None
                continue
            if target is None:
                raw = self.read(PLAYER_POINTER, 4)
                player = struct.unpack(">I", raw)[0] if raw else 0
                if not 0x80000000 <= player < 0x817FFF00:
                    self.status = "No player found (are you in a stage?)"
                    continue
                raw = self.read(player + POSITION_Y, 4)
                if not raw:
                    continue
                target = struct.unpack(">f", raw)[0]
            target += self.rise
            self.write_float(player + POSITION_Y, target)
            self.status = f"Moon jump: height {target:.0f}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--control", type=Path, default=ROOT / "private/launcher-control")
    parser.add_argument("--simulate-hold", type=float, nargs=2, metavar=("START", "SECONDS"))
    parser.add_argument("--headless-seconds", type=float, help="Run without a window for this long (tests)")
    args = parser.parse_args()
    cheats = Cheats(args.control, args.simulate_hold)
    threading.Thread(target=cheats.loop, daemon=True).start()
    if args.headless_seconds:
        time.sleep(args.headless_seconds)
        return
    window = tk.Tk()
    window.title("Wario World - Cheats")
    window.resizable(False, False)
    enabled = tk.BooleanVar(value=True)

    def toggle():
        cheats.enabled = enabled.get()

    tk.Checkbutton(window, text="Moon jump (hold A / X)", variable=enabled, command=toggle).pack(
        anchor="w", padx=12, pady=(10, 2))
    tk.Label(window, text="Rise speed").pack(anchor="w", padx=12)
    speed = tk.DoubleVar(value=RISE_PER_TICK)

    def set_speed(_value):
        cheats.rise = speed.get()

    tk.Scale(window, from_=0.5, to=8.0, resolution=0.5, orient="horizontal", length=200,
             variable=speed, command=set_speed).pack(anchor="w", padx=12)
    status = tk.StringVar(value=cheats.status)
    tk.Label(window, textvariable=status, fg="gray").pack(anchor="w", padx=12, pady=(0, 10))

    def refresh():
        status.set(cheats.status)
        window.after(200, refresh)

    refresh()
    window.attributes("-topmost", True)
    window.mainloop()


if __name__ == "__main__":
    main()
