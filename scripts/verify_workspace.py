"""Repeatable verification for a bundled runtime with workspace-installed dependencies."""

import json
import os
from pathlib import Path
import subprocess
import sys
from time import perf_counter

root = Path(__file__).resolve().parents[1]
os.chdir(root)
environment = dict(os.environ, QT_QPA_PLATFORM="offscreen")
commands = [
    ["test", "-q", "-rs", "-p", "no:cacheprovider", "--basetemp", ".verification-temp"],
    ["lint", "check", "src", "tests", "scripts"],
    ["screenshot"],
    ["measure"],
    ["build", "--noconfirm", "--workpath", ".packaging-work", "NEXIS.spec"],
]
results = []
log = root / "docs" / "verification-output.txt"
with log.open("w", encoding="utf-8") as stream:
    for arguments in commands:
        print("Running " + " ".join(arguments), flush=True)
        started = perf_counter()
        result = subprocess.run(
            [sys.executable, "scripts/dev.py", *arguments],
            env=environment,
            text=True,
            capture_output=True,
        )
        output = result.stdout + result.stderr
        stream.write("COMMAND: scripts/dev.py " + " ".join(arguments) + "\n" + output + "\n")
        stream.flush()
        results.append(
            {
                "arguments": arguments,
                "exit_code": result.returncode,
                "elapsed_seconds": round(perf_counter() - started, 2),
            }
        )
        print(output[-4000:], flush=True)
        if result.returncode:
            print(
                "Verification stopped at failed stage. See docs/verification-output.txt", flush=True
            )
            break
(root / "docs" / "verification-stages.json").write_text(
    json.dumps(results, indent=2), encoding="utf-8"
)
raise SystemExit(
    0 if len(results) == len(commands) and all(r["exit_code"] == 0 for r in results) else 1
)
