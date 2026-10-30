"""Build a local candidate in a new directory, preserving all earlier artifacts.

Run in the documented Python environment. --workspace-runtime additionally uses
the existing private dependency directories; they are never copied into output.
Nothing is uploaded, installed or published by this script.
"""

import argparse
import hashlib
import json
import os
import platform
import re
import ssl
from pathlib import Path
import subprocess
import sys
from time import monotonic
import tomllib
import zipfile
from uuid import uuid5, NAMESPACE_URL

from candidate_evidence import ROOT, fingerprint
from runtime_ssl import ssl_runtime_data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verification", type=Path, required=True, help="Regression results.json for this exact source")
    parser.add_argument("--verification-rounds", type=int, choices=(1, 5), default=5,
                        help="Required full regression runs (historical default: five)")
    parser.add_argument("--output", type=Path, required=True, help="New, nonexistent local output directory")
    parser.add_argument("--iscc", type=Path, required=True, help="Installed Inno Setup 6 compiler")
    parser.add_argument("--workspace-runtime", action="store_true")
    parser.add_argument("--side-by-side-label", help="Isolated test installer identity, directory and shortcuts")
    args = parser.parse_args()
    if args.side_by_side_label and not re.fullmatch(r"[A-Za-z0-9-]{1,60}", args.side_by_side_label):
        parser.error("Use a short letters/digits/hyphens candidate label")
    version = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    candidate = fingerprint()
    verified = json.loads(args.verification.read_text(encoding="utf-8"))
    if (verified.get("status") != "PASS" or verified.get("candidate_sha256") != candidate
            or len(verified.get("rounds", [])) != args.verification_rounds
            or any(row.get("exit_code") != 0 for row in verified["rounds"])):
        raise SystemExit(f"{args.verification_rounds} successful full regressions of this exact source are required. Earlier evidence was retained.")
    if sys.platform != "win32" or not args.iscc.is_file():
        raise SystemExit("Use Windows x64 and an installed Inno Setup compiler.")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    report = {"version": version, "source_sha256": candidate, "status": "RUNNING", "steps": {}}

    def write():
        (output / "BUILD-REPORT.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    def run(label, command, timeout=1200, **kwargs):
        started = monotonic()
        with (output / (label + ".log")).open("w", encoding="utf-8") as log:
            try:
                result = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=timeout, **kwargs)
                row = {"exit_code": result.returncode, "seconds": round(monotonic() - started, 2)}
            except subprocess.TimeoutExpired:
                row = {"exit_code": None, "status": "TIMEOUT", "seconds": round(monotonic() - started, 2)}
        report["steps"][label] = row
        write()
        print(label + ": " + json.dumps(row), flush=True)
        if row["exit_code"] != 0:
            raise ValueError(label + " failed. Incomplete output and earlier artifacts were preserved.")

    write()
    try:
        wrapper = [sys.executable, "scripts/dev.py"]
        lint = wrapper + ["lint", "check", "src", "tests", "scripts"] if args.workspace_runtime else [sys.executable, "-m", "ruff", "check", "src", "tests", "scripts"]
        run("lint", lint)
        build = wrapper + ["build"] if args.workspace_runtime else [sys.executable, "-m", "PyInstaller"]
        run("pyinstaller", build + ["--noconfirm", "--distpath", str(output / "payload"), "--workpath", str(output / "work"), "NEXIS.spec"], timeout=2400)
        folder = output / "payload/NEXIS"
        environment = {key: value for key, value in os.environ.items() if key not in {"PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"}}
        environment["PATH"] = str(Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32")
        environment["QT_QPA_PLATFORM"] = "windows"
        run("frozen-offline", [str(folder / "NEXIS.exe"), "--smoke-test", str(output / "frozen-offline"), "--offline-smoke"], timeout=240, env=environment)
        smoke = json.loads((output / "frozen-offline/packaged-smoke.json").read_text(encoding="utf-8"))
        assert smoke["ok"] and smoke["frozen"] and smoke["app_version"] == version
        assert smoke["release_channel"] == "development" and smoke["schema_version"] == 5
        assert smoke["window_title"] == "NEXIS" and smoke["wizard_completed"]
        assert all(value == "PASS" for value in smoke["latest_feature_checks"].values())
        assert smoke["network_connection_attempts"] == 0 and smoke["python_network_blocked"]
        assert smoke["bundled_model"]["loaded"] and smoke["bundled_model"]["files_verified"] == 14
        assert smoke["bundled_model"]["inside_package"] and smoke["workflow_fixture_check"]["result"] == "PASS"
        assert all(value == "available" for value in smoke["voice_dependencies"].values())
        assert "NEXIS Doctor" in smoke["pages"]
        assert smoke["themes"] == ["og", "midnight", "arctic", "cyber", "matrix", "custom"]
        assert smoke["theme_persistence"].startswith("PASS") and smoke["stylesheet_loaded"]
        assert all(smoke["native_trust"].values())
        for filename, _ in ssl_runtime_data():
            assert (folder / "_internal" / Path(filename).name).read_bytes() == Path(filename).read_bytes(), "Interpreter TLS policy resource changed or missing"
        installer_args = []
        if args.side_by_side_label:
            identity = str(uuid5(NAMESPACE_URL, "nexis-desktop/test-candidate/" + args.side_by_side_label)).upper()
            installer_args = ["/DIsolatedCandidate=" + args.side_by_side_label, "/DAppIdentity=" + identity]
            report["isolated_installer"] = {"label": args.side_by_side_label, "identity": identity,
                "program_folder": "NEXIS-" + args.side_by_side_label,
                "profile": "Normal launches share the account profile; smoke checks use isolated fixture data"}
        run("inno-setup", [str(args.iscc.resolve()), "/DAppSourceDir=" + str(folder), *installer_args, "/O" + str(output), str(ROOT / "installer/NEXIS.iss")], timeout=1200)
        archive_path = output / f"NEXIS-Desktop-{version}-Windows-x64-Portable.zip"
        with zipfile.ZipFile(archive_path, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for path in sorted(folder.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(folder.parent))
        with zipfile.ZipFile(archive_path) as archive:
            assert archive.testzip() is None
            assert hashlib.sha256(archive.read("NEXIS/NEXIS.exe")).digest() == hashlib.sha256((folder / "NEXIS.exe").read_bytes()).digest()
        assert fingerprint() == candidate, "Source changed during build; candidate evidence is invalid."
        artifacts = []
        for path in (folder / "NEXIS.exe", output / f"NEXIS-Desktop-{version}.0-Setup.exe", archive_path):
            with path.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            artifacts.append({"file": path.relative_to(output).as_posix(), "bytes": path.stat().st_size, "sha256": digest})
        manifest = {"version": version, "channel": "development", "source_sha256": candidate,
                    "python_version": platform.python_version(), "build_host_openssl_version": ssl.OPENSSL_VERSION,
                    "bundled_openssl_version": smoke["openssl_version"],
                    "interpreter_tls_policy": [{"file": Path(filename).name,
                        "sha256": hashlib.sha256(Path(filename).read_bytes()).hexdigest()}
                        for filename, _ in ssl_runtime_data()],
                    "artifacts": artifacts, "signed": False, "published": False,
                    "verdict": "NOT READY — RELEASE BLOCKED",
                    "required_owner_gates": ["Application licence / third-party compliance", "Physical microphone and audible speaker", "Live provider reliability", "Clean Windows 10/11 install, upgrade and uninstall"]}
        (output / "RELEASE-MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        (output / "SHA256SUMS.txt").write_text("".join(row["sha256"] + "  " + row["file"] + "\n" for row in artifacts), encoding="utf-8")
        report["status"] = "PASS"
        report["verification_limits"] = "Current-host frozen offline startup and ZIP CRC/identity; install, extracted portable startup and clean Windows require separate evidence."
        write()
    except Exception:
        report["status"] = "FAIL"
        write()
        raise


if __name__ == "__main__":
    main()
