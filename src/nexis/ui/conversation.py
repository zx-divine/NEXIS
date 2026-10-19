from pathlib import Path
from time import monotonic
from nexis.core.voice_session import VoiceTurn, VoiceState
from nexis.core.access import require_access
from nexis.core.privacy import sanitize_request

from PySide6.QtCore import Signal, QTimer, Qt
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from nexis.core.voice import VoiceWorker, setup_status
from nexis.ui.pages import button, heading
from nexis.ui.reactor import ReactorState, ReactorWidget


class ChatPage(QWidget):
    request = Signal(str)

    def __init__(self, window):
        super().__init__()
        self.window = window
        self.pending_prompt = ""
        self.stream_item = None
        layout = QVBoxLayout(self)
        heading(
            layout,
            "TEXT UPLINK",
            "Selected online provider · validated Windows tools · session-only messages",
        )
        self.messages = QListWidget()
        self.messages.setWordWrap(True)
        self.messages.setAccessibleName("Chat messages")
        layout.addWidget(self.messages, 1)
        self.input = QLineEdit()
        self.input.setMaxLength(1000)
        self.input.setPlaceholderText("Ask for help, or try: please open notepad")
        self.input.setAccessibleName("Chat input")
        self.input.returnPressed.connect(self.send)
        row = QHBoxLayout()
        row.addWidget(self.input, 1)
        self.send_button = button("Send", self.send, row)
        layout.addLayout(row)
        controls = QHBoxLayout()
        button("Copy selected message", self.copy_message, controls)
        button("Clear conversation", self.clear_conversation, controls)
        button("Cancel AI request", self.cancel_ai, controls)
        button("AI Providers / switch", lambda: window.navigate("AI Providers"), controls)
        button("Retry last prompt", self.retry, controls)
        button("Return to HUD", lambda: window.navigate("Dashboard"), controls)
        layout.addLayout(controls)
        self.add_message(
            "NEXIS",
            "Online uplink ready. Choose your AI provider to chat or plan permitted Windows actions. "
            "Chat is kept only until this application closes.",
        )

    def add_message(self, role, text):
        self.messages.addItem(role + "  //  " + text)
        while self.messages.count() > 200:
            self.messages.takeItem(0)
        self.messages.scrollToBottom()

    def send(self):
        text = sanitize_request(self.input.text().strip())
        if text:
            self.add_message("YOU", text)
            self.input.clear()
            self.request.emit(text)

    def copy_message(self):
        item = self.messages.currentItem()
        if not item:
            raise ValueError("Select a message to copy.")
        QApplication.clipboard().setText(item.text())

    def retry(self):
        if self.pending_prompt:
            self.request.emit(self.pending_prompt)

    def clear_conversation(self):
        for job in self.window.ai_jobs:
            job.cancel.set()
            if hasattr(job, "respond"):
                job.respond(False)
        self.stream_item = None
        self.messages.clear()
        self.pending_prompt = ""
        self.window.conversation_history.clear()

    def show_stream(self, text):
        if text.lstrip().startswith(("{", "[", "`")):
            return  # A structured plan is displayed only after complete validation.
        if self.stream_item is None:
            self.messages.addItem("AI DRAFT // " + sanitize_request(text))
            self.stream_item = self.messages.item(self.messages.count() - 1)
        else:
            self.stream_item.setText("AI DRAFT // " + sanitize_request(text))
        self.messages.scrollToBottom()

    def finish_stream(self, completed=True):
        if self.stream_item is not None:
            if completed:
                self.messages.takeItem(self.messages.row(self.stream_item))
            else:
                self.stream_item.setText(
                    self.stream_item.text().replace("AI DRAFT //", "INCOMPLETE AI DRAFT //", 1)
                )
            self.stream_item = None

    def cancel_ai(self):
        for job in self.window.ai_jobs:
            job.cancel.set()
        self.add_message(
            "NEXIS", "AI request cancelled. Any in-flight network read will stop at its timeout."
        )


class VoicePage(QWidget):
    request = Signal(str)
    state = Signal(str)

    def __init__(self, window):
        super().__init__()
        self.window, self.worker = window, None
        self.turn = VoiceTurn()
        self.pending_transcript = ""
        self.speech_id = None
        self.speech_service = None
        self.turn_error = False
        self.metrics = {}
        layout = QVBoxLayout(self)
        heading(
            layout,
            "VOICE UPLINK",
            "Talk → Vosk transcript → selected AI provider → Windows speech. No recording starts automatically.",
        )
        row = QHBoxLayout()
        self.reactor = ReactorWidget()
        self.reactor.setMaximumWidth(440)
        row.addWidget(self.reactor, 1)
        controls = QVBoxLayout()
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.PlainText)
        controls.addWidget(self.status)
        capture = QHBoxLayout()
        self.push = button("Talk", self.start, capture)
        self.stop_button = button("Stop and transcribe", self.finish_recording, capture)
        self.cancel_button = button("Cancel turn", self.stop, capture)
        controls.addLayout(capture)
        self.stop_button.setEnabled(False)
        self.indicator = QLabel("IDLE — MICROPHONE OFF")
        controls.addWidget(self.indicator)
        self.level = QProgressBar()
        self.level.setRange(0, 100)
        self.level.setAccessibleName("Live input level; recording only after Talk")
        controls.addWidget(self.level)
        setup = QHBoxLayout()
        self.model_button = button("Choose trusted Vosk model…", self.choose_model, setup)
        button("Voice setup / devices", lambda: window.navigate("Settings"), setup)
        button("Refresh voice setup", self.refresh_setup, setup)
        controls.addLayout(setup)
        self.transcript = QLineEdit()
        self.transcript.setMaxLength(1000)
        self.transcript.setAccessibleName("Recognized voice transcript; retained for retry")
        self.reactor.activated.connect(self.transcript.setFocus)
        self.transcript.setPlaceholderText(
            "Recognized text appears here and is sent to your selected provider; correct or retry it if needed."
        )
        controls.addWidget(self.transcript)
        retry = QHBoxLayout()
        self.execute = button("Retry / send transcript", self.submit_transcript, retry)
        button("Switch provider", lambda: window.navigate("AI Providers"), retry)
        controls.addLayout(retry)
        self.response = QPlainTextEdit()
        self.response.setReadOnly(True)
        self.response.setPlaceholderText(
            "Real provider response or specific error; transcript is retained."
        )
        controls.addWidget(self.response, 1)
        self.read_button = button("Read displayed response", self.read_response, controls)
        self.diagnostic = QLabel("Voice Diagnostics: capture inactive; no retained audio.")
        self.diagnostic.setWordWrap(True)
        controls.addWidget(self.diagnostic)
        button("Return to HUD", self.return_to_hud, controls)
        row.addLayout(controls, 2)
        layout.addLayout(row, 1)
        self.refresh_setup()

    def change_state(self, state, generation=None):
        if not self.turn.change(state, generation):
            return
        value = self.turn.state.value
        self.indicator.setText(
            value
            + (
                " — recording requested / see microphone status"
                if value == "LISTENING"
                else " — MICROPHONE OFF"
            )
        )
        visual = {"TRANSCRIBING": "PROCESSING", "THINKING": "PROCESSING", "CANCELLED": "IDLE"}.get(
            value, value
        )
        self.reactor.set_state(ReactorState(visual))
        self.state.emit(value)
        self.indicator.setStyleSheet(
            "color: #ff304d; font-weight: bold;" if value == "LISTENING" else ""
        )
        busy = value in {"LISTENING", "TRANSCRIBING", "THINKING", "SPEAKING"}
        self.execute.setEnabled(not busy)
        self.read_button.setEnabled(not busy)
        self.model_button.setEnabled(not busy)
        self.stop_button.setEnabled(value == "LISTENING")
        self.push.setEnabled(
            not busy and setup_status(self.window.db.setting("voice_model_path"))[0]
        )

    def refresh_setup(self):
        if self.worker and self.worker.isRunning():
            return
        from nexis.core.models import detect_model

        detected = detect_model(self.window.db.setting("voice_model_path"), self.window.data_dir)
        if detected and detected != self.window.db.setting("voice_model_path"):
            self.window.db.set_setting("voice_model_path", detected)
        ready, message = setup_status(self.window.db.setting("voice_model_path"))
        self.push.setEnabled(
            ready and self.turn.state in {VoiceState.IDLE, VoiceState.ERROR, VoiceState.CANCELLED}
        )
        self.status.setText(message)

    def choose_model(self):
        path = QFileDialog.getExistingDirectory(self, "Choose a trusted extracted Vosk model")
        if path:
            self.window.db.set_setting("voice_model_path", str(Path(path).resolve(strict=True)))
            self.refresh_setup()

    def start(self):
        if (
            self.worker
            and self.worker.isRunning()
            or self.turn.state in {VoiceState.THINKING, VoiceState.SPEAKING}
        ):
            return
        try:
            require_access(self.window.db, "microphone_access")
        except ValueError as exc:
            self.failure(str(exc))
            return
        ready, message = setup_status(self.window.db.setting("voice_model_path"))
        if not ready:
            self.failure(message)
            return
        generation = self.turn.begin()
        self.turn_error = False
        self.pending_transcript = ""
        self.transcript.clear()
        self.speech_id = None
        self.window.settings_page.voice_setup.stop_speech()
        self.change_state(VoiceState.LISTENING)
        self.status.setText(
            "Preparing recognition. Speak when LISTENING — microphone active appears."
        )
        self.capture_deadline = monotonic() + 3
        QTimer.singleShot(80, lambda: self.begin_capture(generation))

    def begin_capture(self, generation):
        if generation != self.turn.generation or self.window.closing:
            return
        speech = self.window.settings_page.voice_setup.speech
        if speech and speech.busy.is_set():
            if monotonic() > self.capture_deadline:
                self.failure("Windows speech has not stopped yet. Retry Talk after playback ends.")
            else:
                QTimer.singleShot(80, lambda: self.begin_capture(generation))
            return
        try:
            require_access(self.window.db, "microphone_access")
        except ValueError as exc:
            self.failure(str(exc))
            return
        worker = VoiceWorker(
            self.window.db.setting("voice_model_path"), self.window.db.setting("audio_input")
        )
        self.worker = worker

        def active():
            return (
                generation == self.turn.generation
                and not worker.cancel.is_set()
                and not self.window.closing
            )

        worker.status.connect(lambda text: self.voice_status(text) if active() else None)
        worker.level.connect(lambda value: self.audio_level(value) if active() else None)
        worker.partial.connect(
            lambda text: (
                self.transcript.setText(sanitize_request(text)[:1000]) if active() else None
            )
        )
        worker.measured.connect(
            lambda metrics: self.capture_measured(metrics) if active() else None
        )
        worker.transcript.connect(lambda text: self.recognized(text) if active() else None)
        worker.failed.connect(lambda message: self.failure(message) if active() else None)
        worker.finished.connect(lambda: self.finished(worker, generation))
        worker.start()

    def voice_status(self, text):
        self.status.setText(text)
        if text.startswith("LISTENING"):
            self.indicator.setText("LISTENING — MICROPHONE ACTIVE")
        elif text.startswith("TRANSCRIBING"):
            self.change_state(VoiceState.TRANSCRIBING)

    def audio_level(self, value):
        self.reactor.set_audio_level(value)
        self.level.setValue(min(100, int(value * 500)))

    def capture_measured(self, metrics):
        self.metrics = metrics
        self.diagnostic.setText(
            "Voice Diagnostics: "
            + metrics["device"]
            + "; "
            + str(metrics["sample_rate"])
            + " Hz, mono int16; "
            + str(metrics["audio_seconds"])
            + " s processed; peak RMS "
            + str(metrics["peak_rms"])
            + ". Capture stream released. No audio saved."
        )

    def recognized(self, text):
        text = sanitize_request(text)
        self.transcript.setText(text[:1000])
        self.pending_transcript = text[:1000].strip()

    def failure(self, message):
        self.turn_error = True
        self.status.setText(message)
        self.change_state(VoiceState.ERROR)

    def finished(self, worker=None, generation=None):
        self.level.setValue(0)
        self.reactor.set_audio_level(None)
        if worker is not self.worker or generation != self.turn.generation or self.window.closing:
            return
        if worker.cancel.is_set():
            self.cancelled()
        elif not self.turn_error and self.pending_transcript:
            self.submit_transcript()
        elif not self.turn_error:
            self.failure(
                "No speech was recognized. Check the live level and selected microphone, then Talk again. Nothing was sent."
            )

    def finish_recording(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop_recording()
            self.status.setText("Stopping capture and finishing recognition…")
            self.stop_button.setEnabled(False)

    def thinking(self):
        self.change_state(VoiceState.THINKING)
        self.status.setText(
            "Contacting only your selected provider. The transcript is retained for retry."
        )

    def attach_speech(self, service):
        if self.speech_service is service:
            return
        self.speech_service = service
        service.playback_finished.connect(
            lambda identifier, outcome: self.speech_finished(service, identifier, outcome)
        )
        service.finished.connect(
            lambda: (
                self.failure(
                    "Windows speech stopped before the reply completed. The answer is retained; retry speech initialization in Settings."
                )
                if self.speech_service is service
                and self.turn.state == VoiceState.SPEAKING
                and not self.window.closing
                else None
            )
        )

    def read_response(self):
        if (
            self.worker
            and self.worker.isRunning()
            or self.turn.state
            in {
                VoiceState.LISTENING,
                VoiceState.TRANSCRIBING,
                VoiceState.THINKING,
                VoiceState.SPEAKING,
            }
        ):
            self.status.setText("Finish or cancel the active turn before reading another response.")
            return
        text = self.response.toPlainText().strip()
        if text:
            self.receive_reply(text)

    def receive_reply(self, text):
        self.response.setPlainText(text)
        panel = self.window.settings_page.voice_setup
        if not self.window.db.setting("tts_enabled"):
            self.change_state(VoiceState.IDLE)
            self.status.setText("Reply ready. Read-aloud is disabled in Settings.")
            return
        if not panel.speech or not panel.speech.isRunning():
            panel.start_speech()
        if not panel.speech or not panel.speech.isRunning():
            self.failure(
                "Reply received, but Windows speech could not initialize. Retry speech in Settings; the answer is retained."
            )
            return
        self.attach_speech(panel.speech)
        self.change_state(VoiceState.SPEAKING)
        self.status.setText("Windows speech is speaking the reply. Cancel stops playback.")
        self.speech_id = panel.speech.say(text)
        if self.speech_id is None:
            self.failure("Speech queue is full. The reply is retained; stop speech and retry.")

    def speech_finished(self, service, identifier, outcome):
        if (
            service is not self.speech_service
            or identifier != self.speech_id
            or self.turn.state != VoiceState.SPEAKING
            or self.window.closing
        ):
            return
        self.speech_id = None
        if outcome == "PASS":
            self.change_state(VoiceState.IDLE)
            self.status.setText(
                "Ready for another turn. Speech synthesis completed; audible output requires your confirmation."
            )
        elif outcome == "CANCELLED":
            self.cancelled()
        else:
            self.failure(
                "The reply is retained, but Windows speech did not complete ("
                + outcome
                + "). Check the speaker, or shorten replies if the two-minute safety limit was reached."
            )

    def cancelled(self):
        self.change_state(VoiceState.CANCELLED)
        self.status.setText(
            "Turn cancelled; microphone and speech stopping. Your last transcript remains available for Retry."
        )

    def stop(self):
        self.turn.cancel()
        self.speech_id = None
        if self.worker and self.worker.isRunning():
            self.worker.cancel.set()
        if hasattr(self.window, "settings_page"):
            self.window.settings_page.voice_setup.stop_speech()
        if self.window.ai_origin == "voice":
            for job in self.window.ai_jobs:
                if job.isRunning():
                    job.cancel.set()
                    if hasattr(job, "respond"):
                        job.respond(False)
        self.cancelled()
        self.level.setValue(0)

    def submit_transcript(self):
        if self.worker and self.worker.isRunning():
            self.status.setText("Wait for the microphone to be released before sending.")
            return
        if any(job.isRunning() for job in self.window.ai_jobs):
            self.status.setText(
                "Wait or cancel the active provider request. Your transcript remains available."
            )
            return
        text = self.transcript.text().strip()
        if text:
            self.request.emit(text)

    def return_to_hud(self):
        self.stop()
        self.window.navigate("Dashboard")
