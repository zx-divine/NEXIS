"""Build an unelevated one-folder Windows release from an installed dev environment."""

import os
from pathlib import Path
import subprocess
import sys

if sys.platform != "win32":
    raise SystemExit("A Windows executable must be built on Windows.")
root = Path(__file__).resolve().parents[1]
if (root / "dist/NEXIS").exists():
    raise SystemExit("Existing distribution preserved. Use scripts/build_development_candidate.py with a new output directory and current five-round evidence.")
os.chdir(root)
subprocess.run([sys.executable, str(root / "scripts/prepare_branding.py")], check=True)
subprocess.run([sys.executable, str(root / "scripts/prepare_model.py"), "--download"], check=True)
subprocess.run([sys.executable, str(root / "scripts/prepare_runtime_notices.py")], check=True)
subprocess.run([sys.executable, "-m", "pytest", "-q"], check=True)
subprocess.run([sys.executable, "-m", "ruff", "check", "src", "tests", "scripts"], check=True)
subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "NEXIS.spec"], check=True)
print("Built dist/NEXIS/NEXIS.exe. Copy the entire folder; test on a clean Windows machine.")
