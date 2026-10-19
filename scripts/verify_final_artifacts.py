"""Finalize local artifact identity and read-only Windows discovery evidence."""

import hashlib
import json
from pathlib import Path
import site
import sys
from threading import Event
from time import monotonic
import zipfile

root = Path(__file__).resolve().parents[1]
site.addsitedir(str(root / ".dev-deps"))
sys.path.insert(0, str(root / "src"))
from nexis.platform.discovery import discover  # noqa: E402


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


manifest = json.loads((root / "docs/v13-source-manifest.json").read_text())
assert all(digest(root / name) == expected for name, expected in manifest.items())
installed_report = json.loads(
    (root / "docs/v13-installed-verification/verification.json").read_text()
)
installed = Path(installed_report["installed_directory"])
distribution = root / "dist/NEXIS"
files = [p for p in distribution.rglob("*") if p.is_file()]
assert all(digest(p) == digest(installed / p.relative_to(distribution)) for p in files)
artifacts = []
for name in (
    "dist/NEXIS/NEXIS.exe",
    "dist/installer/NEXIS-Desktop-1.3.0.0-Setup.exe",
    "dist/NEXIS-Desktop-1.3.0-Windows-x64-Portable.zip",
):
    path = root / name
    artifacts.append({"path": name, "bytes": path.stat().st_size, "sha256": digest(path)})
portable = json.loads((root / "docs/v13-portable-verification/verification.json").read_text())
assert artifacts[2]["sha256"] == portable["sha256"]
with zipfile.ZipFile(root / artifacts[2]["path"]) as archive:
    assert archive.testzip() is None
    assert hashlib.sha256(archive.read("NEXIS/NEXIS.exe")).hexdigest() == artifacts[0]["sha256"]
started = monotonic()
applications, issues = discover(Event())
assert applications, "Read-only host discovery returned no applications"
report = {
    "version": "1.3.0",
    "host": "Windows 10 x64 build 19045",
    "artifacts": artifacts,
    "source_manifest_verified": True,
    "source_files": len(manifest),
    "installed_distribution_files_identical": len(files),
    "portable_crc_verified": True,
    "portable_executable_identical": True,
    "installed_startup_verified": installed_report["smoke"]["ok"],
    "portable_startup_verified": portable["smoke"]["ok"],
    "installed_user_database_unchanged": installed_report["user_data_unchanged"],
    "shortcuts": installed_report["shortcuts"],
    "final_host_discovery": {
        "application_count": len(applications),
        "seconds": round(monotonic() - started, 2),
        "issues": issues,
        "launched_applications": False,
        "execution": "source engine matching frozen-build manifest; frozen diagnostic ends after five seconds",
    },
    "regression": json.loads((root / "docs/v13-final-regression.json").read_text()),
    "clean_windows10": "NOT VERIFIED",
    "clean_windows11": "NOT VERIFIED",
    "physical_audio": "NOT VERIFIED",
    "live_taskbar_grouping": "NOT VERIFIED",
    "published": False,
}
(root / "docs/v13-artifacts.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2))
