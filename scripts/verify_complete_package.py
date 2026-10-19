"""Verify and install the final local package; never publishes artifacts."""
import csv
import json
from pathlib import Path
import subprocess
import sys
from time import monotonic

ROOT = Path(__file__).resolve().parents[1]
output = ROOT / "docs/installer-overhaul"
commands = [
    ("frozen", [sys.executable, "scripts/check_package.py"], 240),
    ("native", [sys.executable, "scripts/audit_native_bundle.py"], 240),
    ("installer", [sys.executable, "scripts/compile_installer_overhaul.py"], 1000),
    ("installed", [sys.executable, "scripts/verify_installation.py", "--install"], 480),
    ("portable", [sys.executable, "scripts/verify_portable.py"], 600),
]
report = {}
for name, command, timeout in commands:
    if name == "installed":
        tasks = subprocess.check_output(["tasklist", "/FI", "IMAGENAME eq NEXIS.exe", "/FO", "CSV", "/NH"], text=True)
        if any(row and row[0].casefold() == "nexis.exe" for row in csv.reader(tasks.splitlines())):
            report[name] = {"status": "NOT VERIFIED", "reason": "An owner NEXIS process is running; it was not closed."}
            (output / "package-results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
            continue
    started = monotonic()
    try:
        result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=timeout)
        (output / (name + "-check.txt")).write_text(result.stdout + result.stderr, encoding="utf-8")
        report[name] = {"exit_code": result.returncode, "seconds": round(monotonic() - started, 2)}
        print(name, report[name], flush=True)
        if result.returncode:
            break
    except subprocess.TimeoutExpired:
        report[name] = {"status": "FAIL", "reason": "Timed out; not counted as verified"}
        break
    finally:
        (output / "package-results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2), flush=True)
raise SystemExit(0 if len(report) == len(commands) and all(r.get("exit_code") == 0 for r in report.values()) else 1)
