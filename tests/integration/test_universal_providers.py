"""Deterministic provider protocol tests. Gemini uses its real SDK over a mock transport."""

import io
import json
import socket
import ssl
from threading import Event
from urllib.error import HTTPError, URLError
import pytest
from nexis.core.providers import request_json, ProviderError, validate_profile
from nexis.core.provider_manager import generate, models


def profile(**extra):
    return {
        "provider": "Custom API Gateway",
        "display_name": "Gateway fixture",
        "endpoint": "https://gateway.example/v1",
        "key": "PRIVATE-FIXTURE-KEY",
        "model": "runtime-fixture",
        **extra,
    }


@pytest.mark.parametrize(
    "reason,category",
    [
        (socket.gaierror(11001, "private host"), "DNS"),
        (ssl.SSLCertVerificationError("private certificate"), "TLS"),
        (TimeoutError("private timeout"), "TIMEOUT"),
        (ConnectionRefusedError("private address"), "CONNECTION"),
    ],
)
def test_network_errors_are_specific_and_do_not_leak(reason, category):
    def fail(*a, **k):
        raise URLError(reason)

    with pytest.raises(ProviderError) as error:
        request_json(profile(), "/models", Event(), opener=fail)
    assert error.value.category == category and "private" not in str(error.value)
    assert "offline" not in str(error.value).casefold()


@pytest.mark.parametrize(
    "status,category",
    [
        (401, "AUTHENTICATION"),
        (403, "AUTHENTICATION"),
        (429, "RATE_LIMIT"),
        (500, "SERVER_ERROR"),
        (404, "ENDPOINT_OR_MODEL"),
    ],
)
def test_http_errors_are_specific(status, category):
    def fail(*a, **k):
        raise HTTPError("https://gateway.example", status, "private body", {}, io.BytesIO(b"{}"))

    with pytest.raises(ProviderError) as error:
        request_json(profile(), "/models", Event(), opener=fail)
    assert error.value.category == category and "private body" not in str(error.value)


class Response(io.BytesIO):
    def __init__(self, data, streaming=False):
        super().__init__(data)
        self.headers = {"Content-Type": "text/event-stream" if streaming else "application/json"}

    def read1(self, size):
        return self.read(min(size, 13))


@pytest.mark.parametrize("line_ending", ["\n", "\r\n"])
def test_custom_route_authentication_and_streaming(line_ending):
    events = [
        {"choices": [{"delta": {"content": "Hello PRIVATE-"}}]},
        {"choices": [{"delta": {"content": "FIXTURE-KEY friend"}}]},
    ]
    data = "".join("data: " + json.dumps(e) + "\n\n" for e in events) + "data: [DONE]\n\n"
    data = data.replace("\n", line_ending)
    seen, chunks = [], []

    def open_request(request, timeout):
        seen.append((request.full_url, request.get_header("X-owner-token"), timeout))
        assert json.loads(request.data)["stream"] is True
        return Response(data.encode(), True)

    result = generate(
        profile(
            api_path="/custom/chat",
            auth="Custom header",
            auth_header="X-Owner-Token",
            stream=True,
            timeout=17,
        ),
        [{"role": "user", "content": "hello"}],
        Event(),
        opener=open_request,
        on_chunk=chunks.append,
    )
    assert seen == [("https://gateway.example/v1/custom/chat", "PRIVATE-FIXTURE-KEY", 17)]
    assert result["text"] == "Hello [redacted] friend"
    assert chunks and all("PRIVATE-FIXTURE-KEY" not in chunk for chunk in chunks)


def test_interrupted_stream_is_not_reported_as_success():
    data = b'data: {"choices":[{"delta":{"content":"partial"}}]}\n\n'
    with pytest.raises(ProviderError, match="INTERRUPTED_STREAM"):
        generate(
            profile(stream=True),
            [{"role": "user", "content": "hi"}],
            Event(),
            opener=lambda *a, **k: Response(data, True),
        )


def test_tool_call_arguments_remain_untrusted_until_registry_validation():
    body = {
        "choices": [
            {
                "message": {
                    "tool_calls": [
                        {
                            "function": {
                                "name": "unknown_shell",
                                "arguments": '{"command":"anything"}',
                            }
                        }
                    ]
                }
            }
        ]
    }
    result = generate(
        profile(native_tools=True),
        [{"role": "user", "content": "hi"}],
        Event(),
        opener=lambda *a, **k: Response(json.dumps(body).encode()),
    )
    from nexis.core.tools import validate_steps

    with pytest.raises(ValueError):
        validate_steps(result["calls"])


@pytest.mark.parametrize(
    "bad",
    [
        {"protocol": "anthropic"},
        {"api_path": "https://another.example/chat"},
        {"api_path": "/../secrets"},
        {"auth_header": "Host"},
        {"timeout": 999},
        {"stream": "yes"},
    ],
)
def test_unsupported_protocol_or_unintended_destination_is_rejected(bad):
    with pytest.raises(ValueError):
        validate_profile(profile(**bad))


@pytest.fixture
def gemini_sdk(monkeypatch):
    import httpx
    from google import genai
    from google.genai import types

    seen = []
    replies = {"status": 200, "text": "Gemini SDK fixture answer", "function": False}

    def handler(request):
        seen.append(request)
        if replies["status"] != 200:
            return httpx.Response(
                replies["status"],
                json={
                    "error": {
                        "code": replies["status"],
                        "message": "PRIVATE-FIXTURE-KEY must not leak",
                        "status": "RESOURCE_EXHAUSTED",
                    }
                },
                request=request,
            )
        if request.method == "GET":
            body = {
                "models": [
                    {
                        "name": "models/runtime-fixture",
                        "supportedGenerationMethods": ["generateContent"],
                    },
                    {
                        "name": "models/embed-fixture",
                        "supportedGenerationMethods": ["embedContent"],
                    },
                ]
            }
        else:
            parts = (
                [{"functionCall": {"name": "volume_get", "args": {}}}]
                if replies["function"]
                else [{"text": replies["text"]}]
            )
            body = {
                "candidates": [
                    {"content": {"role": "model", "parts": parts}, "finishReason": "STOP"}
                ]
            }
        if "streamGenerateContent" in request.url.path:
            return httpx.Response(
                200,
                headers={"Content-Type": "text/event-stream"},
                text="data: " + json.dumps(body) + "\n\n",
                request=request,
            )
        return httpx.Response(200, json=body, request=request)

    def factory(config):
        return genai.Client(
            api_key=config["key"],
            vertexai=False,
            http_options=types.HttpOptions(
                timeout=5000,
                retry_options=types.HttpRetryOptions(attempts=1),
                client_args={"transport": httpx.MockTransport(handler)},
            ),
        )

    monkeypatch.setattr("nexis.core.provider_manager.gemini_client", factory)
    return replies, seen


def gemini(**extra):
    return {
        "provider": "Google Gemini",
        "endpoint": "https://generativelanguage.googleapis.com",
        "key": "PRIVATE-FIXTURE-KEY",
        "model": "models/runtime-fixture",
        **extra,
    }


def test_native_gemini_sdk_model_discovery_and_inference(gemini_sdk):
    replies, seen = gemini_sdk
    assert models(gemini(), Event()) == ["models/runtime-fixture"]
    assert (
        generate(gemini(), [{"role": "user", "content": "नमस्ते"}], Event())["text"]
        == "Gemini SDK fixture answer"
    )
    assert len(seen) == 2 and all(r.url.host == "generativelanguage.googleapis.com" for r in seen)


def test_native_gemini_streaming_and_manual_function_calling(gemini_sdk):
    replies, seen = gemini_sdk
    chunks = []
    response = generate(
        gemini(stream=True), [{"role": "user", "content": "hello"}], Event(), on_chunk=chunks.append
    )
    assert response["text"] == "Gemini SDK fixture answer" and chunks
    replies["function"] = True
    result = generate(
        gemini(),
        [{"role": "user", "content": "get volume"}],
        Event(),
        tools=[
            {
                "name": "volume_get",
                "description": "Read volume",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                    "additionalProperties": False,
                },
            }
        ],
    )
    assert result["calls"] == [{"tool": "volume_get", "arguments": {}}]
    sent = json.loads(seen[-1].content)
    assert sent["tools"][0]["functionDeclarations"][0]["name"] == "volume_get"


@pytest.mark.parametrize(
    "code,category",
    [(403, "AUTHENTICATION"), (429, "RATE_LIMIT"), (404, "INVALID_MODEL"), (500, "SERVER_ERROR")],
)
def test_native_gemini_sdk_errors_are_redacted(gemini_sdk, code, category):
    gemini_sdk[0]["status"] = code
    with pytest.raises(ProviderError) as error:
        generate(gemini(), [{"role": "user", "content": "hello"}], Event())
    assert error.value.category == category and "PRIVATE-FIXTURE-KEY" not in str(error.value)


@pytest.mark.parametrize(
    "base,expected",
    [
        ("http://localhost:20128", "/v1/chat/completions"),
        ("http://localhost:20128/v1", "/chat/completions"),
    ],
)
def test_omniroute_root_and_versioned_addresses_use_correct_routes(base, expected):
    config = validate_profile(
        {"provider": "OmniRoute", "endpoint": base, "key": "fixture", "model": "fixture"}
    )
    assert config["api_path"] == expected
    assert config["endpoint"] == base  # Original settings are not rewritten.


def test_omniroute_upstream_unavailable_is_not_mislabeled_offline():
    def fail(*a, **k):
        raise HTTPError(
            "http://localhost:20128/v1/chat/completions",
            503,
            "Service Unavailable",
            {},
            io.BytesIO(b'{"error":{"message":"upstream unavailable: not configured"}}'),
        )

    with pytest.raises(ProviderError) as error:
        request_json(profile(), "/chat/completions", Event(), opener=fail)
    assert error.value.category == "SERVER_ERROR" and "HTTP 503" in str(error.value)
    assert "upstream" in str(error.value) and "offline" not in str(error.value).casefold()


def test_quoted_secret_is_redacted_inside_structured_tool_arguments():
    config = profile(key='token-with-"quote')
    body = {
        "choices": [
            {
                "message": {
                    "tool_calls": [
                        {
                            "function": {
                                "name": "file_create_text",
                                "arguments": json.dumps(
                                    {"path": "C:/approved/file.txt", "text": config["key"]}
                                ),
                            }
                        }
                    ]
                }
            }
        ]
    }
    result = generate(
        config,
        [{"role": "user", "content": "test"}],
        Event(),
        opener=lambda *a, **k: Response(json.dumps(body).encode()),
    )
    assert result["calls"][0]["arguments"]["text"] == "[redacted]"
