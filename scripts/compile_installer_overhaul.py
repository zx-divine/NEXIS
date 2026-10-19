"""Compile the local-only Inno installer and record its actual exit code."""
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
output = ROOT / "docs/installer-overhaul"
compiler = ROOT / ".tools/InnoSetup/ISCC.exe"
if not compiler.is_file():
    raise SystemExit("Install Inno Setup locally; no compiler found.")
with (output / "installer-build.log").open("w", encoding="utf-8") as log:
    result = subprocess.run([str(compiler), "installer/NEXIS.iss"], cwd=ROOT, stdout=log,
                            stderr=subprocess.STDOUT, timeout=900)
(output / "installer-build-result.json").write_text(json.dumps({"exit_code": result.returncode}))
print("Inno Setup exit:", result.returncode)
raise SystemExit(result.returncode)
