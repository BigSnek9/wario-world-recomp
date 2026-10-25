"""Import the pinned main DOL into portable Ghidra without loader dialogs."""
import csv
import os
from pathlib import Path
import subprocess
from build import check_game

ROOT = Path(__file__).resolve().parents[1]
check_game()
seeds = []
with (ROOT / "reports/functions.csv").open(newline="", encoding="utf-8") as stream:
    for entry in csv.DictReader(stream):
        if entry["module"] == "main":
            seeds.append(entry["address_or_offset"].removeprefix("0x") + "\t" + entry["name"])
seed_path = ROOT / "reports/main-function-seeds.tsv"
seed_path.write_text("\n".join(seeds) + "\n")
private = ROOT / "private/ghidra"
projects = private / "projects"
projects.mkdir(parents=True, exist_ok=True)
ghidra = ROOT / "third_party/ghidra/ghidra_12.1.3_PUBLIC"
environment = os.environ.copy()
environment["GHIDRA_HEADLESS_MAXMEM"] = "4G"
environment["APPDATA"] = str(private / "appdata")
environment["LOCALAPPDATA"] = str(private / "localappdata")
command = [str(ghidra / "support/analyzeHeadless.bat"), str(projects), "WarioWorld-GWWE01",
           "-import", str(ROOT / "original/GWWE01/sys/main.dol"),
           "-loader-autoloadMaps", "false", "-max-cpu", "4", "-analysisTimeoutPerFile", "180",
           "-scriptPath", str(ROOT / "scripts/ghidra"),
           "-preScript", "SeedFunctions.java", str(seed_path),
           "-postScript", "ExportBootstrap.java", str(ROOT / "reports/ghidra-bootstrap"),
           "-log", str(ROOT / "reports/ghidra-analysis.log")]
print("Importing main DOL; ensure the connector has closed this project first.", flush=True)
with (ROOT / "reports/ghidra-import.log").open("w") as log:
    result = subprocess.run(command, cwd=ghidra, env=environment, stdin=subprocess.DEVNULL,
                            stdout=log, stderr=subprocess.STDOUT)
print("Import exit:", result.returncode)
print((ROOT / "reports/ghidra-import.log").read_text(errors="replace")[-5000:])
raise SystemExit(result.returncode)
