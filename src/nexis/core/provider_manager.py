"""Explicit multi-provider selection and native Gemini / compatible gateway adapters."""

import json
import os
from pathlib import Path
from time import monotonic
from uuid import uuid4

from nexis.core.providers import ProviderStore, ProviderError, validate_profile, request_json


class ProviderManager:
    def __init__(self, directory):
        self.path = Path(directory) / "providers.dpapi"
        self.legacy = ProviderStore(directory)

    def read(self):
        if not self.path.exists():
            legacy = self.legacy.load()
            return {
                "version": 1,
                "default_id": "legacy" if legacy else "",
                "profiles": [{"id": "legacy", **legacy}] if legacy else [],
            }
        try:
            import win32crypt

            if self.path.is_symlink() or self.path.stat().st_size > 1024 * 1024:
                raise ValueError()
            data = json.loads(
                win32crypt.CryptUnprotectData(self.path.read_bytes(), None, None, None, 1)[
                    1
                ].decode("utf-8")
            )
            if (
                data.get("version") != 1
                or not isinstance(data.get("profiles"), list)
                or len(data["profiles"]) > 30
            ):
                raise ValueError()
            ids = set()
            profiles = []
            for profile in data["profiles"]:
                identifier = profile.get("id")
                if (
                    not isinstance(identifier, str)
                    or not 1 <= len(identifier) <= 64
                    or not identifier.isalnum()
                    or identifier in ids
                ):
                    raise ValueError()
                ids.add(identifier)
                profiles.append({**validate_profile(profile), "id": identifier})
            if data.get("default_id") and data["default_id"] not in ids:
                raise ValueError()
            return {"version": 1, "default_id": data.get("default_id", ""), "profiles": profiles}
        except Exception:
            raise ValueError(
                "Provider Manager could not unlock its saved configurations. The original encrypted file was preserved; use the same Windows account or reconnect in AI Providers."
            ) from None

    def write(self, data):
        import win32crypt

        temporary = self.path.with_suffix(".tmp")
        if self.path.is_symlink() or temporary.is_symlink():
            raise ValueError("Unsafe provider storage path.")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        encoded = win32crypt.CryptProtectData(
            json.dumps(data).encode("utf-8"), "NEXIS providers", None, None, None, 1
        )
        try:
            with temporary.open("wb") as output:
                output.write(encoded)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, self.path)
        except OSError:
            raise ValueError(
                "Windows could not securely save the provider configurations. Previous settings were preserved."
            ) from None

    def active(self):
        data = self.read()
        return next((p for p in data["profiles"] if p["id"] == data["default_id"]), None)

    def save(self, profile, identifier=None):
        profile = validate_profile(profile)
        data = self.read()
        identifier = identifier or uuid4().hex
        if not identifier.isalnum() or len(identifier) > 64:
            raise ValueError("Invalid provider identifier.")
        data["profiles"] = [p for p in data["profiles"] if p["id"] != identifier] + [
            {**profile, "id": identifier}
        ]
        if len(data["profiles"]) > 30:
            raise ValueError("At most 30 provider configurations are supported.")
        self.write(data)
        return identifier

    def select(self, identifier):
        data = self.read()
        if identifier not in {p["id"] for p in data["profiles"]}:
            raise ValueError("Select a saved provider.")
        data["default_id"] = identifier
        self.write(data)

    def remove(self, identifier):
        data = self.read()
        data["profiles"] = [p for p in data["profiles"] if p["id"] != identifier]
        if data["default_id"] == identifier:
            data["default_id"] = ""  # Explicit selection required; never silently choose another.
        self.write(data)
        if identifier == "legacy":
            self.legacy.delete()


def redact(text, profile):
    for secret in (profile.get("key", ""), *profile.get("headers", {}).values()):
        if secret and len(secret) >= 4:
            text = text.replace(secret, "[redacted]")
    return text


def redact_values(value, profile):
    if isinstance(value, str):
        return redact(value, profile)
    if isinstance(value, list):
        return [redact_values(item, profile) for item in value]
    if isinstance(value, dict):
        return {key: redact_values(item, profile) for key, item in value.items()}
    return value


def gemini_client(profile):
    from google import genai
    from google.genai import types

    if not profile.get("key"):
        raise ProviderError("AUTHENTICATION", "Enter a Gemini API key in AI Providers.")
    # Explicit key/base URL; no ambient credentials, alternate provider or cloud project.
    return genai.Client(
        api_key=profile["key"],
        vertexai=False,
        http_options=types.HttpOptions(
            base_url="https://generativelanguage.googleapis.com",
            timeout=profile["timeout"] * 1000,
            retry_options=types.HttpRetryOptions(attempts=1),
            client_args={"follow_redirects": False},
        ),
    )


def sdk_error(exc):
    code = getattr(exc, "code", None)
    if code in {401, 403}:
        return ProviderError(
            "AUTHENTICATION",
            "Gemini rejected this key or API permission. Check the selected account and key.",
        )
    if code == 429:
        return ProviderError(
            "RATE_LIMIT",
            "Gemini quota/rate limit was reached. Check this account's tier and retry later; model availability does not imply free usage.",
        )
    if code == 404:
        return ProviderError(
            "INVALID_MODEL",
            "Gemini could not find the requested model. Refresh available models for your key.",
        )
    if code and isinstance(code, int) and code >= 500:
        return ProviderError(
            "SERVER_ERROR", "Gemini returned a server error. Retry the selected provider."
        )
    if code:
        return ProviderError(
            "INVALID_REQUEST",
            "Gemini rejected this request. Check the selected model and supported options.",
        )
    import httpx

    if isinstance(exc, httpx.TimeoutException):
        return ProviderError("TIMEOUT", "Gemini did not respond within the configured timeout.")
    if isinstance(exc, httpx.ConnectError):
        reason = exc.__cause__
        import ssl
        import socket

        if isinstance(reason, ssl.SSLError):
            return ProviderError("TLS", "Gemini secure connection verification failed.")
        if isinstance(reason, socket.gaierror):
            return ProviderError("DNS", "Windows could not resolve the Gemini API address.")
    return ProviderError(
        "CONNECTION",
        "The Gemini API request could not complete. Check connectivity and retry; capture and transcripts remain available.",
    )


def models(profile, cancel, **kwargs):
    profile = validate_profile(profile)
    if cancel.is_set():
        raise ProviderError("CANCELLED", "Model refresh cancelled.")
    if profile["protocol"] == "openai":
        from nexis.core.providers import list_models

        return list_models(profile, cancel, **kwargs)
    try:
        with gemini_client(profile) as client:
            found = []
            for model in client.models.list(config={"page_size": 100}):
                if cancel.is_set():
                    raise ProviderError("CANCELLED", "Model refresh cancelled.")
                actions = getattr(model, "supported_actions", None) or []
                if getattr(model, "name", None) and (not actions or "generateContent" in actions):
                    found.append(model.name)
                if len(found) >= 1000:
                    break
            return sorted(set(found))
    except ProviderError:
        raise
    except Exception as exc:
        raise sdk_error(exc) from None


def generate(profile, messages, cancel, *, tools=None, on_chunk=lambda text: None, opener=None):
    profile = validate_profile(profile)
    if cancel.is_set():
        raise ProviderError("CANCELLED", "Request cancelled.")
    if not profile["model"]:
        raise ProviderError("INVALID_MODEL", "Select or refresh a model in AI Providers first.")
    if profile["protocol"] == "gemini":
        return gemini_generate(profile, messages, cancel, tools, on_chunk)
    payload = {
        "model": profile["model"],
        "messages": messages,
        "max_tokens": 2048,
        "stream": profile["stream"],
    }
    if tools and profile["native_tools"]:
        payload["tools"] = [{"type": "function", "function": spec} for spec in tools]
        payload["tool_choice"] = "auto"
    data = request_json(
        profile,
        profile["api_path"],
        cancel,
        payload,
        timeout=profile["timeout"],
        opener=opener,
        on_chunk=on_chunk,
    )
    try:
        message = data["choices"][0]["message"]
        text = message.get("content") or ""
        if not isinstance(text, str):
            raise TypeError()
        calls = []
        for call in message.get("tool_calls", []):
            calls.append(
                {
                    "tool": call["function"]["name"],
                    "arguments": json.loads(call["function"]["arguments"]),
                }
            )
        if not text.strip() and not calls:
            raise ValueError()
        return {
            "text": redact(text[:24000], profile),
            "calls": redact_values(calls, profile),
        }
    except (KeyError, IndexError, TypeError, ValueError):
        raise ProviderError(
            "EMPTY_RESPONSE",
            "Provider returned no compatible text/tool response. Verify its protocol, model and endpoint.",
        ) from None


def gemini_generate(profile, messages, cancel, tools, on_chunk):
    from google.genai import types

    system = "\n".join(m["content"] for m in messages if m["role"] == "system")
    contents = [
        types.Content(
            role="model" if m["role"] == "assistant" else "user",
            parts=[types.Part.from_text(text=m["content"])],
        )
        for m in messages
        if m["role"] != "system"
    ]
    config = types.GenerateContentConfig(
        system_instruction=system,
        max_output_tokens=2048,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    if tools:
        config.tools = [
            types.Tool(
                function_declarations=[
                    types.FunctionDeclaration(
                        name=t["name"],
                        description=t["description"],
                        parameters_json_schema=t["parameters"],
                    )
                    for t in tools
                ]
            )
        ]
    try:
        with gemini_client(profile) as client:
            response = (
                client.models.generate_content_stream(
                    model=profile["model"], contents=contents, config=config
                )
                if profile["stream"]
                else [
                    client.models.generate_content(
                        model=profile["model"], contents=contents, config=config
                    )
                ]
            )
            pieces, calls = [], []
            deadline = monotonic() + profile["timeout"] + 30
            for part in response:
                if cancel.is_set():
                    raise ProviderError("CANCELLED", "Request cancelled.")
                if monotonic() > deadline:
                    raise ProviderError("TIMEOUT", "Gemini streaming deadline exceeded.")
                for candidate in getattr(part, "candidates", None) or []:
                    for item in getattr(getattr(candidate, "content", None), "parts", None) or []:
                        if getattr(item, "text", None):
                            pieces.append(item.text)
                            combined = "".join(pieces)
                            hold = max(
                                [
                                    len(profile.get("key", "")),
                                    *(len(v) for v in profile.get("headers", {}).values()),
                                    0,
                                ]
                            )
                            if len(combined) > hold:
                                on_chunk(redact(combined[:-hold] if hold else combined, profile))
                        call = getattr(item, "function_call", None)
                        if call:
                            calls.append({"tool": call.name, "arguments": dict(call.args or {})})
                if sum(map(len, pieces)) > 24000 or len(calls) > 12:
                    raise ProviderError("RESPONSE_LIMIT", "Gemini response exceeded NEXIS limits.")
            text = redact("".join(pieces), profile)
            if not text.strip() and not calls:
                raise ProviderError(
                    "EMPTY_RESPONSE",
                    "Gemini returned no usable text or function call. Check model safety/availability and retry.",
                )
            on_chunk(text)
            return {"text": text, "calls": redact_values(calls, profile)}
    except ProviderError:
        raise
    except Exception as exc:
        raise sdk_error(exc) from None
