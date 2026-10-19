"""Smoke the frozen application with a temporary database and no Python on PATH."""

import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import ctypes
import tomllib

root = Path(__file__).resolve().parents[1]
folder = root / "dist" / "NEXIS"
exe = folder / "NEXIS.exe"
if not exe.is_file():
    raise SystemExit("Build dist/NEXIS/NEXIS.exe first.")
version = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
output = root / "docs" / ("package-smoke-v" + version)
environment = {
    k: v for k, v in os.environ.items() if k not in {"PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"}
}
environment["QT_QPA_PLATFORM"] = "offscreen"
environment["PATH"] = str(Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32")
if "--diagnose" in sys.argv:
    # Use the official console bootloader and the already generated application archive.
    # This is a temporary diagnostic binary, never the distributed GUI executable.
    diagnostic = folder / "NEXIS-console-check.exe"
    if diagnostic.exists():
        raise SystemExit("Temporary diagnostic filename already exists; inspect it first.")
    bootloader = root / ".dev-deps/PyInstaller/bootloader/Windows-64bit-intel/run.exe"
    candidates = [
        root / directory / "NEXIS/NEXIS.pkg"
        for directory in (
            ".packaging-work-operator",
            ".packaging-work-v13",
            ".packaging-work-branding",
            ".packaging-work-v11",
            ".packaging-work",
            "build",
        )
    ]
    archive = max(
        (path for path in candidates if path.is_file()), key=lambda path: path.stat().st_mtime
    )
    ctypes.windll.kernel32.SetErrorMode(0x8003)
    try:
        diagnostic.write_bytes(bootloader.read_bytes() + archive.read_bytes())
        result = subprocess.run(
            [str(diagnostic), "--smoke-test", str(output)],
            env=environment,
            cwd=root,
            timeout=30,
            text=True,
            capture_output=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        (root / "docs/quick-package-diagnostic.txt").write_text(
            result.stdout + result.stderr, encoding="utf-8"
        )
        print("Diagnostic exit:", result.returncode, flush=True)
        print(result.stdout + result.stderr, flush=True)
    finally:
        diagnostic.unlink(missing_ok=True)
    raise SystemExit(result.returncode)
subprocess.run(
    [str(exe), "--smoke-test", str(output), "--offline-smoke"], env=environment, cwd=root, timeout=120, check=True
)
report = json.loads((output / "packaged-smoke.json").read_text(encoding="utf-8"))
assert report["ok"] and report["frozen"] and report["stylesheet_loaded"]
assert report["bundled_model"]["loaded"] and report["bundled_model"]["inside_package"]
assert report["bundled_model"]["files_verified"] == 14
assert report["bundled_model"]["narrowband_default_selected_rate"] == 16000
assert report["bundled_model"]["synthetic_pcm_decoder_check"] == "PASS"
assert report["python_network_blocked"] and report["network_connection_attempts"] == 0
assert report["windows_plugin_present"]
assert report["application_icon_loaded"] and report["window_icon_loaded"]
assert report["about_logo_loaded"] and report["wizard_completed"]
assert report["app_user_model_id_matches"]
assert report["schema_version"] == 3
assert all(state == "available" for state in report["voice_dependencies"].values())
assert (
    report["logo_sha256"]
    == hashlib.sha256((root / "assets/branding/NEXIS_logo.png").read_bytes()).hexdigest()
)
assert Path(report["logo_path"]).is_relative_to(folder)
files = [p for p in folder.rglob("*") if p.is_file()]
chromium = [p.name for p in files if "webengine" in p.name.lower() or "chromium" in p.name.lower()]
assert not chromium, "Unexpected Chromium/WebEngine component in distribution"
binary = exe.read_bytes()
pe_offset = struct.unpack_from("<I", binary, 0x3C)[0]
assert struct.unpack_from("<H", binary, pe_offset + 4)[0] == 0x8664, (
    "Expected Windows x64 executable"
)
sys.path.insert(0, str(root / ".dev-deps"))
import pefile  # noqa: E402

pe = pefile.PE(str(exe))
icon_groups = next(e for e in pe.DIRECTORY_ENTRY_RESOURCE.entries if e.id == 14)
icon_sizes = set()
for group in icon_groups.directory.entries:
    for language in group.directory.entries:
        entry = language.data.struct
        data = pe.get_data(entry.OffsetToData, entry.Size)
        count = struct.unpack_from("<H", data, 4)[0]
        icon_sizes.update(data[6 + i * 14] or 256 for i in range(count))
assert icon_sizes == {16, 24, 32, 48, 64, 128, 256}
fixed = pe.VS_FIXEDFILEINFO[0]
actual_version = (fixed.FileVersionMS >> 16, fixed.FileVersionMS & 65535, fixed.FileVersionLS >> 16)
assert actual_version == tuple(int(part) for part in version.split("."))
report.update(
    {
        "file_version": ".".join(str(part) for part in actual_version),
        "exe_sha256": hashlib.sha256(binary).hexdigest(),
        "distribution_files": len(files),
        "distribution_mb": round(sum(p.stat().st_size for p in files) / 1048576, 2),
        "chromium_files": chromium,
        "python_removed_from_path": True,
        "clean_machine_verified": False,
        "embedded_icon_sizes": sorted(icon_sizes),
    }
)
(output / "package-verification.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2))
