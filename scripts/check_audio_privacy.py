"""Read Windows audio privacy and endpoint state without opening audio streams."""

import json
from pathlib import Path
import site
import sys
import winreg

root = Path(__file__).resolve().parents[1]
site.addsitedir(str(root / ".dev-deps"))
sys.path.insert(0, str(root / "src"))
from nexis.platform.operator_windows import audio_volume  # noqa: E402
from nexis.platform.discovery import known_folder  # noqa: E402

report = {"microphone_opened": False, "settings_changed": False, "privacy": {}}
for title, hive, key, field in [
    (
        "user_microphone",
        winreg.HKEY_CURRENT_USER,
        r"Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\microphone",
        "Value",
    ),
    (
        "machine_microphone",
        winreg.HKEY_LOCAL_MACHINE,
        r"Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\microphone",
        "Value",
    ),
    (
        "app_microphone_policy",
        winreg.HKEY_LOCAL_MACHINE,
        r"Software\Policies\Microsoft\Windows\AppPrivacy",
        "LetAppsAccessMicrophone",
    ),
]:
    try:
        with winreg.OpenKey(hive, key) as handle:
            report["privacy"][title] = winreg.QueryValueEx(handle, field)[0]
    except OSError:
        report["privacy"][title] = "No explicit value accessible"
for name, capture in [("speaker", False), ("microphone", True)]:
    try:
        report[name] = audio_volume(capture=capture)
    except Exception as exc:
        report[name] = {"result": "NOT VERIFIED", "error_type": type(exc).__name__}
base = known_folder("B4BFCC3A-DB2C-424C-B029-7FE99A87C641") / "NEXIS-Voice-Engine"
(base / "diagnostics/audio-privacy-readonly.json").write_text(
    json.dumps(report, indent=2), encoding="utf-8"
)
print(json.dumps(report, indent=2))
