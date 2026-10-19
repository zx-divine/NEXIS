from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QLabel,
    QListWidget,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from nexis.core.management import Management
from nexis.core.permissions import Permissions
from nexis.ui import dialogs
from nexis.ui.pages import button, heading
from nexis.ui.setup_services import VoiceSetupPanel
from nexis.ui.system_access import SystemAccessPanel


class SettingsPage(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window = window
        layout = QVBoxLayout(self)
        heading(
            layout,
            "Settings",
            "Local preferences. Changes are saved when you select Save preferences.",
        )
        form = QFormLayout()
        self.theme = QComboBox()
        self.theme.addItems(["dark", "light"])
        self.theme.setCurrentText(window.db.setting("theme"))
        form.addRow("Theme", self.theme)
        self.minimised = QCheckBox("Start minimised")
        self.minimised.setChecked(window.db.setting("start_minimised"))
        form.addRow(self.minimised)
        self.maximized = QCheckBox("Start maximized (F11 toggles full screen)")
        self.maximized.setChecked(window.db.setting("start_maximized"))
        form.addRow(self.maximized)
        self.reduced = QCheckBox("Reduced motion — stop reactor and activity animations")
        self.reduced.setChecked(window.db.setting("reduced_motion"))
        form.addRow(self.reduced)
        self.fps = QSpinBox()
        self.fps.setRange(10, 30)
        self.fps.setValue(window.db.setting("animation_fps"))
        form.addRow("Active animation FPS target", self.fps)
        self.history = QCheckBox("Record command history")
        self.history.setChecked(window.db.setting("history_enabled"))
        form.addRow(self.history)
        self.limit = QSpinBox()
        self.limit.setRange(1, 10000)
        self.limit.setValue(window.db.setting("history_limit"))
        form.addRow("History retention (entries)", self.limit)
        self.confirm = QCheckBox("Also confirm low-risk actions")
        self.confirm.setChecked(window.db.setting("confirm_low_risk"))
        form.addRow(self.confirm)
        self.startup = QCheckBox("Launch at Windows sign-in")
        try:
            self.startup.setChecked(window.platform.startup_enabled())
        except OSError:
            self.startup.setEnabled(False)
            self.startup.setToolTip("Windows startup registration unavailable.")
        form.addRow(self.startup)
        layout.addLayout(form)
        button("Save preferences", self.save, layout)
        layout.addWidget(QLabel("Approved search folders (no folders are approved automatically)"))
        self.roots = QListWidget()
        self.refresh_roots()
        layout.addWidget(self.roots)
        button("Approve folder…", self.add_root, layout)
        button("Remove selected folder", self.remove_root, layout)
        button(
            "Manage applications and website shortcuts",
            lambda: window.navigate("Applications"),
            layout,
        )
        button("Export all local data…", self.export, layout)
        button("Delete all local data…", self.delete, layout)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.provider = window.providers
        button("Manage AI providers", lambda: window.navigate("AI Providers"), layout)
        self.access = SystemAccessPanel(window.db)
        self.access.revoked.connect(self.access_changed)
        layout.insertWidget(2, self.access)
        self.browser_port = QSpinBox()
        self.browser_port.setRange(0, 65535)
        self.browser_port.setValue(window.db.setting("browser_adapter_port"))
        form.addRow(
            "Existing browser adapter port (0 disables; NEXIS never enables debugging)",
            self.browser_port,
        )
        self.voice_setup = VoiceSetupPanel(window)
        layout.insertWidget(3, self.voice_setup)

    def save(self):
        db = self.window.db
        desired = self.startup.isChecked()
        if self.startup.isEnabled() and desired != self.window.platform.startup_enabled():
            try:
                self.management().startup(desired)
            except ValueError:
                self.startup.setChecked(not desired)
                raise
        values = {
            "browser_adapter_port": self.browser_port.value(),
            "theme": self.theme.currentText(),
            "reduced_motion": self.reduced.isChecked(),
            "animation_fps": self.fps.value(),
            "start_maximized": self.maximized.isChecked(),
            "start_minimised": self.minimised.isChecked(),
            "history_enabled": self.history.isChecked(),
            "history_limit": self.limit.value(),
            "confirm_low_risk": self.confirm.isChecked(),
        }
        for key, value in values.items():
            db.set_setting(key, value)
        self.window.apply_theme()
        self.status.setText("Preferences saved.")

    def access_changed(self):
        self.window.voice.stop()
        for job in self.window.ai_jobs:
            job.cancel.set()
            if hasattr(job, "respond"):
                job.respond(False)
        self.window.stop_command()

    def refresh_roots(self):
        self.roots.clear()
        self.roots.addItems(self.window.db.setting("search_roots"))

    def add_root(self):
        path = QFileDialog.getExistingDirectory(self, "Approve search folder")
        if not path:
            return
        self.management().approve_folder(path)
        self.refresh_roots()

    def remove_root(self):
        item = self.roots.currentItem()
        if item:
            self.window.db.set_setting(
                "search_roots",
                [p for p in self.window.db.setting("search_roots") if p != item.text()],
            )
            self.refresh_roots()

    def export(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export local data", "nexis-export.json", "JSON (*.json)"
        )
        if path:
            self.management().export(path)
            self.status.setText("Export saved. It contains personal data.")

    def delete(self):
        if any(
            job and job.isRunning()
            for job in self.window.background_jobs()
            if job is not self.voice_setup.speech
        ):
            raise ValueError(
                "Stop active commands, voice, downloads and AI requests before deleting local data."
            )
        self.voice_setup.stop_speech()
        if self.window.files.worker and self.window.files.worker.isRunning():
            raise ValueError("Cancel file search and wait for it to finish before deleting data.")
        self.management().delete_all()
        self.provider.cancel_jobs()
        self.provider.manager.path.unlink(missing_ok=True)
        self.provider.manager.legacy.delete()
        self.provider.current_id = None
        self.provider.reload_saved()
        # Close log handlers before removing local logs.
        import logging

        logger = logging.getLogger("nexis")
        for handler in logger.handlers[:]:
            handler.close()
            logger.removeHandler(handler)
        for path in self.window.data_dir.glob("nexis.log*"):
            path.unlink(missing_ok=True)
        from nexis.utils.logging import configure

        configure(self.window.data_dir)
        self.window.refresh()
        self.window.discovery.refresh()
        self.voice_setup.tts_enabled.setChecked(self.window.db.setting("tts_enabled"))
        self.voice_setup.voices.setCurrentIndex(0)
        self.voice_setup.input.setCurrentIndex(0)
        self.window.voice.refresh_setup()
        self.refresh_roots()
        self.theme.setCurrentText("dark")
        self.minimised.setChecked(False)
        self.maximized.setChecked(True)
        self.reduced.setChecked(False)
        self.fps.setValue(30)
        self.history.setChecked(True)
        self.limit.setValue(500)
        self.confirm.setChecked(False)
        self.startup.setChecked(False)
        self.window.apply_theme()
        self.status.setText(
            "Local data deleted. External exports and backups are outside NEXIS control."
        )

    def management(self):
        return Management(
            self.window.db,
            self.window.platform,
            Permissions(lambda preview: dialogs.confirm(self, preview)),
        )
