"""NEXIS Doctor: explicit checks, bounded worker lifecycle and redacted exports."""

import json

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPlainTextEdit, QFileDialog

from nexis.core import doctor
from nexis.ui import dialogs
from nexis.core.results import Preview, Risk
from nexis.ui.pages import heading, button
from nexis.ui.setup_services import Task, safe_ui


class DoctorPage(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window, self.jobs, self.report = window, [], None
        layout = QVBoxLayout(self)
        heading(layout, "NEXIS DOCTOR", "Local checks run on request. Physical audio, live provider access and clean Windows require separate tests. Exports exclude private content and secrets.")
        row = QHBoxLayout()
        self.run_button = button("Run local checks", self.run_checks, row)
        button("Cancel checks", self.cancel, row)
        self.test_button = button("Test selected provider…", self.test_provider, row)
        layout.addLayout(row)
        self.status = QLabel("NOT TESTED — Run local checks. No microphone, screen or network starts automatically.")
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.PlainText)
        layout.addWidget(self.status)
        self.results = QPlainTextEdit()
        self.results.setReadOnly(True)
        self.results.setAccessibleName("NEXIS Doctor evidence and action required")
        layout.addWidget(self.results, 1)
        row = QHBoxLayout()
        button("Open Voice Studio", lambda: window.open_settings("Voice"), row)
        button("Open AI & Models", lambda: window.open_settings("AI & Models"), row)
        button("Export redacted report…", self.export, row)
        layout.addLayout(row)

    def busy(self):
        return any(job.isRunning() for job in self.jobs)

    @safe_ui
    def run_checks(self):
        if self.busy():
            return
        window = self.window
        workers = (window.voice.worker, window.settings_page.voice_setup.microphone.worker, window.desktop_experience.wake.worker)
        try:
            startup = "PASS" if window.platform.startup_enabled() else "NOT TESTED"
        except OSError:
            startup = "UNAVAILABLE"
        runtime = {"capture_active": any(worker and worker.isRunning() for worker in workers),
                   "windows_voice_count": max(0, window.settings_page.voice_setup.voices.count() - 1),
                   "startup_status": startup}
        profile = window.selected_profile()
        self.start(lambda cancel, progress: doctor.collect(window.db, window.data_dir, cancel, profile=profile, runtime=runtime), self.completed)

    def start(self, function, callback):
        self.status.setText("RUNNING — checks are a snapshot. Cancel retains the last completed report.")
        self.run_button.setEnabled(False)
        self.test_button.setEnabled(False)
        task = Task(function, self)
        task.result.connect(callback)
        task.failed.connect(self.status.setText)
        task.finished.connect(lambda: self.run_button.setEnabled(True))
        task.finished.connect(lambda: self.test_button.setEnabled(True))
        self.jobs.append(task)
        task.start()

    def completed(self, report):
        self.report = report
        self.render()
        self.status.setText("Local checks completed. NOT TESTED and USER ACTION REQUIRED entries remain unverified.")

    def render(self):
        self.results.setPlainText("\n\n".join(f"{row['category'].upper()} / {row['check']}: {row['status']}\n{row['detail']}" for row in self.report["checks"]) + "\n\nNUMERIC METRICS\n" + json.dumps(self.report["metrics"], indent=2))

    def cancel(self):
        for job in self.jobs:
            job.cancel.set()
        self.status.setText("Checks cancelled. A provider request already submitted cannot be recalled; previous results retained.")

    @safe_ui
    def test_provider(self):
        if self.busy():
            return
        if self.report is None:
            raise ValueError("Run local checks first, then test the selected provider.")
        profile = self.window.selected_profile()
        if not profile:
            raise ValueError("Select a valid provider and model in AI & Models first.")
        from nexis.core.providers import endpoint
        from urllib.parse import urlsplit

        destination = urlsplit(endpoint(profile["endpoint"])).hostname
        if not dialogs.confirm(self, Preview("Provider diagnostic", str(destination), "Send one fixed diagnostic sentence to this selected endpoint. No tools, memories or chat history. Provider charges may apply.", Risk.MEDIUM)):
            return
        self.start(lambda cancel, progress: doctor.provider_test(self.window.db, profile, cancel), self.provider_completed)

    def provider_completed(self, row):
        self.report["checks"] = [item for item in self.report["checks"] if item["check"] != "Explicit inference"] + [row]
        self.report["network_requests_in_this_check"] = 1
        self.render()
        self.status.setText("Provider diagnostic finished. Result applies to the selected configuration at test time.")

    @safe_ui
    def export(self):
        if self.report is None:
            raise ValueError("Run checks before exporting a report.")
        path, _ = QFileDialog.getSaveFileName(self, "Export redacted diagnostics", "nexis-doctor.json", "JSON (*.json)")
        if path:
            doctor.export_report(self.report, path, self.window.data_dir)
            self.status.setText("Redacted report exported. Paths, logs, keys, device names, memories and conversation content are excluded.")
