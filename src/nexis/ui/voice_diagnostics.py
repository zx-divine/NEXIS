"""Local, explicit-action standalone voice QA. Never starts capture on launch."""

import json
import os
from pathlib import Path
import re
from datetime import datetime, timezone
from uuid import uuid4

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from nexis.branding import application_icon, set_app_user_model_id
from nexis.core.models import MODEL, valid_model
from nexis.core.voice import VoiceWorker
from nexis.core.audio import level_percent
from nexis.core.privacy import sanitize_request
from nexis.platform.discovery import known_folder
from nexis.platform.speech import SpeechService
from nexis.ui.branding import BrandLogo

TEST_PHRASE = "Hello NEXIS, this is a microphone test."
SPEAKER_PHRASE = "Hello. I am NEXIS. My voice engine is working."


def evidence_directory():
    base = known_folder("B4BFCC3A-DB2C-424C-B029-7FE99A87C641") / "NEXIS-Voice-Engine"
    for name in ("models", "diagnostics", "logs", "standalone-tests", "test-results"):
        (base / name).mkdir(parents=True, exist_ok=True)
    return base


def relevant_transcript(text):
    words = set(re.findall(r"[a-z]+", text.casefold()))
    return {"hello", "microphone", "test"} <= words and len(
        words & {"hello", "this", "is", "a", "microphone", "test"}
    ) >= 5


def completed_cycles(base):
    cycles = {}
    for file in (base / "test-results").glob("standalone-cycle-*.json"):
        try:
            report = json.loads(file.read_text(encoding="utf-8"))
            if report.get("result") == "PASS":
                cycles[report["cycle"]] = report
        except (OSError, ValueError, KeyError):
            continue
    return cycles


class VoiceDiagnostics(QMainWindow):
    def __init__(self, base=None):
        super().__init__()
        self.base = Path(base) if base else evidence_directory()
        self.process_token = uuid4().hex
        self.worker = None
        self.speech_id = None
        self.record = None
        self.cancellation_test = False
        self.cancellation_passed = False
        self.cancel_reached_listening = False
        self.recording_requested = False
        self.closing = False
        self.setWindowTitle("NEXIS Voice Engine — Standalone Hardware Verification")
        self.setWindowIcon(application_icon())
        self.resize(920, 720)
        self.setMinimumSize(700, 600)
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        top = QHBoxLayout()
        top.addWidget(BrandLogo(64))
        self.title = QLabel("STANDALONE VOICE VERIFICATION")
        top.addWidget(self.title, 1)
        layout.addLayout(top)
        note = QLabel(
            "Microphone is OFF until you click Record. Audio stays in memory and is never saved or uploaded. Only the test transcript, device measurements and your confirmations are stored locally."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        self.devices = QComboBox()
        self.devices.setAccessibleName("Microphone selection")
        layout.addWidget(self.devices)
        self.output = QLabel()
        self.output.setWordWrap(True)
        layout.addWidget(self.output)
        row = QHBoxLayout()
        self.refresh_button = self.make_button("Refresh devices", self.refresh_devices, row)
        self.record_button = self.make_button("Record fresh speech", self.start_recording, row)
        self.stop_button = self.make_button("Stop and transcribe", self.stop_recording, row)
        self.cancel_button = self.make_button("Cancel / discard", self.cancel_recording, row)
        layout.addLayout(row)
        self.indicator = QLabel("IDLE — MICROPHONE OFF")
        self.indicator.setAccessibleName("Recording indicator")
        layout.addWidget(self.indicator)
        self.level = QProgressBar()
        self.level.setRange(0, 100)
        self.level.setAccessibleName("Live microphone level; active only while recording")
        layout.addWidget(self.level)
        self.prompt = QLabel('After clicking Record, say: "' + TEST_PHRASE + '"')
        self.prompt.setWordWrap(True)
        layout.addWidget(self.prompt)
        self.transcript = QPlainTextEdit()
        self.transcript.setReadOnly(True)
        self.transcript.setPlaceholderText("Your actual recognized words appear here.")
        self.transcript.setMaximumHeight(100)
        layout.addWidget(self.transcript)
        row = QHBoxLayout()
        self.tts_button = self.make_button("Test speaker", self.test_speaker, row)
        self.heard_yes = self.make_button(
            "I heard the full sentence", lambda: self.confirm_audible(True), row
        )
        self.heard_no = self.make_button(
            "I could not hear it", lambda: self.confirm_audible(False), row
        )
        layout.addLayout(row)
        self.reliability_button = self.make_button(
            "Cycle 3: test recording cancellation", self.test_cancellation, layout
        )
        self.finish_button = self.make_button("Save cycle and close", self.finish_cycle, layout)
        self.status = QLabel("Preparing local diagnostics. No recording starts automatically.")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(150)
        layout.addWidget(self.log, 1)
        self.speech = SpeechService()
        self.speech.status.connect(self.speech_status)
        self.speech.playback_started.connect(self.playback_started)
        self.speech.playback_finished.connect(self.playback_finished)
        self.speech.start()
        self.reset_controls()
        self.refresh_devices()
        self.update_cycle()

    @staticmethod
    def make_button(text, callback, layout):
        widget = QPushButton(text)
        widget.clicked.connect(callback)
        layout.addWidget(widget)
        return widget

    def reset_controls(self):
        self.stop_button.setEnabled(False)
        self.cancel_button.setEnabled(False)
        self.tts_button.setEnabled(False)
        self.heard_yes.setEnabled(False)
        self.heard_no.setEnabled(False)
        self.finish_button.setEnabled(False)

    def update_cycle(self):
        done = completed_cycles(self.base)
        self.cycle = next((i for i in range(1, 4) if i not in done), 4)
        self.title.setText("STANDALONE CYCLE " + str(min(self.cycle, 3)) + " / 3")
        self.reliability_button.setVisible(self.cycle == 3)
        if self.cycle == 4:
            self.record_button.setEnabled(False)
            self.status.setText(
                "All three standalone cycles are recorded. Close this utility and return to Codex to continue NEXIS integration."
            )
        elif self.cycle > 1 and done[self.cycle - 1]["process_token"] == self.process_token:
            self.record_button.setEnabled(False)
            self.status.setText("Close and reopen the utility for a genuinely fresh process.")
        elif self.cycle == 3 and not self.cancellation_passed:
            self.record_button.setEnabled(False)
            self.status.setText(
                "Cycle 3: first click the cancellation test. This visibly opens the microphone, cancels after one second, then releases it. Next record fresh speech."
            )
        else:
            self.status.setText(
                "Ready for cycle "
                + str(self.cycle)
                + ". Click Record and speak the displayed sentence, then Stop. Test the speaker and confirm whether you heard it."
            )

    def refresh_devices(self):
        if self.worker and self.worker.isRunning():
            return
        try:
            import sounddevice as sd

            self.devices.clear()
            default = sd.query_devices(kind="input")
            self.devices.addItem("Windows default — " + default["name"], None)
            for index, device in enumerate(sd.query_devices()):
                if device["max_input_channels"]:
                    self.devices.addItem(str(index) + " — " + device["name"], index)
            speaker = sd.query_devices(kind="output")
            self.output.setText(
                "Windows default speaker: "
                + speaker["name"]
                + ". Check this device's volume and mute state. NEXIS does not alter system volume."
            )
            self.log.appendPlainText("Device discovery succeeded; no audio stream opened.")
        except Exception as exc:
            self.output.setText(
                "Device discovery failed ("
                + type(exc).__name__
                + "). Check Windows audio devices and desktop microphone permissions."
            )
            self.record_button.setEnabled(False)

    def new_record(self):
        return {
            "cycle": self.cycle,
            "attempt": uuid4().hex,
            "process_token": self.process_token,
            "pid": os.getpid(),
            "time_utc": datetime.now(timezone.utc).isoformat(),
            "application": "standalone shared NEXIS VoiceWorker / Windows SAPI",
            "microphone_detection": "NOT VERIFIED",
            "real_audio_capture": "NOT VERIFIED",
            "recognition": "NOT VERIFIED",
            "transcript": "",
            "tts_completion": "NOT VERIFIED",
            "audible_output": "NOT VERIFIED",
            "cleanup": "NOT VERIFIED",
            "fresh_restart": "PASS"
            if self.cycle == 1
            or all(
                r["process_token"] != self.process_token
                for r in completed_cycles(self.base).values()
            )
            else "FAIL",
            "cancellation": "PASS" if self.cancellation_passed else "NOT VERIFIED",
            "result": "NOT VERIFIED",
            "recording_user_initiated": True,
            "audio_saved": False,
            "uploaded": False,
        }

    def start_recording(self):
        if self.worker and self.worker.isRunning():
            return
        if self.cycle > 3 or self.closing:
            return
        model = self.base / "models" / MODEL["id"]
        if not valid_model(model):
            self.status.setText(
                "Verified development model is unavailable. Return to Codex; no microphone opened."
            )
            return
        self.speech.stop_speaking()
        self.speech_id = None
        self.reset_controls()
        self.record = self.new_record()
        self.transcript.clear()
        self.recording_requested = True
        self.worker = VoiceWorker(str(model), self.devices.currentData())
        self.worker.status.connect(self.capture_status)
        self.worker.level.connect(lambda value: self.level.setValue(level_percent(value)))
        self.worker.transcript.connect(self.recognized)
        self.worker.measured.connect(self.measured)
        self.worker.failed.connect(self.capture_failure)
        self.worker.finished.connect(self.capture_finished)
        self.record_button.setEnabled(False)
        self.devices.setEnabled(False)
        self.refresh_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.cancel_button.setEnabled(True)
        self.indicator.setText("PREPARING — recording requested visibly by user")
        self.status.setText(
            "Loading the offline model. Speak when the red LISTENING indicator appears."
        )
        self.worker.start()

    def capture_status(self, text):
        self.indicator.setText(text)
        self.log.appendPlainText(text)
        if text.startswith("LISTENING"):
            self.indicator.setProperty("state", "recording")
            self.indicator.style().unpolish(self.indicator)
            self.indicator.style().polish(self.indicator)
            self.record["microphone_detection"] = "PASS"
            if self.cancellation_test:
                self.cancel_reached_listening = True
                QTimer.singleShot(1000, self.cancel_recording)
        else:
            self.indicator.setProperty("state", "")
            self.indicator.style().unpolish(self.indicator)
            self.indicator.style().polish(self.indicator)

    def stop_recording(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop_recording()
            self.stop_button.setEnabled(False)
            self.status.setText("Finishing recognition; microphone is being released.")

    def cancel_recording(self):
        if self.worker and self.worker.isRunning():
            self.worker.cancel.set()
            self.status.setText("Cancelling — pending speech will not be used.")

    def measured(self, metrics):
        self.record["audio"] = metrics
        loopback = any(
            value in metrics["device"].casefold() for value in ("stereo mix", "cable", "loopback")
        )
        self.record["real_audio_capture"] = (
            "PASS"
            if metrics["samples"] > 0 and metrics["peak_rms"] > 0.002 and not loopback
            else "NOT VERIFIED"
        )
        self.log.appendPlainText(json.dumps(metrics, ensure_ascii=False))

    def recognized(self, text):
        text = sanitize_request(text)
        self.transcript.setPlainText(text)
        self.record["transcript"] = text
        self.record["recognition"] = (
            "PASS"
            if relevant_transcript(text) and self.record["real_audio_capture"] == "PASS"
            else "FAIL"
        )
        self.persist()

    def capture_failure(self, text):
        self.status.setText(text)
        self.record["recognition"] = "FAIL"
        self.record["failure"] = text
        self.persist()

    def capture_finished(self):
        self.level.setValue(0)
        self.indicator.setText("MICROPHONE OFF — capture worker finished")
        self.indicator.setProperty("state", "")
        self.indicator.style().unpolish(self.indicator)
        self.indicator.style().polish(self.indicator)
        self.stop_button.setEnabled(False)
        self.cancel_button.setEnabled(False)
        self.devices.setEnabled(True)
        self.refresh_button.setEnabled(True)
        self.record["cleanup"] = "PASS"
        if self.cancellation_test:
            self.cancellation_passed = (
                self.cancel_reached_listening
                and self.worker.cancel.is_set()
                and not self.record["transcript"]
            )
            self.record["cancellation"] = "PASS" if self.cancellation_passed else "FAIL"
            self.record["test_kind"] = "explicit cancellation probe; not a fresh speech cycle"
            self.persist()
            self.cancellation_test = False
            self.reliability_button.setEnabled(not self.cancellation_passed)
            self.update_cycle()
        elif self.worker.cancel.is_set():
            self.record["result"] = "NOT VERIFIED"
            self.status.setText(
                "Recording cancelled and microphone released. Click Record to retry with fresh speech."
            )
        else:
            good = self.record["recognition"] == "PASS"
            self.tts_button.setEnabled(good)
            self.status.setText(
                "Phrase recognized from fresh audio. Click Test speaker."
                if good
                else "Recognition did not match the test phrase. Check input levels/device and click Record to retry. Empty or unrelated text is not a pass."
            )
        self.persist()
        self.record_button.setEnabled(self.cycle < 3 or self.cancellation_passed)

    def speech_status(self, text):
        self.log.appendPlainText(text)

    def test_speaker(self):
        if not self.record or self.record["recognition"] != "PASS":
            return
        self.tts_button.setEnabled(False)
        self.record_button.setEnabled(False)
        self.speech_id = self.speech.say(SPEAKER_PHRASE)
        self.status.setText(
            "Playing the speaker test. Wait for synthesis to finish, then confirm whether you heard the full sentence."
        )

    def playback_started(self, identifier):
        if identifier == self.speech_id:
            self.indicator.setText("SPEAKING — " + SPEAKER_PHRASE)

    def playback_finished(self, identifier, outcome):
        if identifier != self.speech_id or not self.record:
            return
        self.record["tts_completion"] = outcome if outcome in {"PASS", "FAIL"} else "FAIL"
        self.indicator.setText("IDLE — MICROPHONE OFF")
        self.heard_yes.setEnabled(outcome == "PASS")
        self.heard_no.setEnabled(True)
        self.tts_button.setEnabled(True)
        self.record_button.setEnabled(True)
        self.status.setText(
            "Synthesis completed. Was the full sentence audible? Use the confirmation buttons."
            if outcome == "PASS"
            else "Synthesis failed or was cancelled. Check Windows speaker/voice configuration and retry."
        )
        self.persist()

    def confirm_audible(self, heard):
        if not self.record:
            return
        self.record["audible_output"] = "PASS" if heard else "FAIL"
        required = (
            "microphone_detection",
            "real_audio_capture",
            "recognition",
            "tts_completion",
            "audible_output",
            "cleanup",
            "fresh_restart",
        )
        passed = all(self.record[key] == "PASS" for key in required) and (
            self.cycle != 3 or self.cancellation_passed
        )
        self.record["result"] = "PASS" if passed else "FAIL"
        self.finish_button.setEnabled(passed)
        self.heard_yes.setEnabled(False)
        self.heard_no.setEnabled(False)
        self.status.setText(
            "Cycle passed. Click Save cycle and close, then reopen the Desktop launcher for the next cycle."
            if passed
            else "Cycle not passed. Retry the failed stage. The recorded result is not hidden."
        )
        self.persist()

    def persist(self):
        if not self.record:
            return
        destination = (
            self.base
            / "test-results"
            / ("standalone-cycle-" + str(self.cycle) + "-" + self.record["attempt"] + ".json")
        )
        temporary = destination.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(self.record, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        os.replace(temporary, destination)

    def test_cancellation(self):
        if self.worker and self.worker.isRunning():
            return
        self.cancellation_test = True
        self.cancel_reached_listening = False
        self.start_recording()

    def finish_cycle(self):
        self.persist()
        self.close()

    def closeEvent(self, event):
        self.closing = True
        if self.worker and self.worker.isRunning():
            self.worker.cancel.set()
        self.speech.cancel.set()
        if (self.worker and self.worker.isRunning()) or self.speech.isRunning():
            self.status.setText("Closing audio workers safely; microphone and speech are stopping…")
            QTimer.singleShot(100, self.close)
            event.ignore()
            return
        self.persist()
        event.accept()


def main():
    set_app_user_model_id()
    app = QApplication([])
    app.setApplicationName("NEXIS Voice Diagnostics")
    app.setWindowIcon(application_icon())
    window = VoiceDiagnostics()
    from nexis.ui.themes import apply

    from nexis.storage.database import read_appearance
    profile = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData/Local"))) / "NEXIS/NEXIS Desktop/nexis.db"
    apply(*read_appearance(profile))
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
