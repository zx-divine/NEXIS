"""Record the full regression and static checks with actual subprocess return codes."""

import json
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

root = Path(__file__).resolve().parents[1]
commands = {
    "tests": [
        sys.executable,
        "scripts/dev.py",
        "test",
        "-q",
        "--tb=short",
        "-rs",
        "-p",
        "no:cacheprovider",
        "--basetemp",
        ".verification-operator-final-" + uuid4().hex[:8],
    ],
    "lint": [sys.executable, "scripts/dev.py", "lint", "check", "src", "tests", "scripts"],
}
report = {}
for label, command in commands.items():
    result = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=300)
    (root / "docs" / ("operator-final-" + label + ".txt")).write_text(
        result.stdout + result.stderr, encoding="utf-8"
    )
    report[label] = {"exit_code": result.returncode, "output": result.stdout + result.stderr}
(root / "docs/operator-final-regression.json").write_text(
    json.dumps(report, indent=2), encoding="utf-8"
)
print(json.dumps(report, indent=2))
raise SystemExit(0 if all(r["exit_code"] == 0 for r in report.values()) else 1)
