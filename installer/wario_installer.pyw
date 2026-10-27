"""Wario World Recomp installer: asks for your GWWE01 rev 0 ISO and an install folder, then builds
and installs the PC version there. Double-click Install-WarioWorld.cmd, or run

    python installer/wario_installer.pyw                      (window)
    python installer/wario_installer.pyw --no-gui --iso X --install-dir D   (console)
    python installer/wario_installer.pyw --check              (prerequisites only)
"""
import sys
from pathlib import Path


def fail(text):
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, text, "Wario World Recomp installer", 0x10)
    except Exception:
        pass
    print(text, file=sys.stderr)
    sys.exit(1)


if sys.version_info < (3, 11):
    fail("Python 3.11 or newer is needed (this is Python %d.%d).\n\nGet it from "
         "https://www.python.org/downloads/windows/ and run the installer again." % sys.version_info[:2])

sys.path.insert(0, str(Path(__file__).resolve().parent))

if __name__ == "__main__":
    try:
        import pipeline
        sys.exit(pipeline.main())
    except SystemExit:
        raise
    except Exception as error:  # under pythonw there is no console to show a traceback
        import traceback
        fail("The installer stopped unexpectedly:\n\n" + "".join(traceback.format_exception(error))[-1500:])
