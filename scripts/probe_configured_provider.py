"""Authorized real provider probe; never prints credentials or raw server errors."""

import json
from pathlib import Path
import site
import sys
from threading import Event
from datetime import datetime, timezone

site.addsitedir(str(Path(__file__).resolve().parents[1] / ".provider-deps"))
site.addsitedir(".dev-deps")
sys.path.insert(0, "src")
from PySide6.QtCore import QCoreApplication, QStandardPaths
from nexis.core.providers import ProviderStore, ProviderError, chat
from nexis.platform.discovery import known_folder

app = QCoreApplication([])
app.setOrganizationName("NEXIS")
app.setApplicationName("NEXIS Desktop")
data = Path(QStandardPaths.writableLocation(QStandardPaths.AppLocalDataLocation))
base = known_folder("B4BFCC3A-DB2C-424C-B029-7FE99A87C641") / "NEXIS-Voice-Engine"
report = {
    "time_utc": datetime.now(timezone.utc).isoformat(),
    "test": "Owner-authorized minimal real configured-provider chat; no audio or logs sent",
    "credentials_printed": False,
    "provider_switched": False,
    "generic_connectivity_precheck": False,
}
try:
    profile = ProviderStore(data).load()
    if not profile:
        report.update(result="NOT VERIFIED", category="MISSING_CONFIGURATION")
    else:
        response = chat(profile, "Reply with exactly: NEXIS connectivity verified.", Event())
        report.update(result="PASS", response=response, provider=profile["provider"])
except ProviderError as exc:
    report.update(result="FAIL", category=exc.category, message=str(exc))
except ValueError as exc:
    report.update(result="FAIL", category="CONFIGURATION", message=str(exc))
except Exception as exc:
    report.update(result="FAIL", category=type(exc).__name__)
(base / "diagnostics/real-provider-probe.json").write_text(
    json.dumps(report, indent=2), encoding="utf-8"
)
print(json.dumps(report, indent=2))
