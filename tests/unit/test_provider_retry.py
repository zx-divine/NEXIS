"""Only explicit transient rejection of a read-only GET can be retried."""

import io
import json
from threading import Event
from urllib.error import HTTPError, URLError

import pytest

from nexis.core.providers import ProviderError, discovery_retry_delay, request_json

PROFILE = {"provider": "OmniRoute", "endpoint": "http://127.0.0.1:20128/v1", "model": "fixture"}


class Response(io.BytesIO):
    headers = {"Content-Type": "application/json"}


def rejection(code=503, delay="0"):
    return HTTPError("http://localhost", code, "fixture", {"Retry-After": delay}, io.BytesIO(b"private error body"))


def test_rejected_get_retries_once_and_closes_error_body():
    calls = []
    error = rejection()

    def opener(request, timeout):
        calls.append(request.get_method())
        if len(calls) == 1:
            raise error
        return Response(json.dumps({"data": []}).encode())

    assert request_json(PROFILE, "/models", Event(), opener=opener) == {"data": []}
    assert calls == ["GET", "GET"] and error.fp.closed


@pytest.mark.parametrize("code", [401, 403, 404, 400])
def test_auth_and_configuration_failures_are_not_retried(code):
    calls = []

    def opener(request, timeout):
        calls.append(1)
        raise rejection(code)

    with pytest.raises(ProviderError):
        request_json(PROFILE, "/models", Event(), opener=opener)
    assert len(calls) == 1


def test_generation_is_never_replayed_even_if_rejected():
    calls = []

    def opener(request, timeout):
        calls.append(request.get_method())
        raise rejection(429)

    with pytest.raises(ProviderError, match="429"):
        request_json(PROFILE, "/chat/completions", Event(), {"stream": True}, opener=opener)
    assert calls == ["POST"]


def test_retry_limit_and_server_delay_are_respected():
    for delay, count in [("0", 2), ("120", 1), ("invalid", 1), ("nan", 1)]:
        calls = []

        def opener(request, timeout):
            calls.append(1)
            raise rejection(503, delay)

        with pytest.raises(ProviderError, match="503") as error:
            request_json(PROFILE, "/models", Event(), opener=opener)
        assert len(calls) == count and "private error body" not in str(error.value)
    assert discovery_retry_delay(429) == 1


def test_cancel_interrupts_wait_before_second_request():
    cancel = Event()
    calls = []

    def opener(request, timeout):
        calls.append(1)
        cancel.set()
        raise rejection(503, "1")

    with pytest.raises(ProviderError, match="CANCELLED"):
        request_json(PROFILE, "/models", cancel, opener=opener)
    assert len(calls) == 1


@pytest.mark.parametrize("error", [URLError("fixture connection error"), TimeoutError()])
def test_ambiguous_network_errors_are_not_retried(error):
    calls = []

    def opener(request, timeout):
        calls.append(1)
        raise error

    with pytest.raises(ProviderError):
        request_json(PROFILE, "/models", Event(), opener=opener)
    assert len(calls) == 1
