"""Injected backend tests: no actual audio hardware or ASR model is used."""

import json
import sys
from types import SimpleNamespace
from array import array

from nexis.core.voice import VoiceWorker


def test_capture_lifecycle_levels_and_transcript(qtbot, monkeypatch, tmp_path):
    worker = VoiceWorker(str(tmp_path))
    calls, statuses, levels = [], [], []

    class Recognizer:
        def __init__(self, model, rate):
            assert rate == 16000

        def AcceptWaveform(self, data):
            worker.stop_recording()
            return True

        def Result(self):
            return json.dumps({"text": "open notepad"})

        def FinalResult(self):
            return json.dumps({"text": ""})

    class Stream:
        def __init__(self, **kwargs):
            assert kwargs["dtype"] == "int16" and kwargs["channels"] == 1
            self.callback = kwargs["callback"]

        def __enter__(self):
            calls.append("open")
            self.callback(array("h", [16384] * 1600).tobytes(), 1600, None, None)
            return self

        def __exit__(self, *args):
            calls.append("close")

    monkeypatch.setitem(
        sys.modules,
        "sounddevice",
        SimpleNamespace(
            query_devices=lambda **kwargs: {"default_samplerate": 16000}, RawInputStream=Stream
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        "vosk",
        SimpleNamespace(
            Model=lambda path: object(), KaldiRecognizer=Recognizer, SetLogLevel=lambda level: None
        ),
    )
    worker.status.connect(statuses.append)
    worker.level.connect(levels.append)
    assert calls == []  # Constructing a worker never opens a microphone.
    with qtbot.waitSignal(worker.transcript, timeout=2000) as signal:
        worker.start()
    assert worker.wait(2000)
    qtbot.wait(20)
    assert signal.args == ["open notepad"]
    assert calls == ["open", "close"]
    assert any(text.startswith("LISTENING") for text in statuses)
    assert 0.5 in levels


def test_cancel_during_model_loading_never_opens_microphone(qtbot, monkeypatch, tmp_path):
    worker = VoiceWorker(str(tmp_path))
    calls = []

    def load(path):
        worker.cancel.set()
        return object()

    monkeypatch.setitem(
        sys.modules,
        "vosk",
        SimpleNamespace(
            Model=load, SetLogLevel=lambda level: None, KaldiRecognizer=lambda *args: None
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        "sounddevice",
        SimpleNamespace(
            query_devices=lambda **kwargs: calls.append("device"),
            RawInputStream=lambda **kwargs: calls.append("microphone"),
        ),
    )
    with qtbot.waitSignal(worker.finished, timeout=2000):
        worker.start()
    assert calls == []
