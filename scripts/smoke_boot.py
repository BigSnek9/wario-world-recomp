"""Bounded diagnostic boot in a fresh private user directory. Not a parity test."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--seconds", type=int, default=20)
parser.add_argument("--graphics", default="Null")
parser.add_argument("--lockstep", action="store_true")
parser.add_argument("--lockstep-limit", type=int, default=10000, help="Native dispatch cutoff; zero checks new sites throughout the run")
parser.add_argument("--capture", action="store_true", help="Ask the runtime to save a private diagnostic screenshot")
parser.add_argument("--windowed", action="store_true", help="Open a temporary game window for a rendering check")
parser.add_argument("--capture-at", type=float, help="Seconds after launch to request the screenshot")
parser.add_argument("--menu-probe", action="store_true", help="Try Start/A menu inputs in the fresh private session")
parser.add_argument("--memory-at", type=float, help="Pause briefly and save private MEM1 evidence at the given second")
parser.add_argument("--trace-helpers", action="store_true", help="Log first-seen instruction helper sites for classification")
parser.add_argument("--reference", action="store_true", help="Use the same runtime's original-code JIT for diagnostic comparison; not hardware reference")
parser.add_argument("--pad-hold", type=int, default=2, help="Guest frame callbacks to hold each probe button")
parser.add_argument("--instrumented", action="store_true", help="Use the separately built instruction-count diagnostic DLL")
parser.add_argument("--rel-bundle", action="store_true", help="Use the experimental instrumented main-plus-REL bundle")
parser.add_argument("--full", action="store_true", help="Use the clean main-plus-REL shipping port DLL")
parser.add_argument("--trace-dispatch", action="store_true", help="Save a private sampled native-PC trace")
parser.add_argument("--vectors", action="store_true", help="Use the separate experimental SDK-vector bundle")
parser.add_argument("--lockstep-trace", type=lambda v: int(v,0), help="Trace one shadow entry PC privately")
parser.add_argument("--trace-checks", action="store_true", help="Trace verifier check boundaries privately")
parser.add_argument("--probe-file", type=Path, help="JSON list of [guest-frame-callback, button] pairs")
parser.add_argument("--stack-at", type=float, help="Capture CPU/graphics stacks from this diagnostic child only")
args = parser.parse_args()
if not 1 <= args.seconds <= 180:
    parser.error("--seconds must be between 1 and 180")
if not 1 <= args.pad_hold <= 120:
    parser.error("--pad-hold must be between 1 and 120")
if args.reference and args.lockstep:
    parser.error("--reference cannot run native lockstep")
if args.full and args.lockstep:
    parser.error("Lockstep verification needs the instrumented bundle (--rel-bundle); the clean port has no instruction journal")
runner = ROOT / "build/moderngekko/Release/moderngekko-run.exe"
modules = sorted((ROOT / "build/modules/GWWE01").glob("*/gGWWE01_recomp.dll"), key=lambda p: p.stat().st_mtime)
if not runner.is_file() or not modules:
    raise SystemExit("Build the runtime and main module first")
module = modules[-1]
if args.instrumented:
    module = ROOT / "build/module-instrumented/Release/gGWWE01_recomp.dll"
    if not module.is_file():
        raise SystemExit("Run scripts/build_instrumented.py first")
if args.rel_bundle:
    module = ROOT / "build/module-rel-bundle/Release/gGWWE01_recomp.dll"
    if not module.is_file():
        raise SystemExit("Run scripts/build_rel_bundle.py first")
if args.full:
    module = ROOT / "build/module-full/Release/gGWWE01_recomp.dll"
    if not module.is_file():
        raise SystemExit("Run scripts/build_rel_bundle.py --clean first")
if args.vectors:
    module = ROOT / "build/module-rel-bundle-vectors/Release/gGWWE01_recomp.dll"
    if not module.is_file():
        raise SystemExit("Run scripts/build_rel_bundle.py --vectors first")
folder = ROOT / "private/runs" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
control = folder / "control"
(control / "commands").mkdir(parents=True)
user_directory = folder / "user"
user_directory.mkdir()
(user_directory / "config.ini").write_text(
    "[Video]\nresolution=640x528\nbackend=" + (args.graphics if args.graphics in ("Vulkan", "OpenGL") else "Vulkan") +
    "\nfullscreen=false\nshow_fps_in_title=true\n[Input]\n[Netplay]\n"
    "nickname=Player\naddress=127.0.0.1\nport=2626\nbuffer=auto\n", encoding="utf-8")
environment = os.environ.copy()
environment["MODERNGEKKO_STATICRECOMP"] = "0" if args.reference else "1"
environment["STATICRECOMP_DISPATCH_SAMPLES"] = "1"
if args.trace_dispatch:
    environment["STATICRECOMP_TRACE_FILE"] = str(folder / "dispatch.csv")
if args.trace_helpers:
    environment["WARIO_RECOMP_TRACE_HOOK_FALLBACK"] = "1"
if args.lockstep:
    environment["STATICRECOMP_LOCKSTEP"] = "1"
    environment["STATICRECOMP_LOCKSTEP_LIMIT"] = str(args.lockstep_limit)
    environment["STATICRECOMP_LOCKSTEP_MAXREPORT"] = "10"
    if args.lockstep_trace is not None:
        environment["STATICRECOMP_LOCKSTEP_TRACE"] = str(args.lockstep_trace)
    if args.trace_checks:
        environment["WARIO_LS_CHECK_TRACE"] = "1"
command = [str(runner), "--game", str(ROOT / "original/GWWE01"), "--module", str(module),
           "--user-dir", str(folder / "user"), "--automation-dir", str(control),
           "--graphics", args.graphics, "--mute", "--no-mods"]
if not args.windowed:
    command.append("--headless")
samples = []
forced_stop = False
capture_requested = False
probe_steps = [(900, "start"), (1020, "a"), (1260, "a"), (1500, "a"),
               (1740, "a"), (1980, "a"), (2220, "start"), (2460, "a"), (2700, "start")]
if args.probe_file:
    probe_steps = json.loads(args.probe_file.read_text(encoding="utf-8"))
    allowed = {"a","b","x","y","z","start","dpad_up","dpad_down","dpad_left","dpad_right","main_y","main_x"}
    previous = -1
    for step in probe_steps:
        if not isinstance(step,list) or len(step)!=2 or not isinstance(step[0],int) or step[0]<=previous or step[1] not in allowed:
            parser.error("Probe steps require increasing integer frames and supported button names")
        previous=step[0]
    args.menu_probe = True
probe_index = 0
memory_requested = False
stack_requested = False
started = time.monotonic()
print("Diagnostic output:", folder, flush=True)
with (folder / "runner.log").open("w", encoding="utf-8") as log:
    process = subprocess.Popen(command, cwd=runner.parent, stdout=log, stderr=subprocess.STDOUT,
                               stdin=subprocess.DEVNULL, env=environment,
                               creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    (folder / "process.json").write_text(json.dumps({"pid":process.pid,"runner":str(runner)})+"\n")
    while process.poll() is None and time.monotonic() - started < args.seconds:
        if args.stack_at is not None and not stack_requested and time.monotonic() - started >= args.stack_at:
            stack_requested = True
            try:
                with (folder / "stacks.txt").open("w") as stack_log:
                    subprocess.run([str(ROOT / "build/diagnostic-tools/Release/capture_stack.exe"),str(process.pid),str(runner)],
                                   stdout=stack_log,stderr=subprocess.STDOUT,timeout=15,
                                   creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            except (OSError, subprocess.TimeoutExpired) as error:
                print("Stack diagnostic failed:",error,flush=True)
        status = control / "status.txt"
        if status.is_file():
            try:
                text = status.read_text(encoding="utf-8")
                if not samples or samples[-1]["status"] != text:
                    samples.append({"elapsed": round(time.monotonic() - started, 3), "status": text})
            except (PermissionError, FileNotFoundError):
                pass
        if args.menu_probe and samples and probe_index < len(probe_steps):
            values = dict(line.split("=", 1) for line in samples[-1]["status"].splitlines() if "=" in line)
            threshold, button = probe_steps[probe_index]
            if int(values.get("frame_count", "0")) >= threshold:
                pending = control / "pad.tmp"
                pending.write_text(f"command=pad_frames\nport=0\nframes={args.pad_hold}\n{button}=1\n", encoding="utf-8")
                pending.replace(control / "commands" / f"200-pad-{probe_index}.txt")
                probe_index += 1
        if args.capture and not capture_requested and time.monotonic() - started >= (args.capture_at if args.capture_at is not None else args.seconds / 2):
            pending = control / "capture.tmp"
            pending.write_text("command=screenshot\npath=diagnostic.png\n", encoding="utf-8")
            pending.replace(control / "commands/100-screenshot.txt")
            capture_requested = True
        if args.memory_at is not None and not memory_requested and time.monotonic() - started >= args.memory_at:
            commands = [
                ("300-pause", "command=pause\n"),
                ("301-mem1-low", "command=read_memory\naddress=0x80000000\nsize=0x1000000\npath=mem1-low.bin\n"),
                ("302-mem1-high", "command=read_memory\naddress=0x81000000\nsize=0x800000\npath=mem1-high.bin\n"),
                ("303-resume", "command=resume\n"),
            ]
            for name, text in commands:
                pending = control / (name + ".tmp")
                pending.write_text(text, encoding="utf-8")
                pending.replace(control / "commands" / (name + ".txt"))
            memory_requested = True
        time.sleep(0.2)
    if process.poll() is None:
        pending = control / "stop.tmp"
        pending.write_text("command=stop\n", encoding="utf-8")
        pending.replace(control / "commands/999-stop.txt")
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            forced_stop = True
            process.terminate()
            process.wait(timeout=5)
report = dict(module=str(module), graphics=args.graphics, lockstep=args.lockstep,
              reference=args.reference, pad_hold=args.pad_hold, lockstep_limit=args.lockstep_limit,
              instrumented=args.instrumented,
              rel_bundle=args.rel_bundle,
              vectors=args.vectors,
              probe_steps=probe_steps if args.menu_probe else [], probe_steps_issued=probe_index,
              exit_code=process.returncode, forced_stop=forced_stop, samples=samples,
              limitation="Main-only diagnostic; automatic runtime fallback may execute noncompiled code. No parity claim.")
(folder / "result.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print("Exit:", process.returncode, "forced_stop:", forced_stop)
print((folder / "runner.log").read_text(encoding="utf-8", errors="replace")[-10000:])
if samples:
    print("Last sampled status:\n" + samples[-1]["status"])
print("This smoke run does not prove full static coverage, graphics correctness, or bit accuracy.")
raise SystemExit(process.returncode or int(forced_stop))
