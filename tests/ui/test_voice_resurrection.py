"""Engine lifecycle checks; these never stand in for hardware verification."""

from array import array
import json
import sys
from types import SimpleNamespace

import pytest

from nexis.core.voice import VoiceWorker
from nexis.platform.speech import SpeechService, default_input
from nexis.ui.voice_diagnostics import relevant_transcript, completed_cycles


def backend(monkeypatch, worker, *, cancel=False, error=False, rates=None):
    events = []

    class Recognizer:
        def __init__(self, model, rate):
            events.append(("recognizer", rate))

        def AcceptWaveform(self, data):
            (worker.cancel.set if cancel else worker.stop_recording)()
            return True

        def Result(self):
            return json.dumps({"text": "hello nexis this is a microphone test"})

        def FinalResult(self):
            return json.dumps({"text": ""})

    class Stream:
        def __init__(self, **kwargs):
            self.callback = kwargs["callback"]
            events.append(("stream_rate", kwargs["samplerate"]))

        def __enter__(self):
            events.append("open")
            if error:
                raise OSError("private driver details")
            self.callback(array("h", [1000] * 1600).tobytes(), 1600, None, None)
            return self

        def __exit__(self, *args):
            events.append("closed")

    def check(**kwargs):
        if rates is not None and kwargs["samplerate"] not in rates:
            raise ValueError("unsupported")

    monkeypatch.setitem(
        sys.modules,
        "sounddevice",
        SimpleNamespace(
            query_devices=lambda **kwargs: {"default_samplerate": 44100, "name": "test microphone"},
            check_input_settings=check,
            RawInputStream=Stream,
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        "vosk",
        SimpleNamespace(
            Model=lambda path: object(),
            KaldiRecognizer=Recognizer,
            SetLogLevel=lambda level: None,
        ),
    )
    return events


def test_cancel_after_capture_discards_transcript_and_releases_device(qtbot, monkeypatch, tmp_path):
    worker = VoiceWorker(str(tmp_path))
    events = backend(monkeypatch, worker, cancel=True)
    transcripts = []
    worker.transcript.connect(transcripts.append)
    with qtbot.waitSignal(worker.finished):
        worker.start()
    assert "open" in events and "closed" in events
    assert not transcripts


def test_rate_fallback_matches_recognizer_and_stream(qtbot, monkeypatch, tmp_path):
    worker = VoiceWorker(str(tmp_path))
    events = backend(monkeypatch, worker, rates={16000})
    with qtbot.waitSignal(worker.transcript):
        worker.start()
    assert worker.wait(2000)
    assert ("recognizer", 16000) in events and ("stream_rate", 16000) in events


def test_audio_open_failure_is_reported_without_driver_internals(qtbot, monkeypatch, tmp_path):
    worker = VoiceWorker(str(tmp_path))
    backend(monkeypatch, worker, error=True)
    with qtbot.waitSignal(worker.failed) as message:
        worker.start()
    assert worker.wait(2000)
    assert "microphone" in message.args[0] and "private driver details" not in message.args[0]


def test_corrupt_model_fails_before_microphone_open(qtbot, monkeypatch, tmp_path):
    worker = VoiceWorker(str(tmp_path))
    calls = []

    def corrupt(path):
        raise ValueError("corrupt")

    monkeypatch.setitem(
        sys.modules,
        "vosk",
        SimpleNamespace(Model=corrupt, SetLogLevel=lambda level: None, KaldiRecognizer=None),
    )
    monkeypatch.setitem(
        sys.modules,
        "sounddevice",
        SimpleNamespace(query_devices=lambda **kw: calls.append("device")),
    )
    with qtbot.waitSignal(worker.failed):
        worker.start()
    assert worker.wait(2000) and not calls


def test_selected_device_must_be_input():
    sd = SimpleNamespace(query_devices=lambda *args: {"max_input_channels": 0})
    with pytest.raises(ValueError, match="not a microphone"):
        default_input(sd, 3)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("", False),
        ("open github", False),
        ("hello nexus this is a microphone test", True),
        ("hello nexis this is a microphone test", True),
    ],
)
def test_standalone_rejects_empty_or_unrelated_transcription(text, expected):
    assert relevant_transcript(text) is expected


def test_nonpassed_cycles_do_not_count_as_hardware_success(tmp_path):
    (tmp_path / "test-results").mkdir()
    (tmp_path / "test-results/standalone-cycle-1-incomplete.json").write_text(
        json.dumps({"cycle": 1, "result": "NOT VERIFIED"})
    )
    assert completed_cycles(tmp_path) == {}


def test_sapi_completion_and_com_cleanup(qtbot, monkeypatch):
    import pythoncom
    import win32com.client

    calls = []

    class Token:
        Id = "voice"

        def GetDescription(self):
            return "Test voice"

    class Tokens:
        Count = 1

        def Item(self, index):
            return Token()

    class Speaker:
        def GetVoices(self):
            return Tokens()

        def Speak(self, text, flags):
            calls.append((text, flags))

        def WaitUntilDone(self, timeout):
            calls.append(("wait", timeout))
            return True

    monkeypatch.setattr(pythoncom, "CoInitialize", lambda: calls.append("com_init"))
    monkeypatch.setattr(pythoncom, "CoUninitialize", lambda: calls.append("com_release"))
    monkeypatch.setattr(pythoncom, "PumpWaitingMessages", lambda: None)
    monkeypatch.setattr(win32com.client, "Dispatch", lambda name: Speaker())
    worker = SpeechService()
    with qtbot.waitSignal(worker.voices):
        worker.start()
    with qtbot.waitSignal(worker.playback_finished) as result:
        identifier = worker.say("literal <words>")
    assert result.args == [identifier, "PASS"]
    assert ("literal <words>", 19) in calls and ("wait", 50) in calls
    worker.cancel.set()
    qtbot.waitUntil(lambda: not worker.isRunning())
    assert calls[0] == "com_init" and calls[-1] == "com_release"


def test_stop_before_capture_does_not_open_microphone(qtbot, monkeypatch, tmp_path):
    worker = VoiceWorker(str(tmp_path))
    events = backend(monkeypatch, worker)
    worker.stop_recording()
    with qtbot.waitSignal(worker.transcript) as result:
        worker.start()
    assert worker.wait(2000)
    assert result.args == [""] and "open" not in events


def test_sapi_cancel_during_output_rebind_does_not_speak_stale_reply(qtbot, monkeypatch):
    import win32com.client

    spoken = []
    worker = SpeechService()
    dispatches = []

    class Token:
        Id = "default"

        def GetDescription(self):
            return "Fixture"

    class Tokens:
        Count = 1

        def Item(self, index):
            return Token()

    class Speaker:
        def GetVoices(self):
            return Tokens()

        def Speak(self, text, flags):
            spoken.append(text)

        def WaitUntilDone(self, timeout):
            return True

    def dispatch(name):
        dispatches.append(name)
        if len(dispatches) == 2:
            worker.stop_speaking()
        return Speaker()

    monkeypatch.setattr(win32com.client, "Dispatch", dispatch)
    with qtbot.waitSignal(worker.voices):
        worker.start()
    with qtbot.waitSignal(worker.playback_finished) as result:
        identifier = worker.say("stale reply must not play")
    assert result.args == [identifier, "CANCELLED"]
    assert "stale reply must not play" not in spoken
    worker.cancel.set()
    qtbot.waitUntil(lambda: not worker.isRunning())


def test_speech_queue_overload_is_explicit(qtbot):
    worker = SpeechService()
    for _ in range(8):
        assert worker.say("queued fixture") is not None
    assert worker.say("not queued") is None
    worker.stop_speaking()
    assert worker.queue.empty()


def test_narrowband_device_negotiates_wideband_before_open(qtbot, monkeypatch, tmp_path):
    worker = VoiceWorker(str(tmp_path))
    events = backend(monkeypatch, worker, rates={8000, 16000})
    sys.modules["sounddevice"].query_devices = lambda **kwargs: {
        "default_samplerate": 8000, "name": "Narrowband headset"
    }
    with qtbot.waitSignal(worker.transcript):
        worker.start()
    assert worker.wait(2000)
    assert ("recognizer", 16000) in events and ("stream_rate", 16000) in events
    assert ("stream_rate", 8000) not in events and "closed" in events


def test_incompatible_narrowband_only_device_fails_before_capture(qtbot, monkeypatch, tmp_path):
    worker = VoiceWorker(str(tmp_path))
    events = backend(monkeypatch, worker, rates={8000})
    sys.modules["sounddevice"].query_devices = lambda **kwargs: {
        "default_samplerate": 8000, "name": "Narrowband-only input"
    }
    with qtbot.waitSignal(worker.failed) as failure:
        worker.start()
    assert worker.wait(2000)
    assert "sample rate" in failure.args[0] and "open" not in events
