"""Guided setup and bounded background jobs for ordinary Windows users."""

from datetime import datetime, timezone
from threading import Event
from functools import wraps
import logging

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QApplication,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QCheckBox,
    QGroupBox,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QInputDialog,
    QFileIconProvider,
)
from PySide6.QtCore import QFileInfo

from nexis.core.catalog import Catalog
from nexis.core.models import MODEL, install_model, detect_model
from nexis.platform.discovery import discover
from nexis.platform.speech import SpeechService
from nexis.ui.pages import button
from nexis.ui import dialogs


def safe_ui(method):
    @wraps(method)
    def guarded(self, *args, **kwargs):
        try:
            return method(self, *args, **kwargs)
        except Exception as exc:
            logging.getLogger("nexis").warning("Setup UI failed (%s)", type(exc).__name__)
            message = (
                str(exc)
                if isinstance(exc, ValueError)
                else "Setup could not complete. Check local storage, available devices and Diagnostics, then retry. Other features remain available."
            )
            if hasattr(self, "status") and isinstance(self.status, QLabel):
                self.status.setText(message)
            elif hasattr(self, "output"):
                self.output.setPlainText(message)

    return guarded


class Task(QThread):
    result = Signal(object)
    failed = Signal(str)
    progress = Signal(str)

    def __init__(self, function, parent=None):
        super().__init__(parent)
        self.function = function
        self.cancel = Event()

    def run(self):
        try:
            value = self.function(self.cancel, self.progress.emit)
            if not self.cancel.is_set():
                self.result.emit(value)
        except Exception as exc:
            if not self.cancel.is_set():
                self.failed.emit(
                    str(exc)
                    if isinstance(exc, ValueError)
                    else "This operation could not complete. Check connectivity, free disk space and Diagnostics, then retry."
                )
        finally:
            self.function = None


def ProviderPanel(directory, parent=None):
    """Compatibility constructor for the unified provider manager UI."""
    from nexis.ui.providers_page import AIProvidersPage

    return AIProvidersPage(directory, parent)


class DiscoveryPanel(QGroupBox):
    def __init__(self, window):
        super().__init__("Discovered applications — reviewed before launching")
        self.window, self.jobs = window, []
        self.catalog = Catalog(window.db)
        layout = QVBoxLayout(self)
        self.status = QLabel("Discovery has not run yet.")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.list = QListWidget()
        self.list.setMinimumHeight(180)
        self.list.setAccessibleName("Discovered applications")
        layout.addWidget(self.list)
        row = QHBoxLayout()
        button("Rescan applications", self.scan, row)
        button("Open selected", self.open_selected, row)
        button("Rename alias", self.rename, row)
        button("Hide / show", self.hide_selected, row)
        button("Remove entry", self.remove, row)
        layout.addLayout(row)
        self.refresh()

    def refresh(self):
        self.list.clear()
        self.entries = self.catalog.rows(include_hidden=True)
        icons = QFileIconProvider()
        for entry in self.entries:
            label = (entry["alias"] or entry["name"]) + "  ·  " + entry["source"]
            if entry["hidden"]:
                label += "  [hidden]"
            if not entry["available"]:
                label += "  [not available]"
            item = QListWidgetItem(label)
            item.setToolTip(entry["target"])
            if entry["kind"] == "exe" and entry["available"]:
                item.setIcon(icons.icon(QFileInfo(entry["target"])))
            self.list.addItem(item)
        self.status.setText(
            f"{len(self.entries)} application(s) in local catalog. No application is launched during discovery."
        )

    def scan(self):
        if any(job.isRunning() for job in self.jobs):
            return
        self.status.setText(
            "Discovering Start Menu entries, Windows registrations and approved shortcuts…"
        )
        approved = self.window.db.rows("SELECT * FROM shortcuts WHERE kind='application'")
        task = Task(lambda cancel, progress: discover(cancel, approved), self)
        task.result.connect(self.discovered)
        task.failed.connect(self.status.setText)
        self.jobs.append(task)
        task.start()

    @safe_ui
    def discovered(self, result):
        apps, issues = result
        self.catalog.update(apps)
        self.refresh()
        if issues:
            self.status.setText(self.status.text() + " " + " ".join(issues))

    def selected(self):
        index = self.list.currentRow()
        if index < 0:
            raise ValueError("Choose an application first.")
        return self.entries[index]

    def open_selected(self):
        entry = self.selected()
        if entry["hidden"] or not entry["available"]:
            raise ValueError("This application is hidden or unavailable.")
        self.window.submit("open app:" + entry["id"])

    def rename(self):
        entry = self.selected()
        alias, accepted = QInputDialog.getText(
            self,
            "Application alias",
            "Name to use in commands",
            text=entry["alias"] or entry["name"],
        )
        if accepted:
            self.catalog.preferences(entry["id"], alias, bool(entry["hidden"]))
            self.refresh()

    def hide_selected(self):
        entry = self.selected()
        self.catalog.preferences(entry["id"], entry["alias"], not bool(entry["hidden"]))
        self.refresh()

    def remove(self):
        entry = self.selected()
        self.catalog.preferences(entry["id"], entry["alias"], removed=True)
        self.refresh()

    def stale(self):
        try:
            last = datetime.fromisoformat(self.window.db.setting("catalog_scanned_at"))
            return (datetime.now(timezone.utc) - last).total_seconds() > 86400
        except (ValueError, TypeError):
            return True


class VoiceSetupPanel(QGroupBox):
    def __init__(self, window):
        super().__init__("Voice Studio — offline speech and Windows audio")
        self.window, self.jobs = window, []
        self.speech = None
        layout = QVBoxLayout(self)
        self.status = QLabel(
            "Talk/tests use the selected microphone explicitly. Optional local Hey NEXIS listening is managed in Always Active and requires a separate opt-in. Windows' default microphone and speaker are used when no device is selected. If Windows denies access, review its desktop microphone permissions."
        )
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        languages = QLabel("Verified bundled speech language: English (United States). Hindi/Hinglish recognition is not validated and no verified pack for those languages is bundled. Unicode chat input is supported; response language and Windows voice availability depend on the selected provider/model and installed voices.")
        languages.setWordWrap(True)
        layout.addWidget(languages)
        row = QHBoxLayout()
        self.download_button = button(
            f"Set up {MODEL['language']} offline speech (41.2 MB)", self.download, row
        )
        button("Cancel download", self.cancel_download, row)
        layout.addLayout(row)
        self.voices = QComboBox()
        self.voices.addItem("Windows default voice", "")
        self.voices.currentIndexChanged.connect(self.select_voice)
        layout.addWidget(self.voices)
        self.outputs = QComboBox()
        self.outputs.setAccessibleName("Windows SAPI speaker output; next utterance")
        self.outputs.addItem("Windows default speaker (recommended)", "")
        self.outputs.currentIndexChanged.connect(self.select_output)
        layout.addWidget(self.outputs)
        self.tts_enabled = QCheckBox("Read voice-chat replies aloud")
        self.tts_enabled.setChecked(window.db.setting("tts_enabled"))
        self.tts_enabled.toggled.connect(self.save_tts)
        layout.addWidget(self.tts_enabled)
        row = QHBoxLayout()
        button("Test Windows voice", self.test_voice, row)
        button("Stop speech", self.stop_speech, row)
        button("Retry speech initialization", self.start_speech, row)
        layout.addLayout(row)
        self.input = QComboBox()
        self.input.addItem("Windows default microphone (recommended)", "")
        self.input.currentIndexChanged.connect(self.select_input)
        layout.addWidget(self.input)
        button("Troubleshoot / refresh microphones", self.refresh_inputs, layout)
        self.device_status = QLabel(
            "Manual microphone selection is optional. No capture runs during device discovery."
        )
        self.device_status.setWordWrap(True)
        layout.addWidget(self.device_status)
        from nexis.ui.microphone import MicrophonePanel

        self.microphone = MicrophonePanel(window)
        layout.addWidget(self.microphone)

    def refresh_model(self):
        path = detect_model(self.window.db.setting("voice_model_path"), self.window.data_dir)
        if path:
            self.window.db.set_setting("voice_model_path", path)
            self.download_button.setText("English offline model ready — no download needed")
            self.download_button.setEnabled(False)
        return path

    def download(self):
        if self.refresh_model():
            return
        if any(job.isRunning() for job in self.jobs):
            return
        if self.window.voice.worker and self.window.voice.worker.isRunning():
            raise ValueError("Stop listening before setting up a different speech model.")
        answer = QMessageBox.question(
            self,
            "Download offline speech model?",
            f"Download {MODEL['language']} ({MODEL['size'] / 1000000:.1f} MB) from alphacephei.com?\nLicense: {MODEL['license']}. NEXIS verifies a pinned SHA-256 before safely extracting into its local data directory. Audio stays on your computer.\nNo recording will start.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        task = Task(
            lambda cancel, progress: install_model(
                self.window.data_dir, cancel, progress, consent=True
            ),
            self,
        )
        task.progress.connect(self.status.setText)
        task.result.connect(self.installed)
        task.failed.connect(self.download_failed)
        task.finished.connect(self.download_finished)
        self.jobs.append(task)
        self.download_button.setEnabled(False)
        task.start()

    @safe_ui
    def installed(self, path):
        self.window.db.set_setting("voice_model_path", path)
        self.window.voice.refresh_setup()
        self.status.setText(
            "Verified offline model installed and selected. Use Push to talk when ready."
        )

    def download_failed(self, text):
        self.status.setText(text + " Select Set up offline speech to retry.")

    def download_finished(self):
        self.download_button.setEnabled(not bool(self.refresh_model()))

    def cancel_download(self):
        for job in self.jobs:
            if job.isRunning():
                job.cancel.set()
        self.status.setText("Cancelling setup. Retry resumes any safely cached download.")

    def start_speech(self):
        if self.speech and self.speech.isRunning():
            return
        self.speech = SpeechService(self.window.db.setting("tts_voice"), self.window.db.setting("tts_output"))
        self.speech.status.connect(self.device_status.setText)
        self.speech.voices.connect(self.voices_loaded)
        self.speech.outputs.connect(self.outputs_loaded)
        self.window.voice.attach_speech(self.speech)
        self.speech.start()

    def voices_loaded(self, voices):
        self.voices.blockSignals(True)
        self.voices.clear()
        self.voices.addItem("Windows default voice", "")
        for key, label in voices:
            self.voices.addItem(label, key)
        index = self.voices.findData(self.window.db.setting("tts_voice"))
        self.voices.setCurrentIndex(max(index, 0))
        self.voices.blockSignals(False)

    def outputs_loaded(self, entries):
        self.outputs.blockSignals(True)
        self.outputs.clear()
        self.outputs.addItem("Windows default speaker (recommended)", "")
        for key, label in entries:
            self.outputs.addItem(label, key)
        self.outputs.setCurrentIndex(max(0, self.outputs.findData(self.window.db.setting("tts_output"))))
        self.outputs.blockSignals(False)

    @safe_ui
    def select_output(self, index=None):
        value = self.outputs.currentData() or ""
        self.window.db.set_setting("tts_output", value)
        if self.speech:
            self.speech.select_output(value)

    @safe_ui
    def select_voice(self, index=None):
        value = self.voices.currentData() or ""
        self.window.db.set_setting("tts_voice", value)
        if self.speech:
            self.speech.select(value)

    @safe_ui
    def save_tts(self, enabled):
        self.window.db.set_setting("tts_enabled", enabled)

    def test_voice(self):
        if self.window.db.setting("microphone_muted"):
            self.device_status.setText("Hard mute is on. Wake first to test speech output.")
            return
        if any(w and w.isRunning() for w in (self.window.voice.worker, self.microphone.worker)):
            self.device_status.setText("Stop microphone capture before testing the speaker to avoid feedback.")
            return
        if not self.speech or not self.speech.isRunning():
            self.start_speech()
            self.device_status.setText("Initializing Windows speech; select Test again when ready.")
            return
        self.speech.say("NEXIS speech output is ready.")

    def stop_speech(self):
        if self.speech:
            self.speech.stop_speaking()

    def refresh_inputs(self):
        if any(job.isRunning() for job in self.jobs):
            return

        def devices(cancel, progress):
            import sounddevice as sd

            return [(d["name"], d["max_input_channels"]) for d in sd.query_devices()]

        task = Task(devices, self)
        task.result.connect(self.inputs_loaded)
        task.failed.connect(self.device_status.setText)
        self.jobs.append(task)
        task.start()

    def inputs_loaded(self, devices):
        self.input.blockSignals(True)
        self.input.clear()
        self.input.addItem("Windows default microphone (recommended)", "")
        for name, channels in devices:
            if channels and self.input.findData(name) < 0:
                self.input.addItem(name, name)
        index = self.input.findData(self.window.db.setting("audio_input"))
        self.input.setCurrentIndex(max(0, index))
        self.input.blockSignals(False)
        self.device_status.setText(
            "Microphone list refreshed. If your saved device disappeared, Windows default will be used. Capture remains off."
        )

    @safe_ui
    def select_input(self, index=None):
        self.window.db.set_setting("audio_input", self.input.currentData() or "")


def start_chat(window, text, origin):
    import os
    from nexis.core.operator import OperatorWorker

    window.desktop_experience.wake.pause()

    if any(job.isRunning() for job in window.ai_jobs) or (window.worker and window.worker.isRunning()):
        window.ai_error(
            "An AI request or manual action is already running. Wait or cancel it; your prompt is retained.",
            origin,
        )
        return
    context = {"current_nexis_window_id": int(window.winId()), "current_nexis_pid": os.getpid()}
    job = OperatorWorker(
        window.db, window.data_dir, text, window.platform, context, window.conversation_history[:-1],
        allow_radio=origin != "voice" or getattr(window.voice, "radio_reviewed", False),
    )
    window.ai_origin = origin
    window.current_ai = job
    window.ai_jobs.append(job)
    window.execute.setEnabled(False)
    window.chat.send_button.setEnabled(False)
    window.chat.input.setEnabled(False)

    def active():
        return window.current_ai is job and not job.cancel.is_set() and not window.closing

    job.reply.connect(lambda value: window.ai_reply(value, origin) if active() else None)
    job.failed.connect(lambda value: window.ai_error(value, origin) if active() else None)
    job.phase.connect(lambda value: window.online_phase(value, origin) if active() else None)
    job.partial.connect(lambda value: window.ai_partial(value, origin) if active() else None)

    def confirm(preview):
        window.permission_status.setText("PERMISSIONS / AWAITING REVIEW")
        window.set_state("WAITING_PERMISSION")
        window._approval_cancel = job.cancel
        try:
            allowed = dialogs.confirm(window, preview) if active() else False
        finally:
            window._approval_cancel = None
        window.permission_status.setText(
            "PERMISSIONS / APPROVED" if allowed else "PERMISSIONS / DENIED"
        )
        job.respond(allowed)
        window.set_state("PROCESSING" if allowed and active() else "IDLE")

    job.permission.connect(confirm)
    job.clipboard.connect(
        lambda value: QApplication.clipboard().setText(value) if active() else None
    )
    job.finished.connect(lambda: window.online_finished(job, origin))
    job.start()
