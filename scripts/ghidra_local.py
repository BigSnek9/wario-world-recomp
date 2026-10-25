"""Start the approved portable Ghidra connector on loopback, with private settings."""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("action", choices=["start", "status"])
args = parser.parse_args()
private = ROOT / "private/ghidra"
private.mkdir(parents=True, exist_ok=True)
metadata_path = private / "server.json"
if args.action == "status":
    metadata = json.loads(metadata_path.read_text())
    with urllib.request.urlopen(metadata["url"] + "/check_connection", timeout=10) as response:
        print(response.read().decode())
    raise SystemExit()
ghidra = ROOT / "third_party/ghidra/ghidra_12.1.3_PUBLIC"
connector = ROOT / "third_party/GhidraMCP/build/libs/GhidraMCP-7.0.0.jar"
if not connector.is_file() or not ghidra.is_dir():
    raise SystemExit("Portable Ghidra and built connector are required")
if metadata_path.exists():
    previous = json.loads(metadata_path.read_text())
    try:
        with urllib.request.urlopen(previous["url"] + "/check_connection", timeout=2) as response:
            print("Existing connector:", response.read().decode())
        raise SystemExit()
    except OSError:
        pass
with socket.socket() as probe:
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
classpath = [connector.as_posix()]
classpath.extend((p / "*").as_posix() for p in sorted((ghidra / "Ghidra").rglob("lib")) if p.is_dir())
argfile = private / "java.args"
arguments = ["-Xmx4G", "-Djava.awt.headless=true", "-Duser.home=" + (private / "home").as_posix(),
             "-Dghidra.home=" + ghidra.as_posix(), "-Dapplication.name=GhidraMCP",
             "-classpath", ";".join(classpath), "com.xebyte.headless.GhidraMCPHeadlessServer",
             "--bind", "127.0.0.1", "--port", str(port)]
argfile.write_text("\n".join('"' + a.replace('"', '\\"') + '"' for a in arguments) + "\n", encoding="utf-8")
log_path = ROOT / "reports/ghidra-server.log"
environment = os.environ.copy()
for name, directory in (("APPDATA", private / "appdata"), ("LOCALAPPDATA", private / "localappdata")):
    directory.mkdir(parents=True, exist_ok=True)
    environment[name] = str(directory)
with log_path.open("w") as log:
    process = subprocess.Popen(["java", "@" + str(argfile)], cwd=ghidra, stdout=log,
                               stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, env=environment,
                               creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
metadata = {"pid": process.pid, "url": f"http://127.0.0.1:{port}", "log": str(log_path)}
metadata_path.write_text(json.dumps(metadata, indent=2) + "\n")
for attempt in range(40):
    if process.poll() is not None:
        print(log_path.read_text(errors="replace")[-12000:])
        raise SystemExit(process.returncode or 1)
    try:
        with urllib.request.urlopen(metadata["url"] + "/check_connection", timeout=1) as response:
            print(response.read().decode())
        print("Connector:", metadata["url"], "PID:", process.pid)
        break
    except OSError:
        time.sleep(0.5)
else:
    print("Startup still in progress; inspect", log_path)
