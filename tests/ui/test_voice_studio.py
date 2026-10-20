"""Voice Studio control-flow tests with explicit injected capture; not hardware proof."""
from threading import Event
from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QDialog

from nexis.ui.main_window import MainWindow
from nexis.core.results import Preview, Risk
from nexis.ui import dialogs


class Capture(QObject):
    status = Signal(str)
    input_metrics = Signal(object)
    partial = Signal(str)
    transcript = Signal(str)
    measured = Signal(object)
    calibrated = Signal(float)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, *args):
        super().__init__()
        self.args = args
        self.cancel = Event()
        self.running = False
        self.device_name = "Explicit fixture microphone"

    def isRunning(self):
        return self.running

    def start(self):
        self.running = True
        self.status.emit("LISTENING — microphone active")

    def stop_recording(self):
        self.running = False
        self.finished.emit()


def test_settings_never_records_on_open_and_preferences_persist(qtbot, db, tmp_path, platform):
    window = MainWindow(db, tmp_path, platform)
    qtbot.addWidget(window)
    panel = window.settings_page.voice_setup.microphone
    window.navigate("Settings")
    assert panel.worker is None
    panel.slider.setValue(145)
    panel.pause.setValue(1900)
    assert db.setting("mic_sensitivity") == 145 and db.setting("mic_end_silence_ms") == 1900
    window.set_microphone_muted(True)
    panel.restore_defaults()
    assert db.setting("microphone_muted") and db.setting("mic_sensitivity") == 100
    panel.start()
    assert panel.worker is None and "Hard mute" in panel.notice.text()
    window.close()


def test_explicit_calibration_preview_device_change_and_navigation_cleanup(qtbot, db, tmp_path, platform, monkeypatch):
    monkeypatch.setattr("nexis.ui.microphone.VoiceWorker", Capture)
    window = MainWindow(db, tmp_path, platform)
    qtbot.addWidget(window)
    panel = window.settings_page.voice_setup.microphone
    window.navigate("Settings")
    db.set_setting("audio_input", "Fixture selected input")
    panel.start(True)
    worker = panel.worker
    assert worker.args[1] == "Fixture selected input" and worker.args[3] is True
    worker.calibrated.emit(0.002)
    assert db.setting("mic_noise_floor") == 0.002
    assert db.setting("mic_calibration_device") == "Explicit fixture microphone"
    worker.input_metrics.emit({"rms": 0.02, "gain": 1, "speech": True, "clipping": True})
    assert "CLIPPING" in panel.notice.text()
    worker.transcript.emit("local preview")
    assert panel.preview.toPlainText() == "local preview" and not window.ai_jobs
    window.navigate("Dashboard")
    assert worker.cancel.is_set()
    worker.transcript.emit("stale callback")
    assert panel.preview.toPlainText() == "local preview"
    worker.stop_recording()
    window.close()


def test_hard_mute_rapid_transitions_cancel_capture_and_never_start_a_new_one(qtbot, db, tmp_path, platform, monkeypatch):
    monkeypatch.setattr("nexis.ui.microphone.VoiceWorker", Capture)
    window = MainWindow(db, tmp_path, platform)
    qtbot.addWidget(window)
    panel = window.settings_page.voice_setup.microphone
    panel.start()
    worker = panel.worker
    for _ in range(30):
        window.set_microphone_muted(True)
        assert worker.cancel.is_set()
        window.set_microphone_muted(False)
        assert panel.worker is worker
    worker.stop_recording()
    window.set_microphone_muted(True)
    window.voice.start()
    assert window.voice.worker is None
    window.close()


def test_pending_approval_closes_on_cancel_and_cannot_be_accepted_late(qtbot, db, tmp_path, platform):
    window = MainWindow(db, tmp_path, platform)
    qtbot.addWidget(window)
    cancel = Event()
    window._approval_cancel = cancel
    seen = []

    def cancel_dialog():
        seen.extend(d for d in window.findChildren(QDialog) if d.isVisible())
        cancel.set()

    QTimer.singleShot(30, cancel_dialog)
    preview = Preview("test", "fixture", "no effect", Risk.HIGH, "review")
    assert not dialogs.confirm(window, preview)
    assert seen
    window.close()


def test_hands_free_requires_talk_and_ignores_stale_follow_up_after_mute(qtbot, db, tmp_path, platform, monkeypatch):
    window = MainWindow(db, tmp_path, platform)
    qtbot.addWidget(window)
    window.show()
    window.navigate("Voice Chat")
    calls = []
    monkeypatch.setattr(window.voice, "start", lambda **kwargs: calls.append(kwargs))
    window.voice.hands_free.setChecked(True)
    window.voice.schedule_follow_up()
    qtbot.wait(550)
    assert calls == []  # Checkbox alone does not arm a recording session.
    window.voice.hands_free_armed = True
    window.voice.schedule_follow_up()
    window.set_microphone_muted(True)
    qtbot.wait(550)
    assert calls == []
    window.close()


def test_selected_sapi_output_is_validated_and_removed_output_falls_back():
    from nexis.platform.speech import SpeechService

    class Token:
        Id = "fixture-speaker"

        def GetDescription(self):
            return "Fixture speaker"

    class Tokens:
        Count = 1

        def Item(self, i):
            return Token()

    class Speaker:
        def GetAudioOutputs(self):
            return Tokens()

    speech = SpeechService(output_preference="fixture-speaker")
    speaker = Speaker()
    speech.bind_output(speaker)
    assert speaker.AudioOutput.Id == "fixture-speaker"
    speech.output_preference = "removed-device"
    other = Speaker()
    statuses = []
    speech.status.connect(statuses.append)
    speech.bind_output(other)
    assert not hasattr(other, "AudioOutput") and "unavailable" in statuses[-1]
