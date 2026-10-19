"""Optional existing Chromium CDP adapter. Never enables debugging or submits forms."""

import json
import re
import urllib.request
from urllib.parse import urlsplit
from uuid import uuid4
from time import monotonic

from nexis.core.providers import RejectRedirect
from nexis.utils.validation import url


class BrowserAdapter:
    def __init__(self, port):
        if type(port) is not int or not 1024 <= port <= 65535:
            raise ValueError(
                "Tab automation needs an already-running browser adapter. Set its loopback port in Settings; NEXIS never enables debugging or changes browser security."
            )
        self.port = port
        self.base = "http://127.0.0.1:" + str(port)

    def request(self, route, method="GET"):
        request = urllib.request.Request(self.base + route, method=method)
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), RejectRedirect())
        try:
            with opener.open(request, timeout=5) as response:
                data = response.read(1024 * 1024 + 1)
                if len(data) > 1024 * 1024:
                    raise ValueError("Browser adapter response exceeded its limit.")
                return data
        except OSError:
            raise ValueError(
                "Browser adapter did not respond. Ordinary website/tab opening through your default browser remains available."
            ) from None

    def tabs(self):
        try:
            rows = json.loads(self.request("/json/list"))
        except (ValueError, TypeError):
            raise ValueError("Browser adapter returned an invalid tab list.") from None
        if not isinstance(rows, list):
            raise ValueError("Invalid browser tab list.")
        return [
            r
            for r in rows[:100]
            if isinstance(r, dict)
            and r.get("type") == "page"
            and isinstance(r.get("id"), str)
            and re.fullmatch(r"[A-Za-z0-9_-]{1,128}", r["id"])
        ]

    def selected(self, identifier):
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", identifier):
            raise ValueError("Invalid browser tab identifier.")
        return next((row for row in self.tabs() if row["id"] == identifier), None)

    def control(self, identifier, operation, cancel, target=None):
        row = self.selected(identifier)
        if not row:
            raise ValueError("The selected tab no longer exists. Refresh tabs.")
        if cancel.is_set():
            raise ValueError("Browser operation cancelled.")
        if operation in {"focus", "close"}:
            self.request(
                "/json/" + ("activate" if operation == "focus" else "close") + "/" + identifier
            )
            if operation == "close":
                return {"verified": self.selected(identifier) is None, "operation": operation}
            return {"request_accepted": True, "operation": operation, "focus_verified": False}
        if operation != "navigate":
            raise ValueError("Unsupported browser operation.")
        target = url(target)
        socket_url = row.get("webSocketDebuggerUrl", "")
        parsed = urlsplit(socket_url)
        if (
            parsed.scheme != "ws"
            or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
            or parsed.port != self.port
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or not parsed.path.startswith("/devtools/page/")
        ):
            raise ValueError("Browser adapter supplied an unsafe control address.")
        import websocket

        try:
            connection = websocket.create_connection(
                socket_url,
                timeout=10,
                suppress_origin=True,
                http_no_proxy=["127.0.0.1", "localhost", "::1"],
            )
        except websocket.WebSocketException:
            raise ValueError(
                "Browser control connection timed out or was rejected. Retry the configured adapter; no navigation was verified."
            ) from None
        try:
            connection.settimeout(2)
            deadline = monotonic() + 15
            request_id = int(uuid4().hex[:8], 16)
            connection.send(
                json.dumps({"id": request_id, "method": "Page.navigate", "params": {"url": target}})
            )
            for _ in range(30):
                if cancel.is_set():
                    raise ValueError("Browser navigation cancelled.")
                if monotonic() > deadline:
                    raise ValueError(
                        "Browser navigation timed out before acknowledgement. No page load was verified."
                    )
                try:
                    raw = connection.recv()
                except websocket.WebSocketTimeoutException:
                    continue
                if len(raw) > 1024 * 1024:
                    raise ValueError("Browser message too large.")
                message = json.loads(raw)
                if message.get("id") == request_id:
                    if message.get("error") or message.get("result", {}).get("errorText"):
                        raise ValueError("Browser rejected navigation.")
                    return {"request_accepted": True, "loaded_page_verified": False, "url": target}
            raise ValueError("Browser navigation did not acknowledge the request.")
        except websocket.WebSocketException:
            raise ValueError(
                "Browser navigation failed before acknowledgement. The page was not verified; retry explicitly."
            ) from None
        finally:
            connection.close()
