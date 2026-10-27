"""Bounded diagnostic boot in a fresh private user directory. Not a parity test."""
import argparse
import configparser
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import shutil
import time
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--seconds", type=int, default=20)
parser.add_argument("--graphics", default="Null")
parser.add_argument("--lockstep", action="store_true")
parser.add_argument("--lockstep-limit", type=int, default=10000, help="Native dispatch cutoff; zero checks new sites throughout the run")
parser.add_argument("--capture", action="store_true", help="Ask the runtime to save a private diagnostic screenshot")
parser.add_argument("--capture-cadence", type=float, help="Save a private diagnostic screenshot every N seconds (implies --capture)")
parser.add_argument("--windowed", action="store_true", help="Open a temporary game window for a rendering check")
parser.add_argument("--capture-at", type=float, help="Seconds after launch to request the screenshot")
parser.add_argument("--menu-probe", action="store_true", help="Try Start/A menu inputs in the fresh private session")
parser.add_argument("--memory-at", type=float, action="append", help="Pause briefly and save private MEM1 evidence at the given second (repeatable; later snapshots are numbered). With --load-state, seconds count from the settled state load")
parser.add_argument("--trace-helpers", action="store_true", help="Log first-seen instruction helper sites for classification")
parser.add_argument("--reference", action="store_true", help="Use the same runtime's original-code JIT for diagnostic comparison; not hardware reference")
parser.add_argument("--pad-hold", type=int, default=2, help="Guest frame callbacks to hold each probe button")
parser.add_argument("--instrumented", action="store_true", help="Use the separately built instruction-count diagnostic DLL")
parser.add_argument("--rel-bundle", action="store_true", help="Use the experimental instrumented main-plus-REL bundle")
parser.add_argument("--full", action="store_true", help="Use the uninstrumented main-plus-REL candidate DLL")
parser.add_argument("--trace-dispatch", action="store_true", help="Save a private sampled native-PC trace")
parser.add_argument("--vectors", action="store_true", help="Use the separate experimental SDK-vector bundle")
parser.add_argument("--lockstep-trace", type=lambda v: int(v,0), help="Trace one shadow entry PC privately")
parser.add_argument("--trace-checks", action="store_true", help="Trace verifier check boundaries privately")
parser.add_argument("--probe-file", type=Path, help="JSON list of [guest-frame-callback, button] pairs")
parser.add_argument("--memcard", choices=("folder", "raw"), help="Slot A device override; raw uses a .raw card image instead of a GCI folder")
parser.add_argument("--module", type=Path, help="Use this game module DLL instead of the --full/--vectors selection (e.g. a compiler experiment)")
parser.add_argument("--gfx-setting", action="append", default=[], metavar="SECTION.KEY=VALUE",
                    help="Override a GFX.ini setting after the presentation baseline (repeatable; enhancement tests)")
parser.add_argument("--dolphin-setting", action="append", default=[], metavar="SECTION.KEY=VALUE",
                    help="Override a Dolphin.ini setting in this run's private user folder (repeatable)")
parser.add_argument("--profile-at", type=float, help="Start a read-only sampling profile of busy threads at this second")
parser.add_argument("--profile-ms", type=int, default=10000, help="Sampling profile duration in milliseconds")
parser.add_argument("--stack-at", type=float, help="Capture CPU/graphics stacks from this diagnostic child only")
parser.add_argument("--runtime-root", type=Path, help="Read existing runtime/game elsewhere; keep new diagnostics beside this script")
parser.add_argument("--runner", type=Path, help="Use a separately built workspace diagnostic runtime")
parser.add_argument("--game", type=Path, help="Extracted disc folder (default: <runtime root>/original/GWWE01), e.g. a release test's game/GWWE01")
parser.add_argument("--dump-audio", action="store_true", help="Write private DSP/stream WAV data while output stays muted")
parser.add_argument("--save-state-at", type=float, help="Save a private diagnostic state after this many seconds")
parser.add_argument("--load-state", type=Path, help="Resume a private diagnostic state after boot")
parser.add_argument("--seed-user", type=Path, help="Copy a prior private diagnostic user folder into this fresh run")
parser.add_argument("--resolution", default="640x528", help="config.ini internal resolution label (1920x1080 = 3x)")
args = parser.parse_args()
if args.windowed:
    parser.error("Visible testing is disabled; omit --windowed for hidden, muted testing")
if not 1 <= args.seconds <= 180:
    parser.error("--seconds must be between 1 and 180")
if not 1 <= args.pad_hold <= 120:
    parser.error("--pad-hold must be between 1 and 120")
if args.load_state and not args.load_state.is_file():
    parser.error("Diagnostic state does not exist")
if args.seed_user and (not args.seed_user.is_dir() or not args.seed_user.resolve().is_relative_to((ROOT / "private").resolve())):
    parser.error("Seed user must be one of this project's private diagnostic folders")
if args.reference and args.lockstep:
    parser.error("--reference cannot run native lockstep")
if args.full and args.lockstep:
    parser.error("Lockstep verification needs the instrumented bundle (--rel-bundle); the clean port has no instruction journal")
runtime_root = args.runtime_root.resolve() if args.runtime_root else ROOT
runner = args.runner.resolve() if args.runner else runtime_root / "build/moderngekko/Release/moderngekko-run.exe"
modules = sorted((runtime_root / "build/modules/GWWE01").glob("*/gGWWE01_recomp.dll"), key=lambda p: p.stat().st_mtime)
if not runner.is_file() or not modules:
    raise SystemExit("Build the runtime and main module first")
module = modules[-1]
if args.instrumented:
    module = runtime_root / "build/module-instrumented/Release/gGWWE01_recomp.dll"
    if not module.is_file():
        raise SystemExit("Run scripts/build_instrumented.py first")
if args.rel_bundle:
    module = runtime_root / "build/module-rel-bundle/Release/gGWWE01_recomp.dll"
    if not module.is_file():
        raise SystemExit("Run scripts/build_rel_bundle.py first")
if args.full:
    module = runtime_root / "build/module-full/Release/gGWWE01_recomp.dll"
    if not module.is_file():
        raise SystemExit("Run scripts/build_rel_bundle.py --clean first")
if args.vectors:
    module = runtime_root / ("build/module-full-vectors/Release/gGWWE01_recomp.dll" if args.full else "build/module-rel-bundle-vectors/Release/gGWWE01_recomp.dll")
    if not module.is_file():
        raise SystemExit("Run scripts/build_rel_bundle.py --vectors first")
if args.module:
    module = args.module.resolve()
    if not module.is_file():
        raise SystemExit(f"Module not found: {module}")
folder = ROOT / "private/runs" / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid4().hex[:8])
control = folder / "control"
(control / "commands").mkdir(parents=True)
user_directory = folder / "user"
user_directory.mkdir()
if args.seed_user:
    shutil.copytree(args.seed_user, user_directory, dirs_exist_ok=True)
(user_directory / "config.ini").write_text(
    "[Video]\nresolution=" + args.resolution + "\nbackend=" + (args.graphics if args.graphics in ("Vulkan", "OpenGL") else "Vulkan") +
    "\nfullscreen=false\nshow_fps_in_title=true\n[Input]\n[Netplay]\n"
    "nickname=Player\naddress=127.0.0.1\nport=2626\nbuffer=auto\n", encoding="utf-8")
from configure_baseline import install as install_presentation_baseline
install_presentation_baseline(user_directory)
# The baseline pins 640x528 / OpenGL; an explicit --resolution or --graphics Vulkan wins.
if args.resolution != "640x528" or args.graphics == "Vulkan":
    video = configparser.ConfigParser(interpolation=None, strict=False)
    video.optionxform = str
    video.read(user_directory / "config.ini", encoding="utf-8-sig")
    video.set("Video", "resolution", args.resolution)
    video.set("Video", "backend", "Vulkan" if args.graphics == "Vulkan" else "OpenGL")
    with (user_directory / "config.ini").open("w", encoding="utf-8") as stream:
        video.write(stream)
if args.gfx_setting:
    gfx = configparser.ConfigParser(interpolation=None, strict=False)
    gfx.optionxform = str
    gfx_path = user_directory / "Config/GFX.ini"
    gfx.read(gfx_path, encoding="utf-8")
    for override in args.gfx_setting:
        key, _, value = override.partition("=")
        section, _, name = key.partition(".")
        if not gfx.has_section(section):
            gfx.add_section(section)
        gfx.set(section, name, value)
    with gfx_path.open("w", encoding="utf-8") as output:
        gfx.write(output)
if args.memcard == "raw":
    # The core reads user/Config/Dolphin.ini (F_DOLPHINCONFIG_IDX is
    # D_CONFIG_IDX + DOLPHIN_CONFIG). EXIDeviceType::MemoryCard (1) selects the
    # raw card image device instead of the default GCI folder card.
    config_directory = user_directory / "Config"
    config_directory.mkdir(exist_ok=True)
    (config_directory / "Dolphin.ini").write_text(
        chr(91) + "Core" + chr(93) + "\nSlotA = 1\n", encoding="utf-8")
if args.dump_audio:
    config_directory = user_directory / "Config"
    config_directory.mkdir(exist_ok=True)
    ini = config_directory / "Dolphin.ini"
    settings = configparser.ConfigParser(interpolation=None, strict=False)
    settings.optionxform = str
    if ini.exists():
        settings.read(ini, encoding="utf-8")
    if not settings.has_section("DSP"):
        settings.add_section("DSP")
    settings.set("DSP", "DumpAudio", "True")
    settings.set("DSP", "DumpAudioSilent", "True")
    with ini.open("w", encoding="utf-8") as output:
        settings.write(output)

if args.dolphin_setting:
    config_directory = user_directory / "Config"
    config_directory.mkdir(exist_ok=True)
    ini = config_directory / "Dolphin.ini"
    settings = configparser.ConfigParser(interpolation=None, strict=False)
    settings.optionxform = str
    if ini.exists():
        settings.read(ini, encoding="utf-8")
    for override in args.dolphin_setting:
        key, _, value = override.partition("=")
        section, _, name = key.partition(".")
        if not (section and name and _):
            parser.error("--dolphin-setting expects SECTION.KEY=VALUE")
        if not settings.has_section(section):
            settings.add_section(section)
        settings.set(section, name, value)
    with ini.open("w", encoding="utf-8") as output:
        settings.write(output)

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
game_directory = args.game.resolve() if args.game else runtime_root / "original/GWWE01"
command = [str(runner), "--game", str(game_directory), "--module", str(module),
           "--user-dir", str(folder / "user"), "--automation-dir", str(control),
           "--graphics", args.graphics, "--mute", "--no-mods"]
if not args.windowed:
    command.append("--headless")
samples = []
forced_stop = False
capture_requested = False
captures_issued = 0
probe_steps = [(900, "start"), (1020, "a"), (1260, "a"), (1500, "a"),
               (1740, "a"), (1980, "a"), (2220, "start"), (2460, "a"), (2700, "start")]
if args.probe_file:
    probe_steps = json.loads(args.probe_file.read_text(encoding="utf-8"))
    allowed = {"a","b","x","y","z","start","dpad_up","dpad_down","dpad_left","dpad_right","main_y","main_x"}
    previous = -1
    for step in probe_steps:
        if not isinstance(step,list) or len(step) not in (2,3,4) or not isinstance(step[0],int) or step[0]<=previous or step[1] not in allowed:
            parser.error("Probe steps require increasing integer frames and supported button names")
        if len(step)>=3 and (not isinstance(step[2],int) or not 1 <= step[2] <= 3600):
            parser.error("Per-step hold duration must be 1..3600 guest frame callbacks")
        if len(step)==4 and (not isinstance(step[3],(int,float)) or not -1 <= step[3] <= 1 or (step[1] not in ('main_x','main_y') and step[3] not in (0,1))):
            parser.error("Control value must be -1..1 for sticks or 0/1 for buttons")
        previous=step[0]
    args.menu_probe = True
probe_index = 0
state_saved = False
state_load_observed_at = None
state_load_requested = False
state_load_complete = not bool(args.load_state)
probe_frame_origin = 0
memory_requested = 0
load_settled_at = None
stack_requested = False
profiler = None
started = time.monotonic()
print("Diagnostic output:", folder, flush=True)
with (folder / "runner.log").open("w", encoding="utf-8") as log:
    process = subprocess.Popen(command, cwd=runner.parent, stdout=log, stderr=subprocess.STDOUT,
                               stdin=subprocess.DEVNULL, env=environment,
                               creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    (folder / "process.json").write_text(json.dumps({"pid":process.pid,"runner":str(runner)})+"\n")
    try:
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
            if args.profile_at is not None and profiler is None and time.monotonic() - started >= args.profile_at:
                profile_log = (folder / "profile.txt").open("w")
                profiler = subprocess.Popen([str(ROOT / "build/diagnostic-tools/Release/sample_profile.exe"), str(process.pid), str(runner),
                                             str(args.profile_ms), str(folder / "profile.csv")],
                                            stdout=profile_log, stderr=subprocess.STDOUT,
                                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            status = control / "status.txt"
            if status.is_file():
                try:
                    text = status.read_text(encoding="utf-8")
                    if not samples or samples[-1]["status"] != text:
                        samples.append({"elapsed": round(time.monotonic() - started, 3), "status": text})
                except (PermissionError, FileNotFoundError):
                    pass
            if args.load_state and samples:
                current = dict(line.split("=", 1) for line in samples[-1]["status"].splitlines() if "=" in line)
                if not state_load_requested and current.get("state") == "running" and int(current.get("frame_count", "0")) >= 60:
                    pending = control / "load-state.tmp"
                    pending.write_text("command=load_state\npath=" + str(args.load_state.resolve()) + "\n", encoding="utf-8")
                    pending.replace(control / "commands/050-load-state.txt")
                    state_load_requested = True
                if state_load_requested and not state_load_complete and (control / "processed/050-load-state.txt").exists():
                    if state_load_observed_at is None:
                        state_load_observed_at = time.monotonic()
                    # State load restores the renderer frame counter. Wait for a
                    # post-load callback/status before interpreting relative steps.
                    if current.get("last_command") == "050-load-state.txt" and time.monotonic() - state_load_observed_at >= 0.5:
                        state_load_complete = True
                        load_settled_at = time.monotonic()
                        probe_frame_origin = int(current.get("frame_count", "0"))
            if state_load_complete and args.save_state_at is not None and not state_saved and time.monotonic() - started >= args.save_state_at:
                pending = control / "save-state.tmp"
                pending.write_text("command=save_state\npath=checkpoint.savestate\n", encoding="utf-8")
                pending.replace(control / "commands/400-save-state.txt")
                state_saved = True
            if state_load_complete and args.menu_probe and samples and probe_index < len(probe_steps):
                values = dict(line.split("=", 1) for line in samples[-1]["status"].splitlines() if "=" in line)
                step = probe_steps[probe_index]
                threshold, button = step[:2]
                hold = step[2] if len(step)>=3 else args.pad_hold
                value = step[3] if len(step)==4 else 1
                if int(values.get("frame_count", "0")) >= threshold + probe_frame_origin:
                    pending = control / "pad.tmp"
                    pending.write_text(f"command=pad_frames\nport=0\nframes={hold}\n{button}={value}\n", encoding="utf-8")
                    pending.replace(control / "commands" / f"200-pad-{probe_index}.txt")
                    probe_index += 1
            capture_due = args.capture or args.capture_cadence is not None
            if capture_due and state_load_complete:
                cadence_due = (args.capture_cadence is not None and
                               time.monotonic() - started >= args.capture_cadence * (captures_issued + 1))
                single_due = (args.capture_cadence is None and not capture_requested and
                              time.monotonic() - started >= (args.capture_at if args.capture_at is not None else args.seconds / 2))
                if cadence_due or single_due:
                    pending = control / "capture.tmp"
                    pending.write_text("command=screenshot\npath=diagnostic-%02d.png\n" % captures_issued, encoding="utf-8")
                    pending.replace(control / ("commands/100-screenshot-%02d.txt" % captures_issued))
                    captures_issued += 1
                    capture_requested = True
            memory_times = sorted(args.memory_at or [])
            if state_load_complete and memory_requested < len(memory_times) and time.monotonic() - (load_settled_at or started) >= memory_times[memory_requested]:
                suffix = "" if memory_requested == 0 else "-%d" % memory_requested
                commands = [
                    ("300-pause" + suffix, "command=pause\n"),
                    ("301-mem1-low" + suffix, "command=read_memory\naddress=0x80000000\nsize=0x1000000\npath=mem1-low%s.bin\n" % suffix),
                    ("302-mem1-high" + suffix, "command=read_memory\naddress=0x81000000\nsize=0x800000\npath=mem1-high%s.bin\n" % suffix),
                    ("303-resume" + suffix, "command=resume\n"),
                ]
                for name, text in commands:
                    pending = control / (name + ".tmp")
                    pending.write_text(text, encoding="utf-8")
                    pending.replace(control / "commands" / (name + ".txt"))
                memory_requested += 1
            time.sleep(0.2)
    finally:
        if profiler is not None:
            # Symbolization needs the live child, so let the profiler finish first.
            try:
                profiler.wait(timeout=args.profile_ms / 1000 + 60)
            except subprocess.TimeoutExpired:
                profiler.terminate()
            profile_log.close()
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

report = dict(dolphin_settings=args.dolphin_setting, dump_audio=args.dump_audio, load_state=str(args.load_state) if args.load_state else None, state_load_complete=state_load_complete, probe_frame_origin=probe_frame_origin, seed_user=str(args.seed_user) if args.seed_user else None, module=str(module), runner=str(runner), full=args.full, graphics=args.graphics, lockstep=args.lockstep,
              reference=args.reference, pad_hold=args.pad_hold, lockstep_limit=args.lockstep_limit,
              instrumented=args.instrumented,
              rel_bundle=args.rel_bundle,
              vectors=args.vectors,
              probe_steps=probe_steps if args.menu_probe else [], probe_steps_issued=probe_index,
              exit_code=process.returncode, forced_stop=forced_stop, samples=samples,
              limitation="Bounded diagnostic; hardware helpers and possible JIT execution must be accounted for. Unvisited code and full-game parity remain unverified.")
(folder / "result.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print("Exit:", process.returncode, "forced_stop:", forced_stop)
print((folder / "runner.log").read_text(encoding="utf-8", errors="replace")[-10000:])
if samples:
    print("Last sampled status:\n" + samples[-1]["status"])
print("This smoke run does not prove full static coverage, graphics correctness, or bit accuracy.")
raise SystemExit(process.returncode or int(forced_stop))
