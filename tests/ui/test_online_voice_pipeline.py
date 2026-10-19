"""UI pipeline tests with injected capture/provider/TTS; not hardware evidence."""

from threading import Event
from uuid import uuid4

import pytest
from PySide6.QtCore import QObject, Signal, QTimer, QThread
from nexis.core.voice_session import VoiceTurn, VoiceState
from nexis.core.provider_manager import ProviderManager
from nexis.ui.main_window import MainWindow


class FakeSpeech(QObject):
    playback_finished = Signal(str, str)
    finished = Signal()

    def __init__(self):
        super().__init__()
        self.busy = Event()
        self.spoken = []

    def isRunning(self):
        return True

    def stop_speaking(self):
        self.busy.clear()

    def say(self, text):
        self.spoken.append(text)
        identifier = uuid4().hex
        QTimer.singleShot(30, lambda: self.playback_finished.emit(identifier, "PASS"))
        return identifier


class FakeCapture(QThread):
    status = Signal(str)
    level = Signal(float)
    partial = Signal(str)
    measured = Signal(object)
    transcript = Signal(str)
    failed = Signal(str)

    def __init__(self, *args):
        super().__init__()
        self.cancel = Event()

    def stop_recording(self):
        pass

    def run(self):
        self.status.emit("LISTENING — microphone active")
        if self.cancel.wait(0.05):
            return
        self.level.emit(0.1)
        self.status.emit("TRANSCRIBING — microphone off")
        self.measured.emit(
            {
                "device": "Injected fixture",
                "sample_rate": 16000,
                "audio_seconds": 1,
                "peak_rms": 0.1,
            }
        )
        self.transcript.emit("Tell me something helpful")


@pytest.fixture
def voice_window(qtbot, db, tmp_path, platform, monkeypatch):
    monkeypatch.setattr(
        "nexis.ui.conversation.setup_status", lambda path: (True, "test model ready")
    )
    monkeypatch.setattr("nexis.ui.conversation.VoiceWorker", FakeCapture)
    manager = ProviderManager(tmp_path)
    selected = manager.save(
        {
            "provider": "Compatible gateway",
            "endpoint": "http://127.0.0.1:20128/v1",
            "model": "fixture",
            "key": "fixture-key",
        }
    )
    manager.select(selected)
    monkeypatch.setattr(
        "nexis.core.operator.generate",
        lambda *a, **k: {"text": "A genuine fixture provider response", "calls": []},
    )
    window = MainWindow(db, tmp_path, platform)
    qtbot.addWidget(window)
    speaker = FakeSpeech()
    window.settings_page.voice_setup.speech = speaker
    # FakeSpeech is not a QThread and must not be included in shutdown jobs.
    window.background_jobs = lambda: [window.voice.worker, *window.ai_jobs]
    window.voice.attach_speech(speaker)
    window.navigate("Voice Chat")
    window.show()
    yield window, speaker
    window.voice.stop()
    qtbot.waitUntil(
        lambda: not any(j and j.isRunning() for j in window.background_jobs()), timeout=3000
    )
    window.close()


def test_complete_mock_pipeline_routes_automatically_and_allows_repeat(voice_window, qtbot):
    window, speaker = voice_window
    phases = []
    window.voice.state.connect(phases.append)
    for _ in range(2):
        window.voice.start()
        qtbot.waitUntil(
            lambda: len(speaker.spoken) == _ + 1 and window.voice.turn.state == VoiceState.IDLE,
            timeout=5000,
        )
        assert window.voice.transcript.text() == "Tell me something helpful"
        assert window.voice.response.toPlainText() == speaker.spoken[-1]
    assert {"LISTENING", "TRANSCRIBING", "THINKING", "SPEAKING", "IDLE"} <= set(phases)


def test_provider_failure_keeps_transcript_and_retry_uses_new_explicit_provider(
    voice_window, qtbot, monkeypatch
):
    window, speaker = voice_window

    def fail(*a, **k):
        raise ValueError("RATE_LIMIT: fixture quota reached")

    monkeypatch.setattr("nexis.core.operator.generate", fail)
    window.voice.start()
    qtbot.waitUntil(lambda: "RATE_LIMIT" in window.voice.response.toPlainText(), timeout=5000)
    assert window.voice.transcript.text() and not speaker.spoken
    qtbot.waitUntil(lambda: not window.ai_jobs)
    monkeypatch.setattr(
        "nexis.core.operator.generate", lambda *a, **k: {"text": "Retry succeeded", "calls": []}
    )
    capture = window.voice.worker
    window.voice.submit_transcript()
    qtbot.waitUntil(
        lambda: speaker.spoken == ["Retry succeeded"] and window.voice.turn.state == VoiceState.IDLE
    )
    assert window.voice.worker is capture  # No new recording required.


def test_network_failure_cannot_disable_microphone_or_local_tts(
    voice_window, db, qtbot, monkeypatch
):
    window, speaker = voice_window
    db.execute("INSERT OR REPLACE INTO settings VALUES ('is_offline','true')")
    window.voice.start()
    qtbot.waitUntil(lambda: bool(speaker.spoken), timeout=5000)
    assert window.voice.metrics["sample_rate"] == 16000


def test_leaving_voice_cancels_preparing_capture_and_suppresses_stale_reply(voice_window, qtbot):
    window, speaker = voice_window
    window.voice.start()
    window.navigate("Dashboard")
    qtbot.wait(200)
    assert window.voice.worker is None and not speaker.spoken
    assert window.voice.turn.state == VoiceState.CANCELLED


def test_voice_state_generation_rejects_stale_callback_and_overlap():
    turn = VoiceTurn()
    first = turn.begin()
    with pytest.raises(ValueError, match="already active"):
        turn.begin()
    turn.cancel()
    turn.begin()
    assert not turn.change(VoiceState.SPEAKING, first)
    with pytest.raises(ValueError, match="Invalid"):
        turn.change(VoiceState.SPEAKING)
