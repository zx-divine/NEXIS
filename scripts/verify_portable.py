"""Create and verify the complete local portable archive; never uploads anything."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import tomllib
import zipfile

root = Path(__file__).resolve().parents[1]
version = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
folder = root / "dist/NEXIS"
assert (folder / "NEXIS.exe").is_file(), "Build the application first"
destination = root / "dist" / f"NEXIS-Desktop-{version}-Windows-x64-Portable.zip"
with zipfile.ZipFile(
    destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6
) as archive:
    for path in sorted(folder.rglob("*")):
        if path.is_file():
            archive.write(path, path.relative_to(folder.parent))
output = root / "docs/installer-overhaul/portable"
output.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="nexis-portable-", ignore_cleanup_errors=True) as temporary:
    base = Path(temporary)
    with zipfile.ZipFile(destination) as archive:
        assert archive.testzip() is None, "Archive CRC check failed"
        assert all(
            not Path(name).is_absolute() and ".." not in Path(name).parts
            for name in archive.namelist()
        )
        archive.extractall(base)
    environment = {
        k: v for k, v in os.environ.items() if k not in {"PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"}
    }
    environment["PATH"] = str(Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32")
    environment["QT_QPA_PLATFORM"] = "windows"
    subprocess.run(
        [str(base / "NEXIS/NEXIS.exe"), "--smoke-test", str(output), "--capability-smoke"],
        cwd=base,
        env=environment,
        timeout=120,
        check=True,
    )
    result = json.loads((output / "packaged-smoke.json").read_text(encoding="utf-8"))
    assert result["frozen"] and result["ok"] and result["app_user_model_id_matches"]
    assert result["wizard_completed"] and result["about_logo_loaded"]
    assert result["schema_version"] == 3
    assert result["bundled_model"]["loaded"] and result["bundled_model"]["inside_package"]
    assert result["bundled_model"]["files_verified"] == 14
    assert all(value == "available" for value in result["voice_dependencies"].values())
    assert Path(result["logo_path"]).is_relative_to(base)
report = {
    "portable_zip": str(destination),
    "bytes": destination.stat().st_size,
    "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
    "zip_crc_verified": True,
    "extracted_launch_verified": True,
    "python_removed_from_path": True,
    "clean_machine_without_python": "NOT VERIFIED",
    "smoke": result,
    "temporary_cleanup": "Windows retained files; cleanup must be retried"
    if base.exists()
    else "complete",
    "temporary_directory": str(base) if base.exists() else None,
}
(output / "verification.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2))
