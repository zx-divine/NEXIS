"""Crimson provider manager. Saved API keys are never put back into UI fields."""

import json
from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
    QLineEdit,
    QComboBox,
    QSpinBox,
    QCheckBox,
    QGroupBox,
    QListWidget,
    QMessageBox,
    QPushButton,
)

from nexis.core.providers import DEFAULT_ENDPOINTS, validate_profile
from nexis.core.provider_manager import ProviderManager, models, generate
from nexis.ui.setup_services import Task, safe_ui
from nexis.ui.pages import button, heading


class AIProvidersPage(QWidget):
    profile_saved = Signal()
    changed = Signal()

    def __init__(self, directory, parent=None):
        super().__init__(parent)
        self.manager = ProviderManager(directory)
        self.jobs = []
        self.saved = None
        self.current_id = None
        layout = QVBoxLayout(self)
        heading(
            layout,
            "AI PROVIDERS",
            "Choose where your requests go. NEXIS never switches providers automatically.",
        )
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.PlainText)
        self.profiles = QListWidget()
        self.profiles.setMaximumHeight(115)
        self.profiles.currentRowChanged.connect(self.load_selected)
        layout.addWidget(self.profiles)
        row = QHBoxLayout()
        button("Add provider", self.new_profile, row)
        button("Use selected provider", self.select_default, row)
        button("Remove selected provider", self.remove, row)
        layout.addLayout(row)
        form = QFormLayout()
        self.provider = QComboBox()
        self.provider.addItems(DEFAULT_ENDPOINTS)
        self.provider.currentTextChanged.connect(self.type_changed)
        self.display_name = QLineEdit()
        self.address = QLineEdit()
        self.key = QLineEdit()
        self.key.setEchoMode(QLineEdit.Password)
        self.key.setPlaceholderText("API key or token — encrypted by Windows")
        self.model = QComboBox()
        self.model.setEditable(True)
        self.model.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.model.setMinimumContentsLength(18)
        self.model.setInsertPolicy(QComboBox.NoInsert)
        form.addRow("Provider adapter", self.provider)
        form.addRow("Display name", self.display_name)
        form.addRow("Base URL", self.address)
        form.addRow("API key / token", self.key)
        form.addRow("Default model", self.model)
        layout.addLayout(form)
        self.advanced = QGroupBox("Advanced API options")
        self.advanced.setCheckable(True)
        self.advanced.setChecked(False)
        advanced = QFormLayout(self.advanced)
        self.protocol = QComboBox()
        self.protocol.addItems(["openai", "gemini"])
        self.api_path = QLineEdit("/chat/completions")
        self.models_path = QLineEdit("/models")
        self.auth = QComboBox()
        self.auth.addItems(["Bearer", "api-key", "Custom header", "None"])
        self.auth_header = QLineEdit("X-API-Key")
        self.headers = QLineEdit()
        self.headers.setEchoMode(QLineEdit.Password)
        self.headers.setPlaceholderText("Optional headers JSON; saved values stay hidden")
        self.timeout = QSpinBox()
        self.timeout.setRange(5, 120)
        self.timeout.setValue(20)
        self.streaming = QCheckBox("Stream responses (when supported by this provider)")
        self.native_tools = QCheckBox("Native function/tool calling (when supported)")
        for label, widget in (
            ("Protocol adapter", self.protocol),
            ("Chat API path", self.api_path),
            ("Models API path", self.models_path),
            ("Authentication", self.auth),
            ("Custom auth header", self.auth_header),
            ("Custom headers JSON", self.headers),
            ("Timeout (seconds)", self.timeout),
        ):
            advanced.addRow(label, widget)
        advanced.addRow(self.streaming)
        advanced.addRow(self.native_tools)
        layout.addWidget(self.advanced)
        self.advanced.toggled.connect(self.toggle_advanced)
        self.toggle_advanced(False)
        row = QHBoxLayout()
        self.refresh_button = button("Refresh models", self.refresh_models, row)
        self.test_button = button("Test connection / inference", self.test, row)
        layout.addLayout(row)
        row = QHBoxLayout()
        self.save_button = button("Save provider", self.save, row)
        button("Save & use as default", self.save_and_select, row)
        button("Cancel request", self.cancel_jobs, row)
        layout.addLayout(row)
        button("Open OmniRoute dashboard", self.open_gateway, layout)
        notice = QLabel(
            "Keys and custom credentials are encrypted for your Windows account and are never displayed after saving. Refresh/Test sends a request only to the shown configuration. Model availability does not imply free usage. Native Gemini uses Google's official SDK; gateways must implement the selected supported protocol. Audio stays local; request text and authorized tool context may be sent to the selected provider."
        )
        notice.setWordWrap(True)
        layout.addWidget(notice)
        layout.addWidget(self.status)
        self.reload_saved()

    def toggle_advanced(self, checked):
        for child in self.advanced.findChildren(QWidget):
            child.setVisible(checked)

    @safe_ui
    def reload_saved(self):
        data = self.manager.read()
        self.profile_rows = data["profiles"]
        self.profiles.blockSignals(True)
        self.profiles.clear()
        selected = -1
        for i, profile in enumerate(self.profile_rows):
            active = profile["id"] == data["default_id"]
            self.profiles.addItem(
                ("DEFAULT · " if active else "")
                + profile["display_name"]
                + " / "
                + (profile["model"] or "model not selected")
            )
            if profile["id"] == (self.current_id or data["default_id"]):
                selected = i
        self.profiles.setCurrentRow(selected)
        self.profiles.blockSignals(False)
        if selected >= 0:
            self.load_selected(selected)
        else:
            self.new_profile()

    def new_profile(self):
        if any(j.isRunning() for j in self.jobs):
            self.status.setText("Cancel or finish the active provider request first.")
            return
        self.current_id, self.saved = None, None
        self.profiles.setCurrentRow(-1)
        self.provider.setCurrentText("OpenRouter")
        self.type_changed(self.provider.currentText())
        self.status.setText("New configuration. Save it, then explicitly choose it as default.")

    def type_changed(self, provider):
        self.key.clear()
        self.headers.clear()
        self.address.setText(DEFAULT_ENDPOINTS.get(provider, ""))
        self.display_name.setText(provider)
        self.model.clear()
        self.protocol.setCurrentText("gemini" if provider == "Google Gemini" else "openai")
        self.native_tools.setChecked(provider == "Google Gemini")
        self.auth.setCurrentText("api-key" if provider == "Google Gemini" else "Bearer")
        if provider in {"OpenAI-compatible", "Custom API Gateway", "Compatible gateway"}:
            self.advanced.setChecked(True)

    def load_selected(self, index):
        if index < 0 or index >= len(getattr(self, "profile_rows", [])):
            return
        if any(j.isRunning() for j in self.jobs):
            self.status.setText(
                "Wait for the provider request to finish before editing another configuration."
            )
            return
        self.saved = self.profile_rows[index]
        self.current_id = self.saved["id"]
        if self.provider.findText(self.saved["provider"]) < 0:
            self.provider.addItem(self.saved["provider"])
        self.provider.setCurrentText(self.saved["provider"])
        self.display_name.setText(self.saved["display_name"])
        self.address.setText(self.saved["endpoint"])
        self.model.setCurrentText(self.saved["model"])
        self.auth.setCurrentText(self.saved["auth"])
        self.auth_header.setText(self.saved["auth_header"])
        self.protocol.setCurrentText(self.saved["protocol"])
        self.api_path.setText(self.saved["api_path"])
        self.models_path.setText(self.saved["models_path"])
        self.timeout.setValue(self.saved["timeout"])
        self.streaming.setChecked(self.saved["stream"])
        self.native_tools.setChecked(self.saved["native_tools"])
        self.key.clear()
        self.headers.clear()
        self.key.setPlaceholderText("Saved key retained — leave blank to reuse this destination")
        self.headers.setPlaceholderText(
            "Saved headers hidden — leave blank to retain this destination"
        )
        self.status.setText(
            "Saved configuration loaded securely. Complete saved keys are not displayed."
        )

    def profile(self):
        binding = (
            self.address.text().strip().rstrip("/"),
            self.protocol.currentText(),
            self.auth.currentText(),
            self.auth_header.text().strip(),
            self.api_path.text().strip(),
        )
        reuse = self.saved and binding == (
            self.saved["endpoint"],
            self.saved["protocol"],
            self.saved["auth"],
            self.saved["auth_header"],
            self.saved["api_path"],
        )
        try:
            headers = (
                json.loads(self.headers.text())
                if self.headers.text()
                else (self.saved["headers"] if reuse else {})
            )
        except ValueError:
            raise ValueError("Custom headers must be a JSON object.") from None
        return validate_profile(
            {
                "provider": self.provider.currentText(),
                "display_name": self.display_name.text(),
                "endpoint": self.address.text().strip(),
                "key": self.key.text() or (self.saved["key"] if reuse else ""),
                "model": self.model.currentText().strip(),
                "protocol": self.protocol.currentText(),
                "auth": self.auth.currentText(),
                "auth_header": self.auth_header.text().strip(),
                "headers": headers,
                "api_path": self.api_path.text().strip(),
                "models_path": self.models_path.text().strip(),
                "timeout": self.timeout.value(),
                "stream": self.streaming.isChecked(),
                "native_tools": self.native_tools.isChecked(),
            }
        )

    @safe_ui
    def save(self):
        if any(j.isRunning() for j in self.jobs):
            raise ValueError("Wait for the current provider request to finish.")
        profile = self.profile()
        if not profile["model"]:
            raise ValueError(
                "Choose a model from Refresh models or enter a supported model identifier."
            )
        self.current_id = self.manager.save(profile, self.current_id)
        self.reload_saved()
        self.status.setText("Saved securely. Choose Use selected provider to change the default.")
        self.profile_saved.emit()
        return True

    def approve_switch(self):
        return (
            QMessageBox.question(
                self,
                "Use this provider?",
                "Future requests, retry prompts and any retained conversation/tool context will be sent to this selected configuration. NEXIS will not switch automatically. Continue?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            == QMessageBox.Yes
        )

    @safe_ui
    def save_and_select(self):
        if not self.approve_switch():
            return
        saved = self.save()
        if saved and self.current_id:
            self.manager.select(self.current_id)
            self.reload_saved()
            self.changed.emit()
            self.status.setText(
                "Selected default provider saved. Retry your retained prompt when ready."
            )

    @safe_ui
    def select_default(self):
        if not self.current_id or not self.approve_switch():
            return
        self.manager.select(self.current_id)
        self.reload_saved()
        self.changed.emit()
        self.status.setText(
            "Default provider changed explicitly. Existing prompts remain available for Retry."
        )

    @safe_ui
    def remove(self):
        if not self.current_id:
            return
        if (
            QMessageBox.question(
                self,
                "Remove provider?",
                "Remove this saved configuration? If it is the default, NEXIS will require you to select another one; it will not switch automatically.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            != QMessageBox.Yes
        ):
            return
        self.manager.remove(self.current_id)
        self.current_id = None
        self.reload_saved()
        self.changed.emit()

    def cancel_jobs(self):
        for task in self.jobs:
            task.cancel.set()
        self.status.setText(
            "Cancelling the provider request. Any current network read is bounded by its timeout."
        )

    @safe_ui
    def open_gateway(self):
        from urllib.parse import urlsplit, urlunsplit
        import webbrowser

        profile = self.profile()
        if profile["provider"] != "OmniRoute":
            raise ValueError("Select an OmniRoute configuration to open its dashboard.")
        address = urlsplit(profile["endpoint"])
        root = urlunsplit((address.scheme, address.netloc, "/", "", ""))
        if not webbrowser.open(root, new=2):
            raise ValueError("The default browser did not accept the dashboard request.")
        self.status.setText(
            "Dashboard launch requested. Configure the upstream account/model yourself in OmniRoute, then Retry in NEXIS. No credentials were entered automatically."
        )

    @safe_ui
    def refresh_models(self):
        self.start_task(lambda profile, cancel: models(profile, cancel), self.models_loaded)

    def models_loaded(self, entries):
        selected = self.model.currentText()
        self.model.clear()
        self.model.addItems(entries)
        if selected:
            self.model.setCurrentText(selected)
        self.status.setText(
            str(len(entries))
            + " model(s) available to this key. Pricing/quota depends on the provider; live inference is a separate test."
        )

    @safe_ui
    def test(self):
        self.start_task(
            lambda profile, cancel: generate(
                profile,
                [{"role": "user", "content": "Reply with exactly: NEXIS provider test OK."}],
                cancel,
            ),
            lambda value: self.status.setText("Real inference succeeded: " + value["text"]),
        )

    def start_task(self, operation, callback):
        if any(j.isRunning() for j in self.jobs):
            return
        profile = self.profile()
        self.status.setText("Contacting only the shown provider configuration…")
        task = Task(lambda cancel, progress: operation(profile, cancel), self)
        task.result.connect(callback)
        task.failed.connect(self.status.setText)
        task.finished.connect(self.task_finished)
        self.jobs.append(task)
        self.set_busy(True)
        task.start()

    def task_finished(self):
        self.set_busy(False)

    def set_busy(self, busy):
        for widget in self.findChildren(QWidget):
            if isinstance(
                widget, (QLineEdit, QComboBox, QSpinBox, QCheckBox, QListWidget, QPushButton)
            ):
                widget.setEnabled(
                    not busy
                    or isinstance(widget, QPushButton)
                    and widget.text() == "Cancel request"
                )
