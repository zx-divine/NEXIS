"""Explicit experimental drafting panel; generated text never executes itself."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPlainTextEdit, QLabel,
    QCheckBox, QMessageBox,
)

from nexis.core.workflow_drafts import draft_workflow, dry_run
from nexis.core.results import Preview, Risk
from nexis.ui import dialogs
from nexis.ui.pages import button
from nexis.ui.setup_services import Task, safe_ui


class WorkflowStudio(QWidget):
    def __init__(self, window, resource):
        super().__init__()
        self.window, self.resource, self.jobs = window, resource, []
        layout = QVBoxLayout(self)
        self.enabled = QCheckBox("Enable experimental AI workflow drafting")
        self.enabled.setChecked(window.db.setting("workflow_drafting_enabled"))
        self.enabled.toggled.connect(self.toggle)
        layout.addWidget(self.enabled)
        self.prompt = QLineEdit()
        self.prompt.setMaxLength(1000)
        self.prompt.setPlaceholderText("Describe a routine. Only this text goes to the selected provider; include required names yourself.")
        self.prompt.setAccessibleName("Natural language workflow description")
        layout.addWidget(self.prompt)
        row = QHBoxLayout()
        self.generate_button = button("Draft with selected AI", self.generate, row)
        button("Cancel drafting", self.cancel, row)
        layout.addLayout(row)
        self.title = QLineEdit()
        self.title.setPlaceholderText("Routine name")
        self.title.setAccessibleName("Saved workflow name")
        layout.addWidget(self.title)
        self.steps = QPlainTextEdit()
        self.steps.setPlaceholderText("Editable preview, one command per line: open … / folder … / copy …")
        self.steps.setAccessibleName("Editable workflow draft")
        self.steps.setMaximumHeight(120)
        layout.addWidget(self.steps)
        row = QHBoxLayout()
        button("Dry-run validation (no execution)", self.preview, row)
        button("Save reviewed routine", self.save, row)
        layout.addLayout(row)
        self.status = QLabel("AI drafting is optional and off by default. Manual editing/dry-run works locally. Save does not execute. Run a saved routine with the existing Run button; pause/resume/stop are in the Manual Command Deck. Pausing occurs between steps, and does not undo completed actions.")
        self.status.setTextFormat(Qt.PlainText)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.generate_button.setEnabled(self.enabled.isChecked())

    def toggle(self, enabled):
        self.window.db.set_setting("workflow_drafting_enabled", enabled)
        self.generate_button.setEnabled(enabled)
        if not enabled:
            self.cancel()

    def cancel(self):
        for job in self.jobs:
            job.cancel.set()

    @safe_ui
    def generate(self):
        if not self.enabled.isChecked() or any(job.isRunning() for job in self.jobs):
            return
        profile = self.window.providers.manager.active()
        if not profile:
            raise ValueError("Select a provider in AI Providers first. The draft text is retained.")
        prompt = self.prompt.text()
        for old in self.jobs:
            old.deleteLater()
        self.jobs.clear()
        task = Task(lambda cancel, progress: draft_workflow(self.window.db, profile, prompt, cancel), self)
        task.result.connect(lambda commands: self.loaded(commands) if not task.cancel.is_set() else None)
        task.failed.connect(self.status.setText)
        self.jobs.append(task)
        self.status.setText("Drafting only with the selected configuration; no commands will execute.")
        task.start()

    def loaded(self, commands):
        self.steps.setPlainText("\n".join(commands))
        self.status.setText("Draft ready. Check every step, run Dry-run validation, then explicitly save. Nothing has executed.")

    @safe_ui
    def preview(self):
        rows = dry_run(self.window.db, self.steps.toPlainText(), self.window.platform)
        text = "NO EXECUTION. Availability is checked now; grants and targets are checked again when run.\n\n"
        text += "\n\n".join(f"{index}. {row['command']}\n{row['risk']} · {row['effect']}\n{row['target']}" for index, row in enumerate(rows, 1))
        QMessageBox.information(self, "Workflow dry-run", text)
        self.status.setText("Dry-run validation passed. No application was launched, file changed or clipboard written.")

    @safe_ui
    def save(self):
        rows = dry_run(self.window.db, self.steps.toPlainText(), self.window.platform)
        title = self.title.text()
        if self.window.db.rows("SELECT name FROM workflows WHERE name=?", (title.strip().lower(),)):
            if not dialogs.confirm(self.window, Preview("Replace routine", title, "Overwrite this existing saved routine; no step executes now.", Risk.HIGH)):
                return
        self.window.repo.save_workflow(title, [row["command"] for row in rows])
        self.resource.refresh()
        self.status.setText("Routine saved locally. Select it and press Run when ready; execution rechecks permissions and stops on failure.")
