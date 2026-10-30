"""Build a local updater-enabled candidate and signed TUF assets; never publish."""

import argparse
import json
import os
from pathlib import Path
import shutil
import site
import subprocess
import sys
from time import monotonic

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / ".dev-deps", ROOT / ".provider-deps"):
    site.addsitedir(str(path))
sys.path.insert(0, str(ROOT / "src"))

from nexis import __version__, PUBLIC_VERSION  # noqa: E402
from candidate_evidence import fingerprint  # noqa: E402
from update_repository import key_location, sign_release, write_checksums  # noqa: E402
from nexis.core.update_service import operation_lock  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keys-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    args = parser.parse_args()
    output, work = args.output.resolve(), args.work.resolve()
    if output.exists() or work.exists():
        raise SystemExit("Output and work directories must be new. Previous artifacts are preserved.")
    work.mkdir(parents=True)
    source = fingerprint()
    report = {"status": "RUNNING", "source_sha256": source, "public_version": PUBLIC_VERSION,
              "build_version": __version__, "published": False, "steps": {}}

    def save():
        (work / "build-results.json").write_text(json.dumps(report, indent=2))

    def run(label, command, timeout=1200, environment=None):
        start = monotonic()
        with (work / (label + ".log")).open("w", encoding="utf-8") as log:
            result = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                timeout=timeout, env=environment, creationflags=subprocess.CREATE_NO_WINDOW)
        report["steps"][label] = {"exit_code": result.returncode, "seconds": round(monotonic() - start, 2)}
        save()
        print(label + ": " + str(result.returncode), flush=True)
        if result.returncode:
            raise RuntimeError(label + " failed; see the preserved build log")

    save()
    try:
        env = dict(os.environ)
        env["PYINSTALLER_CONFIG_DIR"] = str(work / "cache")
        run("pyinstaller", [sys.executable, "scripts/dev.py", "build", "--noconfirm",
            "--distpath", str(work / "payload"), "--workpath", str(work / "pyinstaller"),
            "NEXIS.spec"], timeout=2400, environment=env)
        executable = work / "payload/NEXIS/NEXIS.exe"
        env = {k: v for k, v in os.environ.items() if k not in {"PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"}}
        env["QT_QPA_PLATFORM"] = "windows"
        run("frozen-offline-smoke", [str(executable), "--smoke-test", str(work / "smoke"),
                                   "--offline-smoke"], timeout=300, environment=env)
        smoke = json.loads((work / "smoke/packaged-smoke.json").read_bytes())
        assert smoke["ok"] and smoke["frozen"] and smoke["app_version"] == __version__
        assert smoke["network_connection_attempts"] == 0
        run("inno-setup", [str(ROOT / ".tools/InnoSetup/ISCC.exe"),
            "/DAppSourceDir=" + str(executable.parent), "/O" + str(work / "installer"),
            str(ROOT / "installer/NEXIS.iss")])
        installer = next((work / "installer").glob("*.exe"))
        assert fingerprint() == source, "Source changed during build. Do not release these artifacts."
        with operation_lock(key_location(args.keys_dir)):
            summary = sign_release(args.keys_dir, installer, ROOT / "assets/release/UPDATE-RELEASE-NOTES.md",
                output, __version__, PUBLIC_VERSION)
        shutil.copy2(ROOT / "assets/release/UPDATE-GUIDE.md", output / "UPDATE-GUIDE.md")
        report.update({"status": "PASS", "metadata": summary,
                       "qualification": "Local candidate; see RELEASE-VERIFICATION.md for limits"})
        save()
        shutil.copy2(work / "build-results.json", output / "BUILD-RESULTS.json")
        write_checksums(output)
    except Exception as exc:
        report.update({"status": "FAIL", "error": str(exc)})
        save()
        raise


if __name__ == "__main__":
    main()
