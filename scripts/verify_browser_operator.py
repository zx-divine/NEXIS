"""Real CDP checks in a disposable headless Edge profile, never the owner's browser."""

import json
from pathlib import Path
import os
import site
import socket
import subprocess
import sys
import tempfile
from threading import Event
from time import monotonic
from urllib.parse import quote

root = Path(__file__).resolve().parents[1]
site.addsitedir(str(root / ".dev-deps"))
sys.path.insert(0, str(root / "src"))
from nexis.platform.browser import BrowserAdapter  # noqa: E402
from nexis.platform.discovery import known_folder  # noqa: E402

base = known_folder("B4BFCC3A-DB2C-424C-B029-7FE99A87C641") / "NEXIS-Voice-Engine"
import websocket  # noqa: E402

real_connect = websocket.create_connection
trace = []


class TracedSocket:
    def __init__(self, inner):
        self.inner = inner

    def send(self, message):
        trace.append("send:" + json.loads(message)["method"])
        return self.inner.send(message)

    def recv(self):
        trace.append("receive_started")
        result = self.inner.recv()
        trace.append("receive_completed")
        return result

    def settimeout(self, value):
        return self.inner.settimeout(value)

    def close(self):
        return self.inner.close()


def connect(*args, **kwargs):
    trace.append("websocket_connect_started")
    inner = real_connect(*args, **kwargs)
    trace.append("websocket_connected")
    return TracedSocket(inner)


websocket.create_connection = connect
report = {
    "owner_profile_used": False,
    "owner_tabs_modified": False,
    "page_load_visual_confirmation": "NOT VERIFIED",
    "stages": {},
}
paths = [
    Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)"))
    / "Microsoft/Edge/Application/msedge.exe",
    Path(os.environ.get("ProgramFiles", "C:/Program Files"))
    / "Microsoft/Edge/Application/msedge.exe",
]
edge = next((p for p in paths if p.is_file()), None)
if not edge:
    report["result"] = "NOT VERIFIED"
    report["reason"] = "Microsoft Edge executable unavailable"
else:
    with tempfile.TemporaryDirectory(
        prefix="nexis-browser-", ignore_cleanup_errors=True
    ) as temporary:
        temporary = Path(temporary).resolve()
        assert temporary.is_relative_to(
            Path(tempfile.gettempdir()).resolve()
        ) and temporary.name.startswith("nexis-browser-")
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        process = subprocess.Popen(
            [
                str(edge),
                "--headless=new",
                "--no-first-run",
                "--disable-gpu",
                "--remote-debugging-address=127.0.0.1",
                "--remote-debugging-port=" + str(port),
                "--user-data-dir=" + str(temporary),
                "about:blank",
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        adapter = BrowserAdapter(port)
        try:
            deadline = monotonic() + 20
            while True:
                try:
                    rows = adapter.tabs()
                    if rows:
                        break
                except ValueError:
                    pass
                if monotonic() > deadline:
                    raise TimeoutError("Disposable browser did not initialize")
                Event().wait(0.25)
            report["stages"]["list_tabs"] = "PASS"
            opened = json.loads(
                adapter.request("/json/new?" + quote("about:blank", safe=""), method="PUT")
            )
            tab = opened["id"]
            report["stages"]["open_tab"] = "PASS" if adapter.selected(tab) else "FAIL"
            focused = adapter.control(tab, "focus", Event())
            report["stages"]["focus_request"] = "PASS" if focused["request_accepted"] else "FAIL"
            navigated = adapter.control(tab, "navigate", Event(), "https://example.com/")
            report["stages"]["navigate_acknowledgement"] = (
                "PASS" if navigated["request_accepted"] else "FAIL"
            )
            closed = adapter.control(tab, "close", Event())
            report["stages"]["close_own_tab"] = "PASS" if closed["verified"] else "FAIL"
            report["result"] = (
                "PASS" if all(v == "PASS" for v in report["stages"].values()) else "FAIL"
            )
        except Exception as exc:
            report["result"] = "FAIL"
            report["error_type"] = type(exc).__name__
            report["message"] = (
                str(exc)
                if isinstance(exc, (ValueError, TimeoutError))
                else "Disposable browser protocol check failed"
            )
        finally:
            if process.poll() is None:
                subprocess.run(
                    ["C:/Windows/System32/taskkill.exe", "/PID", str(process.pid), "/T", "/F"],
                    capture_output=True,
                    timeout=15,
                )
                process.wait(timeout=10)
report["protocol_trace"] = trace
report["temporary_profile_cleanup"] = (
    "complete" if not edge or not temporary.exists() else "retained due to a Windows file lock"
)
if edge and temporary.exists():
    report["retained_owned_profile"] = str(temporary)
(base / "diagnostics/browser-native-controls.json").write_text(
    json.dumps(report, indent=2), encoding="utf-8"
)
print(json.dumps(report, indent=2))
