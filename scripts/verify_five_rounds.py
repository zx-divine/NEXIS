"""Five independent regression processes against an unchanged candidate.

Evidence stays local/ignored. A failure or code change stops the sequence; after
repair, start a new sequence rather than counting earlier rounds as current.
"""

import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from time import monotonic
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / ".verification-launch-v1/final-regression"
OUTPUT.mkdir(parents=True, exist_ok=True)


def fingerprint():
    paths = set()
    for directory in ("src", "tests", "scripts"):
        paths.update(path for path in (ROOT / directory).rglob("*") if path.suffix in {".py", ".qss"})
    paths.update(ROOT / value for value in ("NEXIS.spec", "pyproject.toml", "requirements.txt",
        "requirements-dev.txt", "installer/NEXIS.iss", "scripts/version.txt", "assets/models/manifest.json",
        "assets/branding/NEXIS_logo.png", "assets/branding/NEXIS.ico"))
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(path.relative_to(ROOT).as_posix().encode() + b"\0" + path.read_bytes())
    return digest.hexdigest()


candidate = fingerprint()
report = {"candidate_sha256": candidate, "independent_processes": True,
          "fresh_test_state_each_round": True, "rounds": [], "status": "RUNNING"}
for number in range(1, 6):
    if fingerprint() != candidate:
        report["status"] = "SOURCE_CHANGED"
        break
    temporary = Path(tempfile.gettempdir()) / ("nexis-final-" + uuid4().hex)
    if temporary.exists():
        raise SystemExit("Unexpected existing test directory; stopped without deleting it.")
    started = monotonic()
    log = OUTPUT / f"round-{number}.txt"
    try:
        with log.open("w", encoding="utf-8") as stream:
            result = subprocess.run([sys.executable, "scripts/dev.py", "test", "-q", "--tb=short", "-rs",
                "-p", "no:cacheprovider", "--basetemp", str(temporary)], cwd=ROOT,
                stdout=stream, stderr=subprocess.STDOUT, timeout=900)
        summary = log.read_text(encoding="utf-8")[-5000:]
        counts = re.search(r"(\d+) passed(?:, (\d+) skipped)?", summary)
        row = {"round": number, "exit_code": result.returncode,
               "seconds": round(monotonic() - started, 2), "log": log.name,
               "passed": int(counts[1]) if counts else None, "skipped": int(counts[2] or 0) if counts else None}
    except subprocess.TimeoutExpired:
        row = {"round": number, "exit_code": None, "status": "TIMEOUT", "log": log.name}
    report["rounds"].append(row)
    print(json.dumps(row), flush=True)
    if row.get("exit_code") != 0:
        report["status"] = "FAIL"
    elif fingerprint() != candidate:
        report["status"] = "SOURCE_CHANGED"
    elif number == 5:
        report["status"] = "PASS"
    (OUTPUT / "results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    if report["status"] not in {"RUNNING", "PASS"}:
        break
(OUTPUT / "results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
raise SystemExit(0 if report["status"] == "PASS" else 1)
