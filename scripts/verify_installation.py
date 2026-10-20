"""Verify the local per-user installer and shortcuts without touching user data."""

import hashlib
import json
import os
from pathlib import Path
import site
import subprocess
import sys
import tomllib

root = Path(__file__).resolve().parents[1]
site.addsitedir(str(root / ".dev-deps"))
sys.path.insert(0, str(root / "src"))
from nexis.platform.discovery import known_folder  # noqa: E402
from PySide6.QtCore import QCoreApplication, QStandardPaths  # noqa: E402

if "--install" not in sys.argv:
    raise SystemExit("Use --install only for an authorized local installation test.")
app = QCoreApplication([])
app.setOrganizationName("NEXIS")
app.setApplicationName("NEXIS Desktop")
data = Path(QStandardPaths.writableLocation(QStandardPaths.AppLocalDataLocation))
files = [data / name for name in ("nexis.db", "provider.dpapi", "providers.dpapi")]


def snapshot():
    return {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
        for path in files
    }


before = snapshot()
output = root / "docs/installer-overhaul/installed"
output.mkdir(parents=True, exist_ok=True)
version = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
installer = root / "dist/installer" / ("NEXIS-Desktop-" + version + ".0-Setup.exe")
subprocess.run(
    [
        str(installer),
        "/VERYSILENT",
        "/SUPPRESSMSGBOXES",
        "/NORESTART",
        "/CURRENTUSER",
        "/TASKS=desktopicon",
        "/LOG=" + str(output / "install.log"),
    ],
    timeout=240,
    check=True,
)
assert before == snapshot(), "Installer changed existing user database or provider profile"
directory = known_folder("F1B32785-6FBA-4FCF-9D55-7B8E7F157091") / "Programs/NEXIS Desktop"
installed = directory / "NEXIS.exe"
assert installed.read_bytes() == (root / "dist/NEXIS/NEXIS.exe").read_bytes()
shortcuts = []
for path in (
    known_folder("A77F5D77-2E2B-44C3-A6A2-ABA601054A51") / "NEXIS Desktop/NEXIS Desktop.lnk",
    known_folder("B4BFCC3A-DB2C-424C-B029-7FE99A87C641") / "NEXIS Desktop.lnk",
):
    result = subprocess.run(
        [
            str(Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32/cscript.exe"),
            "//nologo",
            str(root / "scripts/read_shortcut.js"),
            str(path),
        ],
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
    )
    lines = result.stdout.strip().splitlines()
    assert len(lines) == 3 and lines[2] == "NEXIS.Desktop"
    assert Path(lines[0]) == installed and lines[1] == str(installed) + ",0"
    shortcuts.append(
        {"path": str(path), "target": lines[0], "icon": lines[1], "app_user_model_id": lines[2]}
    )
environment = {
    k: v for k, v in os.environ.items() if k not in {"PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"}
}
environment["PATH"] = str(Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32")
environment["QT_QPA_PLATFORM"] = "windows"
subprocess.run(
    [str(installed), "--smoke-test", str(output), "--capability-smoke"],
    cwd=directory,
    env=environment,
    timeout=120,
    check=True,
)
smoke = json.loads((output / "packaged-smoke.json").read_text(encoding="utf-8"))
assert smoke["frozen"] and smoke["ok"] and smoke["app_user_model_id_matches"]
assert smoke["app_version"] == version and smoke["workflow_fixture_check"]["result"] == "PASS"
assert all(value == "available" for value in smoke["voice_dependencies"].values())
assert smoke["bundled_model"]["loaded"] and smoke["bundled_model"]["inside_package"]
assert smoke["bundled_model"]["files_verified"] == 14
assert Path(smoke["logo_path"]).is_relative_to(directory)
assert before == snapshot(), "Isolated smoke test changed actual user data"
report = {
    "installed_directory": str(directory),
    "installed_executable_matches": True,
    "user_data_unchanged": True,
    "user_data_existed": {key: value is not None for key, value in before.items()},
    "shortcuts": shortcuts,
    "smoke": smoke,
    "clean_windows10": "NOT VERIFIED",
    "clean_windows11": "NOT VERIFIED",
}
(output / "verification.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2))
