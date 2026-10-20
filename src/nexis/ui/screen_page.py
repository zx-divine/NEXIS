"""Visible, explicit capture/preview/send. Never called by the AI tool registry."""

from PySide6.QtCore import Qt, QBuffer, QByteArray, QIODevice
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QCheckBox, QLineEdit,
    QLabel, QPlainTextEdit, QMessageBox, QApplication,
)

from nexis.core.access import require_access
from nexis.core.identity import provider_label
from nexis.core.vision import MAX_IMAGE_BYTES, analyze_image
from nexis.core.providers import validate_profile
from nexis.ui.pages import heading, button
from nexis.ui.setup_services import Task, safe_ui


class ScreenPage(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window, self.jobs, self.image = window, [], b""
        self.generation = 0
        layout = QVBoxLayout(self)
        heading(layout, "SCREEN AWARENESS", "Experimental. No continuous capture. Hide passwords, private messages and protected content first. Captures stay in memory unless you explicitly approve a request to the selected provider; its data policies then apply. Vision availability must be verified for your configured model.")
        self.enabled = QCheckBox("Enable explicit screen preview and optional vision analysis")
        self.enabled.setChecked(window.db.setting("screen_awareness_enabled"))
        self.enabled.toggled.connect(self.toggle)
        layout.addWidget(self.enabled)
        row = QHBoxLayout()
        self.source = QComboBox()
        self.source.setAccessibleName("Explicit screenshot source")
        row.addWidget(self.source, 1)
        button("Refresh sources", self.refresh_sources, row)
        button("Capture preview", self.capture, row)
        button("Cancel / discard", self.discard, row)
        layout.addLayout(row)
        self.preview = QLabel("No capture. The screen has not been read.")
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMaximumHeight(260)
        self.preview.setMinimumHeight(100)
        self.preview.setAccessibleName("Screenshot preview; review before transmission")
        layout.addWidget(self.preview)
        self.question = QLineEdit("Explain the visible error or interface. Do not take any action.")
        self.question.setMaxLength(1000)
        self.question.setAccessibleName("Question about the screenshot")
        layout.addWidget(self.question)
        self.send_button = button("Review destination & approve sending…", self.send, layout)
        self.send_button.setEnabled(False)
        self.status = QLabel("OFF until enabled and Capture preview is clicked. No screenshot files are created. Sending is a separate explicit action.")
        self.status.setTextFormat(Qt.PlainText)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.answer = QPlainTextEdit()
        self.answer.setReadOnly(True)
        self.answer.setPlaceholderText("Vision explanation only; no command execution")
        layout.addWidget(self.answer, 1)
        self.refresh_sources()

    def refresh_sources(self):
        self.source.clear()
        self.source.addItem("Current NEXIS window only", None)
        for index, screen in enumerate(QApplication.screens()):
            self.source.addItem(f"Screen {index + 1} — {screen.name()}", screen)

    def toggle(self, enabled):
        self.window.db.set_setting("screen_awareness_enabled", enabled)
        if not enabled:
            self.discard()

    def grab(self):
        screen = self.source.currentData()
        if screen is None:
            return self.window.grab()
        if screen not in QApplication.screens():
            raise ValueError("That screen was disconnected. Refresh sources and try again.")
        return screen.grabWindow(0)

    @safe_ui
    def capture(self):
        if not self.enabled.isChecked():
            raise ValueError("Enable the experimental screen feature first.")
        require_access(self.window.db, "screen_capture")
        self.discard()
        self.status.setText("CAPTURING one explicit preview — nothing is being transmitted.")
        shot = self.grab()
        if shot.isNull():
            raise ValueError("Windows did not provide a screenshot. Protected/secure screens are not bypassed.")
        if shot.width() > 1280 or shot.height() > 1280:
            shot = shot.scaled(1280, 1280, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        data = QByteArray()
        buffer = QBuffer(data)
        if not buffer.open(QIODevice.WriteOnly) or not shot.save(buffer, "PNG"):
            raise ValueError("Could not prepare the local screenshot preview.")
        buffer.close()
        if data.size() > MAX_IMAGE_BYTES:
            raise ValueError("Screenshot exceeds the 4 MB bound. Choose a smaller window; nothing was sent.")
        self.image = bytes(data)
        self.preview.setPixmap(shot.scaled(700, 250, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.send_button.setEnabled(True)
        self.status.setText(f"PREVIEW ONLY · {shot.width()} × {shot.height()} · {len(self.image):,} bytes. Inspect every visible detail. Cancel/discard before sending guarantees no request is made.")

    @safe_ui
    def send(self):
        if not self.enabled.isChecked() or not self.image or any(job.isRunning() for job in self.jobs):
            return
        require_access(self.window.db, "screen_capture")
        require_access(self.window.db, "network_actions")
        profile = self.window.providers.manager.active()
        if not profile:
            raise ValueError("Select a vision-capable provider/model in AI Providers first. No screenshot has been sent.")
        profile = validate_profile(profile)
        image, question, generation = self.image, self.question.text(), self.generation
        if QMessageBox.question(self, "Approve this screenshot transmission?", "Send this exact preview and question to " + provider_label(profile) + "\nDestination: " + profile["endpoint"] + "\nModel image support is not yet verified. Check the preview for secrets. No tools or conversation history are included. Once transmission begins, cancellation cannot recall bytes already sent. Proceed?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        # Discarding, disabling or navigating away during the dialog invalidates consent.
        if self.generation != generation or self.image != image or not self.enabled.isChecked() or not self.isVisible():
            return
        for old in self.jobs:
            old.deleteLater()
        self.jobs.clear()

        def operation(cancel, progress):
            require_access(self.window.db, "screen_capture")
            require_access(self.window.db, "network_actions")
            return analyze_image(profile, image, question, cancel, consent=True)

        task = Task(operation, self)
        label = provider_label(profile)
        task.result.connect(lambda value: self.loaded(value, label) if not task.cancel.is_set() and self.generation == generation else None)
        task.failed.connect(self.status.setText)
        task.finished.connect(lambda: self.send_button.setEnabled(bool(self.image) and self.enabled.isChecked() and self.isVisible()))
        self.jobs.append(task)
        self.send_button.setEnabled(False)
        self.status.setText("Transmission approved to the disclosed provider. Explanation only; no tools. Cancel can stop remaining work but cannot recall bytes already transmitted.")
        task.start()

    def loaded(self, value, label):
        self.answer.setPlainText(value)
        self.status.setText("Explanation received from " + label + ". No command was executed. Any further send requires fresh approval.")

    def discard(self):
        self.generation += 1
        for job in self.jobs:
            job.cancel.set()
        self.image = b""
        self.preview.setPixmap(QPixmap())
        self.preview.setText("Preview discarded. Capture again explicitly to make another request.")
        self.send_button.setEnabled(False)
        self.answer.clear()
        self.status.setText("Discarded locally. Queued requests cancelled; an already-approved transmission cannot be recalled.")

    def hideEvent(self, event):
        self.discard()
        super().hideEvent(event)
