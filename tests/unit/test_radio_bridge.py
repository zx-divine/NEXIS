"""Exercise the real bridge's response/cancellation path without radio changes."""
import base64
import os
from threading import Event
import pytest
from nexis.platform import radios

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows radio bridge ABI and helper paths")


class NativeCall:
    def __init__(self, effect=lambda *args: 1):
        self.effect = effect

    def __call__(self, *args):
        return self.effect(*args)


def bridge(monkeypatch, output, cancel, cancel_during_wait=False):
    events, launches = [], []
    class Kernel:
        CreateEventW = NativeCall()
        SetEvent = NativeCall(lambda handle: events.append("cancel-signalled") or 1)
        CloseHandle = NativeCall()
    class Helper:
        killed = False
        def communicate(self, timeout):
            if cancel_during_wait and not self.killed:
                cancel.set()
                raise radios.subprocess.TimeoutExpired("fixed bridge", timeout)
            return output, b""
        def kill(self):
            self.killed = True
        def poll(self):
            return 0
    helper = Helper()
    def launch(args, **kwargs):
        launches.append((args, kwargs))
        return helper
    monkeypatch.setattr(radios.ctypes, "WinDLL", lambda *args, **kwargs: Kernel())
    monkeypatch.setattr(radios, "remote_session", lambda: False)
    monkeypatch.setattr(radios.subprocess, "Popen", launch)
    monkeypatch.setattr(radios, "_access_allowed", False)
    return helper, events, launches


@pytest.mark.parametrize("output,message", [
    (b'{"verified":false,"message":"Unsupported or unavailable radio hardware"}', "unavailable"),
    (b'{"verified":false,"message":"Windows radio access: DeniedBySystem"}', "DeniedBySystem"),
    (b'{"verified":false,"states":["disabled"]}', "not verified"),
    (b'not JSON', "readable result"),
])
def test_bridge_never_equates_submission_to_success(monkeypatch, output, message):
    cancel = Event()
    helper, events, launches = bridge(monkeypatch, output, cancel)
    with pytest.raises(ValueError, match=message):
        radios.set_state("wifi", "on", cancel)
    args, kwargs = launches[0]
    assert kwargs["shell"] is False
    assert kwargs["creationflags"] == radios.subprocess.CREATE_NO_WINDOW
    assert args[-2] == "-EncodedCommand"
    assert "__STATE__" not in base64.b64decode(args[-1]).decode("utf-16le")
    assert events


def test_cancel_during_bridge_wait_signals_and_stops_helper(monkeypatch):
    cancel = Event()
    helper, events, launches = bridge(monkeypatch, b"", cancel, cancel_during_wait=True)
    with pytest.raises(ValueError, match="cancelled or timed out"):
        radios.set_state("bluetooth", "on", cancel)
    assert helper.killed and events and len(launches) == 1
