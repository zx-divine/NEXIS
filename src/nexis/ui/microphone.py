"""Settings diagnostics use the same capture engine; never send preview text to AI."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGroupBox, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QSpinBox, QSlider, QCheckBox, QPlainTextEdit

from nexis.core.access import require_access
from nexis.core.audio import input_options, level_percent
from nexis.core.voice import VoiceWorker
from nexis.ui.pages import button


class MicrophonePanel(QGroupBox):
    def __init__(self, window):
        super().__init__("Microphone test and sensitivity")
        self.window, self.worker = window, None
        self.closing = False
        layout = QVBoxLayout(self)
        self.notice = QLabel("Microphone OFF. Uses the selected device above. A test or calibration starts only when you click its button; previews are never sent to AI.")
        self.notice.setWordWrap(True)
        self.notice.setTextFormat(Qt.PlainText)
        layout.addWidget(self.notice)
        self.level = QProgressBar()
        self.level.setAccessibleName("Microphone input level in dBFS; recording only during a test")
        layout.addWidget(self.level)
        self.indicator = QLabel("IDLE — MICROPHONE OFF")
        self.indicator.setWordWrap(True)
        self.indicator.setTextFormat(Qt.PlainText)
        layout.addWidget(self.indicator)
        row = QHBoxLayout()
        row.addWidget(QLabel("Sensitivity (%)"))
        self.sensitivity = QSpinBox()
        self.sensitivity.setRange(50, 200)
        self.sensitivity.setValue(window.db.setting("mic_sensitivity"))
        self.sensitivity.setAccessibleName("Microphone sensitivity; bounded speech gain only")
        self.sensitivity.valueChanged.connect(lambda v: window.db.set_setting("mic_sensitivity", v))
        row.addWidget(self.sensitivity)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(50, 200)
        self.slider.setValue(self.sensitivity.value())
        self.slider.setAccessibleName("Speech sensitivity slider; fifty to two hundred percent")
        self.slider.valueChanged.connect(self.sensitivity.setValue)
        self.sensitivity.valueChanged.connect(self.slider.setValue)
        row.addWidget(self.slider)
        row.addWidget(QLabel("Pause before finish (ms)"))
        self.pause = QSpinBox()
        self.pause.setRange(700, 3000)
        self.pause.setSingleStep(100)
        self.pause.setValue(window.db.setting("mic_end_silence_ms"))
        self.pause.setAccessibleName("Silence duration before ending a spoken turn")
        self.pause.valueChanged.connect(lambda v: window.db.set_setting("mic_end_silence_ms", v))
        row.addWidget(self.pause)
        layout.addLayout(row)
        self.normalize = QCheckBox("Gentle speech gain (up to 4×; does not boost detected background-only frames)")
        self.normalize.setChecked(window.db.setting("mic_normalize"))
        self.normalize.toggled.connect(lambda v: window.db.set_setting("mic_normalize", v))
        layout.addWidget(self.normalize)
        row = QHBoxLayout()
        self.test_button = button("Test normal speech", lambda: self.start(False), row)
        self.calibrate_button = button("Calibrate: stay quiet for 2 seconds", lambda: self.start(True), row)
        self.finish_button = button("Stop and transcribe", self.finish, row)
        button("Cancel / discard", self.stop, row)
        layout.addLayout(row)
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setMaximumHeight(110)
        self.preview.setAccessibleName("Local microphone transcription preview; not sent to AI")
        layout.addWidget(self.preview)
        button("Restore voice defaults (keeps Hard Mute)", self.restore_defaults, layout)
        self.finish_button.setEnabled(False)

    def start(self, calibrate=False):
        if self.worker and self.worker.isRunning():
            return
        try:
            if self.window.db.setting("microphone_muted"):
                raise ValueError("Hard mute is on. Use Wake / enable microphone first; it does not start recording.")
            require_access(self.window.db, "microphone_access")
            panel = self.window.settings_page.voice_setup
            if panel.speech and panel.speech.busy.is_set():
                raise ValueError("Stop speech playback before testing the microphone to avoid feedback.")
            if self.window.voice.worker and self.window.voice.worker.isRunning():
                raise ValueError("Finish Voice Chat recording before running a microphone test.")
            self.preview.clear()
            worker = VoiceWorker(self.window.db.setting("voice_model_path"), self.window.db.setting("audio_input"), input_options(self.window.db), calibrate)
            self.worker = worker

            def active():
                return self.worker is worker and not worker.cancel.is_set() and not self.window.closing

            worker.status.connect(lambda t: self.indicator.setText(t) if active() else None)
            worker.input_metrics.connect(lambda m: self.show_metrics(m) if active() else None)
            worker.partial.connect(lambda t: self.preview.setPlainText(t) if active() else None)
            worker.transcript.connect(lambda t: self.preview.setPlainText(t) if active() else None)
            worker.measured.connect(lambda m: self.show_result(m) if active() else None)
            worker.calibrated.connect(lambda v: self.save_calibration(v, worker) if active() else None)
            worker.failed.connect(lambda t: self.notice.setText(t) if active() else None)
            worker.finished.connect(lambda: self.finished(worker))
            self.test_button.setEnabled(False)
            self.calibrate_button.setEnabled(False)
            self.finish_button.setEnabled(not calibrate)
            panel.input.setEnabled(False)
            self.indicator.setText("PREPARING — recording requested by you")
            worker.start()
        except ValueError as exc:
            self.notice.setText(str(exc))

    def show_metrics(self, metrics):
        self.level.setValue(level_percent(metrics["rms"]))
        self.notice.setText(
            ("CLIPPING — reduce microphone gain or move farther away. " if metrics["clipping"] else "")
            + f"Raw RMS {metrics['rms']:.5f}; detected {'speech' if metrics['speech'] else 'background'}; speech gain {metrics['gain']:.2f}×. No audio saved."
        )

    def show_result(self, metrics):
        self.notice.setText("Input: " + metrics["device"] + ". Stream released. "
                            + ("Contextual greeting selected; raw decoder: " + metrics["raw_transcript"] if metrics.get("greeting_adapted") else "Original words preserved.")
                            + (" Clipping detected; reduce hardware gain." if metrics.get("clipping_frames") else ""))

    def save_calibration(self, value, worker):
        self.window.db.set_setting("mic_noise_floor", float(value))
        self.window.db.set_setting("mic_calibration_device", worker.device_name)
        self.notice.setText(f"Background calibrated ({value:.5f} RMS) for this microphone. Speak normally during Test normal speech. A different device starts with conservative defaults.")

    def finish(self):
        if self.worker:
            self.worker.stop_recording()

    def stop(self):
        if self.worker:
            self.worker.cancel.set()
        self.level.setValue(0)
        self.indicator.setText("CANCELLING — microphone release requested")

    def finished(self, worker):
        if worker is not self.worker:
            return
        self.level.setValue(0)
        self.indicator.setText("MICROPHONE OFF — worker finished")
        self.test_button.setEnabled(True)
        self.calibrate_button.setEnabled(True)
        self.finish_button.setEnabled(False)
        self.window.settings_page.voice_setup.input.setEnabled(True)

    def restore_defaults(self):
        if self.worker and self.worker.isRunning():
            self.notice.setText("Stop the microphone test before restoring voice defaults.")
            return
        from nexis.storage.database import DEFAULTS

        for key in ("mic_sensitivity", "mic_noise_floor", "mic_calibration_device", "mic_end_silence_ms", "mic_normalize", "audio_input", "tts_voice", "tts_output"):
            self.window.db.set_setting(key, DEFAULTS[key])
        self.sensitivity.setValue(100)
        self.pause.setValue(1400)
        self.normalize.setChecked(True)
        panel = self.window.settings_page.voice_setup
        for combo in (panel.input, panel.voices, panel.outputs):
            combo.setCurrentIndex(0)
        self.notice.setText("Voice defaults restored. Hard Mute is unchanged. Microphone remains OFF.")
