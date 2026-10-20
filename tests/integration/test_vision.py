"""Vision over injected transports only. No desktop captures or live API calls."""

import base64
import io
import json
from threading import Event
from urllib.error import HTTPError

import pytest

from nexis.core.providers import ProviderError
from nexis.core.vision import analyze_image

PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jf1sAAAAASUVORK5CYII=")
PROFILE = {"provider": "OpenAI-compatible", "endpoint": "https://gateway.example/v1",
           "model": "owner-vision-fixture", "key": "fixture-private-key"}


class Response(io.BytesIO):
    headers = {}


def test_vision_has_explicit_consent_and_no_tools_or_conversation_context():
    seen = []

    def opener(request, timeout):
        seen.append(json.loads(request.data))
        return Response(json.dumps({"choices": [{"message": {"content": "Explanation with fixture-private-key redacted"}}]}).encode())

    with pytest.raises(ProviderError, match="CONSENT_REQUIRED"):
        analyze_image(PROFILE, PNG, "Explain", Event(), opener=opener)
    assert not seen
    reply = analyze_image(PROFILE, PNG, "Explain this image", Event(), consent=True, opener=opener)
    assert "fixture-private-key" not in reply
    body = seen[0]
    assert body["model"] == PROFILE["model"] and body["stream"] is False
    assert "tools" not in body and len(body["messages"]) == 2
    parts = body["messages"][1]["content"]
    assert parts[1]["image_url"]["url"].startswith("data:image/png;base64,")
    assert "untrusted" in body["messages"][0]["content"]


def test_cancellation_blocks_queued_transmission_and_http_errors_never_replay():
    seen = []

    def fail(request, timeout):
        seen.append(1)
        raise HTTPError(request.full_url, 503, "private", {}, io.BytesIO(b"{}"))

    cancel = Event()
    cancel.set()
    with pytest.raises(ProviderError, match="CANCELLED"):
        analyze_image(PROFILE, PNG, "Explain", cancel, consent=True, opener=fail)
    assert not seen
    with pytest.raises(ProviderError, match="503"):
        analyze_image(PROFILE, PNG, "Explain", Event(), consent=True, opener=fail)
    assert len(seen) == 1


@pytest.mark.parametrize("message", [{"content": "", "tool_calls": [{"anything": "untrusted"}]},
                                   {"content": ""}, {"content": ["invalid"]}])
def test_unsupported_vision_outputs_never_become_actions(message):
    with pytest.raises(ProviderError):
        analyze_image(PROFILE, PNG, "Explain", Event(), consent=True,
            opener=lambda *args, **kwargs: Response(json.dumps({"choices": [{"message": message}]}).encode()))


@pytest.mark.parametrize("image", [b"invalid", PNG * 100000], ids=["invalid", "oversized"])
def test_invalid_and_oversized_images_are_rejected_before_network(image):
    with pytest.raises(ValueError, match="PNG"):
        analyze_image(PROFILE, image, "Explain", Event(), consent=True)


def test_native_gemini_vision_uses_installed_official_sdk_with_mock_transport(monkeypatch):
    import httpx
    from google import genai
    from google.genai import types
    seen = []

    def handler(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, json={"candidates": [{"content": {"role": "model", "parts": [{"text": "Fixture image explanation"}]}}]}, request=request)

    def factory(profile):
        return genai.Client(api_key=profile["key"], vertexai=False,
            http_options=types.HttpOptions(timeout=5000,
                retry_options=types.HttpRetryOptions(attempts=1),
                client_args={"transport": httpx.MockTransport(handler)}))

    monkeypatch.setattr("nexis.core.vision.gemini_client", factory)
    profile = {**PROFILE, "provider": "Google Gemini", "endpoint": "https://generativelanguage.googleapis.com"}
    assert analyze_image(profile, PNG, "Explain", Event(), consent=True) == "Fixture image explanation"
    assert len(seen) == 1 and "tools" not in seen[0]
    parts = seen[0]["contents"][0]["parts"]
    inline = parts[1]["inlineData"]
    assert inline.get("mimeType", inline.get("mime_type")) == "image/png"
    assert base64.urlsafe_b64decode(parts[1]["inlineData"]["data"]) == PNG
