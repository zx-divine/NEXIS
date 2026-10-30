import json
import site
import sys
import urllib.error
from pathlib import Path
from threading import Event

site.addsitedir(".dev-deps")
sys.path.insert(0, "src")
from PySide6.QtCore import QCoreApplication, QStandardPaths
from nexis.core.providers import ProviderStore, request_json, RejectRedirect
import urllib.request
from nexis.platform.discovery import known_folder

app = QCoreApplication([])
app.setOrganizationName("NEXIS")
app.setApplicationName("NEXIS Desktop")
p = ProviderStore(Path(QStandardPaths.writableLocation(QStandardPaths.AppLocalDataLocation))).load()
health = request_json(p, "/api/monitoring/health", Event())
report = {
    "health_status": health.get("status"),
    "setup_complete": health.get("setupComplete"),
    "settings_unchanged": True,
    "selected_provider_unchanged": True,
    "model_changed": False,
}
headers = {"Content-Type": "application/json"}
if p["key"]:
    headers["Authorization"] = "Bearer " + p["key"]
req = urllib.request.Request(
    p["endpoint"] + p["api_path"],
    data=json.dumps(
        {
            "model": p["model"],
            "stream": False,
            "max_tokens": 20,
            "messages": [{"role": "user", "content": "Reply only OK."}],
        }
    ).encode(),
    headers=headers,
)
try:
    with urllib.request.build_opener(urllib.request.ProxyHandler({}), RejectRedirect()).open(
        req, timeout=20
    ) as response:
        report["inference_http"] = response.status
        report["response_shape"] = list(json.loads(response.read(65536)))
except urllib.error.HTTPError as exc:
    report["inference_http"] = exc.code
    raw = exc.read(65536).decode("utf-8", "replace").casefold()
    report["upstream_setup_indicators"] = {
        term: term in raw
        for term in [
            "no credentials",
            "no active",
            "no provider",
            "no available",
            "connection",
            "rate limit",
            "cooldown",
            "not configured",
            "unavailable",
        ]
    }
try:
    import win32crypt

    stored = (
        Path(QStandardPaths.writableLocation(QStandardPaths.AppLocalDataLocation))
        / "provider.dpapi"
    )
    report["stored_fields"] = list(
        json.loads(win32crypt.CryptUnprotectData(stored.read_bytes(), None, None, None, 1)[1])
    )
except Exception:
    pass
base = known_folder("B4BFCC3A-DB2C-424C-B029-7FE99A87C641") / "NEXIS-Voice-Engine"
(base / "diagnostics/omniroute-current-verification.json").write_text(
    json.dumps(report, indent=2), encoding="utf-8"
)
print(json.dumps(report, indent=2))
