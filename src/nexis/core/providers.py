"""Bounded compatible chat client. Provider text never executes OS commands."""

import json
import math
import os
from pathlib import Path
import re
import socket
import ssl
import urllib.error
import urllib.request
from time import monotonic
from urllib.parse import urlsplit

DEFAULT_ENDPOINTS = {
    "OpenRouter": "https://openrouter.ai/api/v1",
    "OmniRoute": "http://127.0.0.1:20128/v1",
    "Compatible gateway": "",
    "OpenAI-compatible": "",
    "Custom API Gateway": "",
    "Google Gemini": "https://generativelanguage.googleapis.com",
}
LEGACY_PROVIDER_TYPES = {"Ollama", "LM Studio"}


class ProviderError(ValueError):
    """A safe actionable category, without server bodies, keys or raw URLs."""

    def __init__(self, category, message):
        self.category = category
        super().__init__(category + ": " + message)


def endpoint(value):
    if (
        not isinstance(value, str)
        or len(value) > 2048
        or any(c.isspace() or ord(c) < 32 for c in value)
    ):
        raise ValueError("Enter a valid provider address.")
    try:
        parsed = urlsplit(value)
        local = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        if (
            not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or "\\" in value
            or parsed.scheme not in {"http", "https"}
            or parsed.scheme == "http"
            and not local
            or parsed.port == 0
        ):
            raise ValueError()
    except ValueError:
        raise ValueError(
            "Use HTTPS for remote providers, or HTTP on localhost. Put credentials in the key field."
        ) from None
    return value.rstrip("/")


def validate_profile(profile):
    result = dict(profile)
    result["endpoint"] = endpoint(profile.get("endpoint", ""))
    if profile.get("provider") not in {*DEFAULT_ENDPOINTS, *LEGACY_PROVIDER_TYPES}:
        raise ValueError("Choose a supported provider type.")
    for field in ("key", "model"):
        value = profile.get(field, "")
        if not isinstance(value, str) or len(value) > 8192 or any(ord(c) < 32 for c in value):
            raise ValueError("Invalid provider field.")
    if profile.get("auth", "Bearer") not in {"Bearer", "api-key", "None", "Custom header"}:
        raise ValueError("Unsupported authentication type.")
    headers = profile.get("headers", {})
    if not isinstance(headers, dict) or len(headers) > 10:
        raise ValueError("Invalid custom headers.")
    for key, value in headers.items():
        if (
            not re.fullmatch(r"[A-Za-z0-9-]{1,64}", key)
            or key.casefold()
            in {
                "host",
                "content-length",
                "authorization",
                "connection",
                "transfer-encoding",
                "proxy-authorization",
            }
            or not isinstance(value, str)
            or len(value) > 2048
            or any(ord(c) < 32 or ord(c) > 126 for c in value)
        ):
            raise ValueError(
                "Invalid custom header. Use the dedicated authentication selector for credentials."
            )
    protocol = profile.get(
        "protocol", "gemini" if profile.get("provider") == "Google Gemini" else "openai"
    )
    if protocol not in {"openai", "gemini"}:
        raise ProviderError(
            "UNSUPPORTED_PROTOCOL",
            "Use the OpenAI-compatible adapter or native Google Gemini adapter.",
        )
    if protocol == "gemini" and result["endpoint"] != "https://generativelanguage.googleapis.com":
        raise ValueError(
            "Native Gemini uses the official Google API address. Use a compatible gateway adapter for other addresses."
        )
    result["protocol"] = protocol
    prefix = (
        "/v1"
        if profile.get("provider") == "OmniRoute"
        and not urlsplit(result["endpoint"]).path.rstrip("/")
        else ""
    )
    for field, default in (
        ("api_path", prefix + "/chat/completions"),
        ("models_path", prefix + "/models"),
    ):
        route = profile.get(field, default)
        if (
            not isinstance(route, str)
            or not re.fullmatch(r"/[A-Za-z0-9_./-]{1,255}", route)
            or ".." in route
            or "//" in route
        ):
            raise ValueError(
                "API paths must be relative routes on the configured base URL, without queries or traversal."
            )
        result[field] = route
    timeout = profile.get("timeout", 20)
    if type(timeout) is not int or not 5 <= timeout <= 120:
        raise ValueError("Request timeout must be 5–120 seconds.")
    result["timeout"] = timeout
    for field in ("stream", "native_tools"):
        if type(profile.get(field, False)) is not bool:
            raise ValueError("Invalid provider option.")
        result[field] = profile.get(field, False)
    display = profile.get("display_name", profile["provider"])
    if (
        not isinstance(display, str)
        or not 1 <= len(display.strip()) <= 100
        or any(ord(c) < 32 for c in display)
    ):
        raise ValueError("Enter a provider display name of 1–100 characters.")
    result["display_name"] = display.strip()
    result.setdefault("headers", {})
    result.setdefault("auth", "Bearer")
    auth_header = profile.get("auth_header", "X-API-Key")
    if (
        not isinstance(auth_header, str)
        or not re.fullmatch(r"[A-Za-z0-9-]{1,64}", auth_header)
        or auth_header.casefold()
        in {"host", "content-length", "connection", "transfer-encoding", "proxy-authorization"}
    ):
        raise ValueError("Invalid authentication header name.")
    result["auth_header"] = auth_header
    result.setdefault("key", "")
    result.setdefault("model", "")
    return result


class ProviderStore:
    def __init__(self, directory):
        self.path = Path(directory) / "provider.dpapi"

    def load(self):
        if not self.path.exists():
            return None
        try:
            import win32crypt

            if self.path.is_symlink() or self.path.stat().st_size > 256 * 1024:
                raise ValueError()
            decoded = win32crypt.CryptUnprotectData(self.path.read_bytes(), None, None, None, 1)[1]
            return validate_profile(json.loads(decoded.decode("utf-8")))
        except Exception:
            raise ValueError(
                "Saved provider settings could not be unlocked by this Windows account. Reconnect in Settings; the original file was preserved."
            ) from None

    def save(self, profile):
        profile = validate_profile(profile)
        try:
            import win32crypt

            data = win32crypt.CryptProtectData(
                json.dumps(profile).encode("utf-8"), "NEXIS provider", None, None, None, 1
            )
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(".tmp")
            if self.path.is_symlink() or temporary.is_symlink():
                raise OSError()
            with temporary.open("wb") as output:
                output.write(data)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, self.path)
        except Exception:
            raise ValueError(
                "Windows could not securely save the provider. Previous credentials were preserved."
            ) from None

    def delete(self):
        self.path.unlink(missing_ok=True)


class RejectRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError(
            "Provider redirected the request. Update its address in Settings; credentials were not forwarded."
        )


def discovery_retry_delay(status, headers=None):
    """At most one short retry of a rejected read-only model-list request.

    Respect longer/server-date Retry-After values by leaving Retry to the user.
    Generation, partial responses, connection failures and auth are never replayed.
    """
    if status not in {429, 502, 503, 504}:
        return None
    value = (headers or {}).get("Retry-After")
    if value is None:
        return 1.0
    try:
        delay = float(value)
    except (ValueError, TypeError):
        return None
    return delay if math.isfinite(delay) and 0 <= delay <= 2 else None


def open_with_discovery_retry(open_request, request, cancel, timeout, deadline):
    for attempt in range(2):
        if cancel.is_set():
            raise ProviderError("CANCELLED", "Provider request cancelled.")
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise ProviderError("TIMEOUT", "Provider request deadline exceeded.")
        try:
            return open_request(request, timeout=min(timeout, remaining))
        except urllib.error.HTTPError as exc:
            delay = (discovery_retry_delay(exc.code, exc.headers)
                     if request.get_method() == "GET" and attempt == 0 else None)
            if delay is None or deadline - monotonic() <= delay:
                raise
            exc.close()
            if cancel.wait(delay):
                raise ProviderError("CANCELLED", "Model refresh cancelled.") from None
    raise AssertionError("Unreachable retry state")


def request_json(
    profile, route, cancel, payload=None, timeout=10, opener=None, on_chunk=lambda text: None
):
    config = validate_profile(profile)
    if cancel.is_set():
        raise ValueError("Provider request cancelled.")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        **config["headers"],
    }
    key = config["key"]
    if key and config["auth"] != "None":
        header = (
            config["auth_header"]
            if config["auth"] == "Custom header"
            else "Authorization"
            if config["auth"] == "Bearer"
            else "api-key"
        )
        headers[header] = ("Bearer " if config["auth"] == "Bearer" else "") + key
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(config["endpoint"] + route, data=data, headers=headers)
    try:
        # Local servers do not pass through corporate/public HTTP proxies.
        handlers = [RejectRedirect()]
        if urlsplit(config["endpoint"]).hostname in {"localhost", "127.0.0.1", "::1"}:
            handlers.append(urllib.request.ProxyHandler({}))
        open_request = opener or urllib.request.build_opener(*handlers).open
        deadline = monotonic() + min(150, timeout + 30)
        with open_with_discovery_retry(open_request, req, cancel, timeout, deadline) as response:
            chunks, size = [], 0
            stream = (
                SSECollector(config, on_chunk)
                if payload
                and payload.get("stream")
                and "event-stream" in getattr(response, "headers", {}).get("Content-Type", "")
                else None
            )
            reader = getattr(response, "read1", response.read)
            while chunk := reader(65536):
                if cancel.is_set():
                    raise ValueError("Provider request cancelled.")
                if monotonic() > deadline:
                    raise ProviderError(
                        "TIMEOUT",
                        "Provider response timed out. Retry when the connection is stable.",
                    )
                size += len(chunk)
                if size > 8 * 1024 * 1024:
                    raise ValueError("Provider response exceeded the size limit.")
                chunks.append(chunk)
                if stream:
                    stream.feed(chunk)
            if cancel.is_set():
                raise ValueError("Provider request cancelled.")
            return stream.finish() if stream else json.loads(b"".join(chunks))
    except urllib.error.HTTPError as exc:
        if exc.code == 503:
            try:
                body = exc.read(65536).decode("utf-8", "ignore").casefold()
            except OSError:
                body = ""
            if "not configured" in body or "unavailable" in body:
                raise ProviderError(
                    "SERVER_ERROR",
                    "Provider returned HTTP 503; the gateway reports its upstream is unavailable or not configured. Check the gateway's connected account/model, then Retry. NEXIS has not switched providers.",
                ) from None
        if exc.code in {401, 403}:
            raise ProviderError(
                "AUTHENTICATION",
                "Provider authentication was rejected. Check your saved key or gateway permissions.",
            ) from None
        category = {429: "RATE_LIMIT", 404: "ENDPOINT_OR_MODEL", 408: "TIMEOUT"}.get(
            exc.code, "SERVER_ERROR" if exc.code >= 500 else "INVALID_REQUEST"
        )
        if exc.code in {400, 404, 422}:
            try:
                error = json.loads(exc.read(65536)).get("error", {})
                code = error.get("code", "") if isinstance(error, dict) else ""
                if isinstance(code, str) and code in {
                    "model_not_found",
                    "invalid_model",
                    "unknown_model",
                }:
                    category = "INVALID_MODEL"
            except (ValueError, OSError, AttributeError):
                pass
        raise ProviderError(
            category,
            f"Provider returned HTTP {exc.code}. Check the endpoint, selected model, account access or usage limits, then retry.",
        ) from None
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        reason = exc.reason if isinstance(exc, urllib.error.URLError) else exc
        if isinstance(reason, socket.gaierror):
            category, message = (
                "DNS",
                "Windows could not resolve the configured provider host. Check its address and DNS connection.",
            )
        elif isinstance(reason, ssl.SSLError):
            category, message = (
                "TLS",
                "The configured provider's secure connection could not be verified. Check its certificate and Windows date/time.",
            )
        elif isinstance(reason, (TimeoutError, socket.timeout)):
            category, message = (
                "TIMEOUT",
                "The configured provider did not respond in time. Retry this request.",
            )
        else:
            category, message = (
                "CONNECTION",
                "Could not connect to the configured provider. Check its address/service and retry.",
            )
        raise ProviderError(category, message) from None
    except (json.JSONDecodeError, UnicodeError):
        raise ProviderError(
            "INVALID_RESPONSE", "Provider returned invalid JSON or text encoding."
        ) from None


def list_models(profile, cancel, **kwargs):
    config = validate_profile(profile)
    if config["protocol"] == "gemini":
        from nexis.core.provider_manager import models

        return models(config, cancel, **kwargs)
    kwargs.setdefault("timeout", config["timeout"])
    data = request_json(config, config["models_path"], cancel, **kwargs)
    if not isinstance(data, dict) or not isinstance(data.get("data"), list):
        raise ValueError(
            "This endpoint did not return a compatible model list. Check Advanced Settings."
        )
    models = [
        entry["id"]
        for entry in data["data"]
        if isinstance(entry, dict) and isinstance(entry.get("id"), str) and len(entry["id"]) <= 300
    ]
    return sorted(set(models))[:3000]


def chat(profile, text, cancel, **kwargs):
    from nexis.core.provider_manager import generate

    result = generate(
        profile,
        [
            {
                "role": "system",
                "content": "You are NEXIS. Answer this text request. No operating-system tool execution is available in this connection test.",
            },
            {"role": "user", "content": text[:1000]},
        ],
        cancel,
        **kwargs,
    )
    if not result["text"].strip():
        raise ProviderError("EMPTY_RESPONSE", "Provider returned no usable assistant message.")
    return result["text"]


class SSECollector:
    """Bounded OpenAI-compatible event stream; tool calls are never executed here."""

    def __init__(self, profile, on_chunk):
        self.profile, self.on_chunk = profile, on_chunk
        self.buffer = b""
        self.text = ""
        self.calls = {}
        self.done = False

    def feed(self, chunk):
        self.buffer = (self.buffer + chunk).replace(b"\r\n", b"\n")
        if len(self.buffer) > 1024 * 1024:
            raise ProviderError("RESPONSE_LIMIT", "Provider stream event exceeded its size limit.")
        while b"\n\n" in self.buffer:
            event, self.buffer = self.buffer.split(b"\n\n", 1)
            self.event(event)

    def event(self, event):
        data = b"\n".join(
            line[5:].strip() for line in event.splitlines() if line.startswith(b"data:")
        )
        if not data:
            return
        if data == b"[DONE]":
            self.done = True
            return
        try:
            payload = json.loads(data)
            if "error" in payload:
                raise ProviderError(
                    "SERVER_ERROR",
                    "Provider reported a streaming error. Retry the selected provider.",
                )
            choices = payload.get("choices", [])
            if not choices:
                return
            delta = choices[0].get("delta", {})
            content = delta.get("content") or ""
            if not isinstance(content, str):
                raise ValueError()
            self.text += content
            if len(self.text) > 24000:
                raise ProviderError("RESPONSE_LIMIT", "Provider text exceeded its limit.")
            from nexis.core.provider_manager import redact

            hold = max(
                [
                    len(self.profile.get("key", "")),
                    *(len(v) for v in self.profile.get("headers", {}).values()),
                    0,
                ]
            )
            if len(self.text) > hold:
                self.on_chunk(redact(self.text[:-hold] if hold else self.text, self.profile))
            for item in delta.get("tool_calls", []):
                index = item.get("index", 0)
                if type(index) is not int or not 0 <= index < 12:
                    raise ValueError()
                current = self.calls.setdefault(
                    index, {"id": "", "type": "function", "function": {"name": "", "arguments": ""}}
                )
                current["id"] += item.get("id", "")
                for field in ("name", "arguments"):
                    value = item.get("function", {}).get(field, "")
                    if not isinstance(value, str) or len(value) > 65536:
                        raise ValueError()
                    current["function"][field] += value
                    if len(current["function"][field]) > 65536:
                        raise ValueError()
        except ProviderError:
            raise
        except (ValueError, KeyError, TypeError, AttributeError):
            raise ProviderError(
                "INVALID_RESPONSE", "Provider sent a malformed streaming event."
            ) from None

    def finish(self):
        if self.buffer.strip():
            self.event(self.buffer)
        if not self.done:
            raise ProviderError(
                "INTERRUPTED_STREAM",
                "Provider stream ended before its completion marker. Partial output was retained; retry explicitly.",
            )
        from nexis.core.provider_manager import redact

        self.text = redact(self.text, self.profile)
        self.on_chunk(self.text)
        return {
            "choices": [
                {
                    "message": {
                        "content": self.text,
                        "tool_calls": [self.calls[i] for i in sorted(self.calls)],
                    }
                }
            ]
        }
