"""One full, unchanged-source regression qualification; preserve all earlier runs."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
from time import monotonic

from candidate_evidence import ROOT, fingerprint


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    candidate = fingerprint()
    report = {"candidate_sha256": candidate, "rounds": [], "status": "RUNNING",
              "scope": "Complete pytest suite, fresh fixture directory, one serial qualification run"}
    (output / "results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    started = monotonic()
    with (output / "tests.txt").open("w", encoding="utf-8") as stream:
        result = subprocess.run([sys.executable, "scripts/dev.py", "test", "-vv", "--tb=short", "-rs",
            "-p", "no:cacheprovider", "--basetemp", str(output / "fixtures")],
            cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, timeout=1200)
    summary = (output / "tests.txt").read_text(encoding="utf-8")[-6000:]
    counts = re.search(r"(\d+) passed(?:, (\d+) skipped)?", summary)
    report["rounds"].append({"exit_code": result.returncode, "seconds": round(monotonic() - started, 2),
        "passed": int(counts[1]) if counts else None, "skipped": int(counts[2] or 0) if counts else None,
        "log": "tests.txt"})
    report["status"] = "PASS" if result.returncode == 0 and fingerprint() == candidate else "FAIL_OR_SOURCE_CHANGED"
    (output / "results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
