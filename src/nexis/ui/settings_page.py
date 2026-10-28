from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QLineEdit,
    QFileDialog,
    QFormLayout,
    QLabel,
    QListWidget,
    QSpinBox,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
)

from nexis.core.management import Management
from nexis.core.permissions import Permissions
from nexis.ui import dialogs
from nexis.ui.pages import button, heading
from nexis.ui.setup_services import VoiceSetupPanel
from nexis.ui.system_access import SystemAccessPanel
from nexis.ui.launch_page import ModuleNavigation
from nexis.core.profile import LAUNCH_MODES, preferred_name


class SettingsPage(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window = window
        layout = QVBoxLayout(self)
        heading(
            layout,
            "Settings",
            "Make NEXIS yours. Save General preferences; device and permission changes take effect immediately.",
        )
        body = QHBoxLayout()
        self.categories = ModuleNavigation()
        self.categories.setFixedWidth(180)
        self.categories.setAccessibleName("Settings category")
        body.addWidget(self.categories)
        self.sections = QStackedWidget()
        self.section_indices = {}
        body.addWidget(self.sections, 1)
        layout.addLayout(body, 1)

        def section(title):
            body = QWidget()
            content = QVBoxLayout(body)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(body)
            self.section_indices[title] = self.sections.addWidget(scroll)
            self.categories.addItem(title)
            return content

        general = section("General")
        form = QFormLayout()
        self.preferred_name = QLineEdit(window.db.setting("preferred_name"))
        self.preferred_name.setMaxLength(80)
        self.preferred_name.setAccessibleName("Preferred user name")
        self.preferred_name.setPlaceholderText("What should NEXIS call you?")
        form.addRow("Preferred name", self.preferred_name)
        self.launch_mode = QComboBox()
        self.launch_mode.setAccessibleName("Default launch mode")
        for key, title in LAUNCH_MODES.items():
            self.launch_mode.addItem(title, key)
        self.launch_mode.setCurrentIndex(self.launch_mode.findData(window.db.setting("default_launch_mode")))
        form.addRow("Default launch mode", self.launch_mode)
        from nexis.platform.hotkeys import HOTKEYS

        self.launcher_enabled = QCheckBox("Enable global command launcher")
        self.launcher_enabled.setChecked(window.db.setting("global_launcher_enabled"))
        form.addRow(self.launcher_enabled)
        self.launcher_hotkey = QComboBox()
        self.launcher_hotkey.addItems(HOTKEYS)
        self.launcher_hotkey.setCurrentText(window.db.setting("global_launcher_hotkey"))
        self.launcher_hotkey.setAccessibleName("Global command-launcher shortcut")
        form.addRow("Command launcher shortcut", self.launcher_hotkey)
        self.launcher_status = QLabel("Registration is checked when NEXIS starts its services or when you save. Conflicts keep Ctrl+K available inside the app.")
        self.launcher_status.setWordWrap(True)
        form.addRow(self.launcher_status)
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
        self.minimize_to_tray = QCheckBox("Minimize to tray when Always Active and Windows tray are available")
        self.minimize_to_tray.setChecked(window.db.setting("minimize_to_tray"))
        form.addRow(self.minimize_to_tray)
        general.addLayout(form)
        button("Save general preferences", self.save, general)
        button("Always Active controls", lambda: window.navigate("Desktop Companion"), general)
        button("Update preferences", lambda: window.navigate("Updates"), general)
        general.addStretch()

        voice = section("Voice")
        self.voice_setup = VoiceSetupPanel(window)
        voice.addWidget(self.voice_setup)
        button("Hard Mute / Wake", window.toggle_microphone_mute, voice)
        voice.addStretch()

        ai = section("AI Providers")
        label = QLabel("Manage encrypted provider profiles, base URLs, model discovery, connection tests, timeouts and streaming in the provider editor. Saved configuration does not prove a live connection.")
        label.setWordWrap(True)
        ai.addWidget(label)
        button("Manage AI providers and models", lambda: window.navigate("AI Providers"), ai)
        ai.addStretch()

        automation = section("Advanced")
        label = QLabel("Workflows use allowed commands, action previews, dry-run validation, explicit save/run, pause and cancellation. Scheduling is not available. The browser adapter below is optional and never enabled automatically.")
        label.setWordWrap(True)
        automation.addWidget(label)
        button("Open Workflow Studio", lambda: window.navigate("Workflows"), automation)
        self.browser_port = QSpinBox()
        self.browser_port.setRange(0, 65535)
        self.browser_port.setValue(window.db.setting("browser_adapter_port"))
        browser_form = QFormLayout()
        browser_form.addRow("Existing browser adapter port (0 disables)", self.browser_port)
        automation.addLayout(browser_form)
        button("Save automation preferences", self.save, automation)
        automation.addStretch()

        privacy = section("Permissions")
        self.access = SystemAccessPanel(window.db)
        self.access.revoked.connect(self.access_changed)
        privacy.addWidget(self.access)
        privacy.addWidget(QLabel("Approved search folders (none approved automatically)"))
        self.roots = QListWidget()
        self.refresh_roots()
        privacy.addWidget(self.roots)
        button("Approve folder…", self.add_root, privacy)
        button("Remove selected folder", self.remove_root, privacy)
        button(
            "Manage applications and website shortcuts",
            lambda: window.navigate("Applications"),
            privacy,
        )
        button("Screen Awareness permissions and preview", lambda: window.navigate("Screen Awareness"), privacy)
        privacy.addStretch()

        memory = section("Memory and Privacy")
        note = QLabel("Memory is saved only when you approve it. Provider credentials use Windows account protection. Exports contain personal data; review where you save them.")
        note.setWordWrap(True)
        memory.addWidget(note)
        button("Review, edit, export or delete memories", lambda: window.navigate("Local Memory"), memory)
        button("Manage history", lambda: window.navigate("History"), memory)
        button("Search saved conversations", lambda: window.navigate("Saved Conversations"), memory)
        button("Export settings & saved resources…", self.export, memory)
        button("Delete all local data…", self.delete, memory)
        memory.addStretch()

        desktop = section("Appearance")
        from nexis.ui.appearance import AppearancePanel

        self.appearance = AppearancePanel(window)
        self.theme = self.appearance.theme
        desktop.addWidget(self.appearance)
        label = QLabel("Motion and animation rate are in General. Always Active provides the floating orb, tray controls and opt-in local Hey NEXIS phrase listening. Check its microphone status before speaking.")
        label.setWordWrap(True)
        desktop.addWidget(label)
        button("Open desktop / Always Active controls", lambda: window.navigate("Desktop Companion"), desktop)
        desktop.addStretch()

        diagnostics = automation
        button("Open NEXIS Doctor", lambda: window.navigate("NEXIS Doctor"), diagnostics)
        button("Microphone / speaker tests", lambda: self.open_section("Voice"), diagnostics)
        button("Provider diagnostic test", lambda: window.navigate("NEXIS Doctor"), diagnostics)
        about = automation
        button("Version, creator, licensing and project information", lambda: window.navigate("About"), about)
        button("Update status", lambda: window.navigate("Updates"), about)
        about.addStretch()
        integrations = section("Integrations")
        note = QLabel("Calendar, email, messaging, smart home, media accounts and cross-device sync are not connected in this build. Their authenticated adapters are pending implementation. Local commands and provider settings remain available. No account access is implied by this page.")
        note.setWordWrap(True)
        integrations.addWidget(note)
        integrations.addStretch()
        # Display the product's eight categories in a predictable order.
        order = ("General", "AI Providers", "Voice", "Appearance", "Permissions", "Memory and Privacy", "Integrations", "Advanced")
        self.categories.clear()
        self.categories.addItems(order)
        self.category_order = order
        self.status = QLabel("")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.provider = window.providers
        self.categories.currentTextChanged.connect(lambda name: self.sections.setCurrentIndex(self.section_indices[name]) if name in self.section_indices else None)
        self.sections.currentChanged.connect(self.section_changed)
        self.categories.setCurrentRow(0)

    def open_section(self, name):
        name = {"AI & Models": "AI Providers", "Automation": "Advanced", "Permissions & Privacy": "Permissions", "Desktop & Appearance": "Appearance", "Diagnostics": "Advanced", "About": "Advanced"}.get(name, name)
        if name in self.section_indices:
            self.categories.setCurrentText(name)

    def reload_profile(self):
        self.preferred_name.setText(self.window.db.setting("preferred_name"))
        self.launch_mode.setCurrentIndex(self.launch_mode.findData(self.window.db.setting("default_launch_mode")))

    def section_changed(self, index):
        if index != self.section_indices["Voice"]:
            self.voice_setup.microphone.stop()
            self.voice_setup.stop_speech()

    def save(self):
        db = self.window.db
        name = self.preferred_name.text().strip()
        if name:
            name = preferred_name(name)
        desired = self.startup.isChecked()
        if self.startup.isEnabled() and desired != self.window.platform.startup_enabled():
            try:
                self.management().startup(desired)
            except ValueError:
                self.startup.setChecked(not desired)
                raise
        values = {
            "browser_adapter_port": self.browser_port.value(),
            "reduced_motion": self.reduced.isChecked(),
            "animation_fps": self.fps.value(),
            "start_maximized": self.maximized.isChecked(),
            "start_minimised": self.minimised.isChecked(),
            "history_enabled": self.history.isChecked(),
            "history_limit": self.limit.value(),
            "confirm_low_risk": self.confirm.isChecked(),
            "minimize_to_tray": self.minimize_to_tray.isChecked(),
            "default_launch_mode": self.launch_mode.currentData(),
            "global_launcher_enabled": self.launcher_enabled.isChecked(),
            "global_launcher_hotkey": self.launcher_hotkey.currentText(),
        }
        if name:
            values["preferred_name"] = name
        for key, value in values.items():
            db.set_setting(key, value)
        self.window.apply_theme()
        self.window.welcome.refresh()
        self.window.configure_launcher()
        self.status.setText("Preferences saved.")

    def access_changed(self):
        self.window.desktop_experience.wake.pause()
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
            self.status.setText("Export saved. It contains personal data. Memory has its own export; indexed document contents are excluded.")

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
        self.window.desktop_experience.enabled.setChecked(False)
        self.window.desktop_experience.cleanup()
        self.window.updates_page.automatic.setChecked(False)
        self.window.workflow_studio.enabled.setChecked(False)
        self.window.workflow_studio.steps.clear()
        self.window.workflow_studio.prompt.clear()
        self.window.workflow_studio.title.clear()
        self.window.screen_awareness.enabled.setChecked(False)
        self.window.screen_awareness.discard()
        self.window.memories.new()
        self.window.memories.enabled.setChecked(self.window.db.setting("memory_enabled"))
        self.window.memories.query.clear()
        self.window.memories.refresh()
        self.window.files.results.clear()
        self.window.files.result_metadata.clear()
        self.window.files.metadata.clear()
        self.window.chat.clear_conversation()
        self.window.saved_conversations.query.clear()
        self.window.saved_conversations.refresh()
        self.window.voice.transcript.clear()
        self.window.voice.response.clear()
        self.window.voice.pending_transcript = ""
        self.window.voice.metrics = {}
        self.window.refresh_provider_identity()
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
        self.reload_profile()
        self.window.update_mute_label()
        self.launcher_enabled.setChecked(self.window.db.setting("global_launcher_enabled"))
        self.launcher_hotkey.setCurrentText(self.window.db.setting("global_launcher_hotkey"))
        self.window.configure_launcher()
        self.window.discovery.refresh()
        self.voice_setup.tts_enabled.setChecked(self.window.db.setting("tts_enabled"))
        self.voice_setup.voices.setCurrentIndex(0)
        self.voice_setup.input.setCurrentIndex(0)
        self.window.voice.refresh_setup()
        self.refresh_roots()
        self.appearance.revert()
        self.minimised.setChecked(False)
        self.minimize_to_tray.setChecked(False)
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
