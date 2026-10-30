"""Record regression return codes without replacing previous checkpoint evidence."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
output = ROOT / "docs/installer-overhaul"
output.mkdir(parents=True, exist_ok=True)
commands = {
    "tests": [sys.executable, "scripts/dev.py", "test", "-q", "--tb=short", "-rs",
              "-p", "no:cacheprovider", "--basetemp", str(Path(tempfile.gettempdir()) / ("nexis-permission-final-" + uuid4().hex[:8]))],
    "lint": [sys.executable, "scripts/dev.py", "lint", "check", "src", "tests", "scripts"],
}
report = {}
for name, command in commands.items():
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=900)
    (output / (name + ".txt")).write_text(result.stdout + result.stderr, encoding="utf-8")
    report[name] = {"exit_code": result.returncode, "output": result.stdout + result.stderr}
    print(name, result.returncode, result.stdout + result.stderr, flush=True)
(output / "regression.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
raise SystemExit(0 if all(row["exit_code"] == 0 for row in report.values()) else 1)
