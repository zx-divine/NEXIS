import json
import site
import sys
from pathlib import Path
from threading import Event

site.addsitedir(".dev-deps")
sys.path.insert(0, "src")
from PySide6.QtCore import QCoreApplication, QStandardPaths
from nexis.core.providers import ProviderStore, request_json
from nexis.platform.discovery import known_folder

app = QCoreApplication([])
app.setOrganizationName("NEXIS")
app.setApplicationName("NEXIS Desktop")
p = ProviderStore(Path(QStandardPaths.writableLocation(QStandardPaths.AppLocalDataLocation))).load()
report = {"routes": {}, "settings_changed": False}
for route in ("/api/monitoring/health", "/v1/models"):
    try:
        data = request_json(p, route, Event(), timeout=10)
        report["routes"][route] = {
            "result": "PASS",
            "data_shape": list(data)[:15] if isinstance(data, dict) else type(data).__name__,
        }
        if route == "/v1/models" and isinstance(data, dict):
            ids = [m.get("id") for m in data.get("data", []) if isinstance(m, dict)]
            report["routes"][route]["model_count"] = len(ids)
            report["routes"][route]["selected_model_available"] = p["model"] in ids
    except ValueError as exc:
        report["routes"][route] = {
            "result": "FAIL",
            "category": getattr(exc, "category", "INVALID_RESPONSE"),
            "message": str(exc),
        }
base = known_folder("B4BFCC3A-DB2C-424C-B029-7FE99A87C641") / "NEXIS-Voice-Engine"
(base / "diagnostics/omniroute-routes.json").write_text(
    json.dumps(report, indent=2), encoding="utf-8"
)
print(json.dumps(report, indent=2))
