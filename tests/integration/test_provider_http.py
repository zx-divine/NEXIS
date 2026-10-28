import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Event, Thread

import pytest

from nexis.core.providers import chat, list_models


@pytest.fixture
def gateway():
    received = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            received.append((self.path, self.headers.get("Authorization")))
            if self.path.startswith("/redirect"):
                self.send_response(302)
                self.send_header("Location", "/stolen/models")
                self.end_headers()
                return
            if self.path.startswith("/invalid"):
                self.send_response(401)
                self.end_headers()
                self.wfile.write(b"must not expose server's sensitive error text")
                return
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps({"data": [{"id": "fixture-chat"}]}).encode())

        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            received.append(payload)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(
                json.dumps(
                    {"choices": [{"message": {"content": "Hello — नमस्ते"}}]}, ensure_ascii=False
                ).encode()
            )

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", received
    finally:
        server.shutdown()
        server.server_close()
        thread.join(2)


def test_real_http_compatible_chat_has_no_execution_tools(gateway):
    address, received = gateway
    config = {
        "provider": "Compatible gateway",
        "endpoint": address + "/v1",
        "model": "fixture-chat",
        "key": "fixture-key",
    }
    assert list_models(config, Event()) == ["fixture-chat"]
    assert chat(config, "नमस्ते", Event()) == "Hello — नमस्ते"
    assert received[0] == ("/v1/models", "Bearer fixture-key")
    assert "tools" not in received[1]
    assert received[1]["messages"][-1]["content"] == "नमस्ते"


def test_ollama_compatible_local_http_models_and_chat_without_authentication(gateway):
    address, received = gateway
    config = {"provider": "Ollama", "endpoint": address + "/v1", "model": "fixture-chat", "key": "", "auth": "None"}
    assert list_models(config, Event()) == ["fixture-chat"]
    assert chat(config, "hello", Event()) == "Hello — नमस्ते"
    assert received[0] == ("/v1/models", None)
    assert received[1]["model"] == "fixture-chat"
    assert "tools" not in received[1]


def test_redirects_and_authentication_failures_do_not_leak(gateway):
    address, received = gateway
    config = {
        "provider": "Compatible gateway",
        "endpoint": address + "/redirect",
        "key": "fixture-key",
    }
    with pytest.raises(ValueError, match="redirected"):
        list_models(config, Event())
    assert len(received) == 1
    config["endpoint"] = address + "/invalid"
    with pytest.raises(ValueError, match="authentication") as error:
        list_models(config, Event())
    assert "sensitive" not in str(error.value)
