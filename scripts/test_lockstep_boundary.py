"""Compatibility entry point; normal unittest discovery must not build binaries."""
from pathlib import Path
import runpy

if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).with_name("verify_lockstep_boundary.py")), run_name="__main__")
