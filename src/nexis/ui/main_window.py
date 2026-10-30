import json
import re
from datetime import datetime
from pathlib import Path
from time import perf_counter

from PySide6.QtCore import QEvent, QTimer, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QInputDialog,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from nexis import __version__, DISPLAY_VERSION
from nexis.branding import application_icon
from nexis.ui.branding import BrandLogo
from nexis.core.commands import REGISTRY
from nexis.platform.system import SystemSampler
from nexis.platform.windows import Windows
from nexis.storage.repository import Repository
from nexis.ui import dialogs
from nexis.ui.conversation import ChatPage, VoicePage
from nexis.ui.command_deck import CommandDeck
from nexis.ui.hud_widgets import HUDPanel, RadarWidget, SegmentedMeter, SystemGraph
from nexis.ui.pages import FilesPage, HistoryPage, ResourcePage, button, heading
from nexis.ui.reactor import ReactorState, ReactorWidget
from nexis.ui.settings_page import SettingsPage
from nexis.ui.workers import CommandWorker
from nexis.ui.setup_services import DiscoveryPanel, start_chat, safe_ui
from nexis.core.models import detect_model
from nexis.ui.providers_page import AIProvidersPage
from nexis.core.privacy import sanitize_request
from nexis.core.identity import is_identity_question, identity_reply, provider_label
from nexis.ui.memory_page import MemoryPage
from nexis.ui.health_page import HealthPage
from nexis.ui.workflow_studio import WorkflowStudio
from nexis.ui.screen_page import ScreenPage
from nexis.ui.desktop_page import DesktopPage
from nexis.ui.updates_page import UpdatesPage, SoftwareUpdatesPanel
from nexis.ui.doctor_page import DoctorPage
from nexis.ui.launch_page import ModuleNavigation, WelcomePage


class MainWindow(QMainWindow):
    def __init__(self, db, data_dir, platform=None, sampler=None):
        super().__init__()
        self.setWindowIcon(application_icon())
        started = perf_counter()
        self.db, self.data_dir = db, Path(data_dir)
        self.ai_jobs = []
        self.ai_origin = "chat"
        self.current_ai = None
        self.conversation_history = []
        self.closing = False
        self.microphone_muted = db.setting("microphone_muted")
        self.global_launcher = None
        self.platform = platform or Windows()
        self.sampler = sampler or SystemSampler()
        self.repo = Repository(db)
        self.worker = None
        self.origin = "manual"
        self.assistant_state = ReactorState.IDLE
        self.setWindowTitle("NEXIS")
        self.resize(1366, 768)
        self.setMinimumSize(820, 600)
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(14, 10, 14, 8)
        root.setSpacing(9)
        self.build_header(root)
        nav = QHBoxLayout()
        self.tools_button = button("Tools", self.toggle_tools, nav)
        self.tools_button.setCheckable(True)
        self.navigation = ModuleNavigation()
        self.navigation.setAccessibleName("Module navigation")
        self.navigation.setFixedWidth(190)
        self.navigation.hide()
        nav.addStretch()
        self.nav_hint = self.small_label(
            "ONLINE AI   /   YOUR SELECTED PROVIDER   /   PERMISSIONS ENFORCED"
        )
        nav.addWidget(self.nav_hint)
        self.mute_button = button("Hard mute / sleep", self.toggle_microphone_mute, nav)
        self.mute_button.setAccessibleName("Hard mute or wake microphone; Ctrl Shift M")
        self.mute_button.setToolTip("Stops microphone capture, speech and queued actions. Wake resumes opted-in Hey NEXIS listening, or enables explicit Talk when wake listening is off.")
        self.update_mute_label()
        root.addLayout(nav)
        self.stack = QStackedWidget()
        workspace = QHBoxLayout()
        workspace.addWidget(self.navigation)
        workspace.addWidget(self.stack, 1)
        root.addLayout(workspace, 1)
        self.pages = {}
        self.build_dashboard()
        self.welcome = WelcomePage(self)
        self.add_page("Welcome", self.welcome)
        self.chat = ChatPage(self)
        self.chat.request.connect(lambda text: self.conversation_request(text, "chat"))
        self.add_page("Chat", self.chat)
        from nexis.ui.saved_conversations import SavedConversationsPage

        self.saved_conversations = SavedConversationsPage(self)
        self.add_page("Saved Conversations", self.saved_conversations)
        self.voice = VoicePage(self)
        self.voice.request.connect(lambda text: self.conversation_request(text, "voice"))
        self.voice.state.connect(self.voice_state)
        self.add_page("Voice Chat", self.voice)
        commands = QWidget()
        layout = QVBoxLayout(commands)
        heading(
            layout,
            "COMMAND REFERENCE",
            "Enter executes · Ctrl+K opens the drawer · Escape collapses it or stops work",
        )
        reference = QPlainTextEdit()
        reference.setReadOnly(True)
        reference.setPlainText(
            "\n\n".join(
                c.identifier.replace("_", " ") + " " + c.argument + "\n" + c.description
                for c in REGISTRY.values()
            )
            + "\n\nWorkflows: run <name>. Manual commands and AI-proposed tools share revocable permissions. Voice requests use the selected AI provider."
        )
        layout.addWidget(reference)
        self.add_page("Commands", commands)
        self.resources = []
        for title, table in (
            ("Applications", "shortcuts"),
            ("Snippets", "snippets"),
            ("Workflows", "workflows"),
        ):
            page = ResourcePage(self, table)
            self.resources.append(page)
            if table == "shortcuts":
                self.discovery = DiscoveryPanel(self)
                page.layout().insertWidget(2, self.discovery)
            if table == "workflows":
                self.workflow_studio = WorkflowStudio(self, page)
                page.layout().insertWidget(2, self.workflow_studio)
            self.add_page(title, page)
        self.files = FilesPage(self)
        self.add_page("Files", self.files)
        self.memories = MemoryPage(self)
        self.add_page("Local Memory", self.memories)
        self.health = HealthPage(self)
        self.add_page("PC Health", self.health)
        self.history_page = HistoryPage(self)
        self.add_page("History", self.history_page)
        self.providers = AIProvidersPage(self.data_dir)
        self.add_page("AI Providers", self.providers)
        self.providers.changed.connect(self.refresh_provider_identity)
        self.providers.profile_saved.connect(self.refresh_provider_identity)
        self.refresh_provider_identity()
        self.screen_awareness = ScreenPage(self)
        self.add_page("Screen Awareness", self.screen_awareness)
        self.settings_page = SettingsPage(self)
        self.add_page("Settings", self.settings_page)
        self.desktop_experience = DesktopPage(self)
        self.add_page("Desktop Companion", self.desktop_experience)
        self.updates_page = UpdatesPage(self)
        self.add_page("Updates", self.updates_page)
        self.settings_page.software_updates = SoftwareUpdatesPanel(self.updates_page)
        self.settings_page.general_layout.insertWidget(
            self.settings_page.general_layout.count() - 1, self.settings_page.software_updates
        )
        self.doctor = DoctorPage(self)
        self.add_page("NEXIS Doctor", self.doctor)
        about = QWidget()
        layout = QVBoxLayout(about)
        layout.addWidget(BrandLogo(128))
        heading(
            layout, "ABOUT / DIAGNOSTICS", "NEXIS Desktop " + DISPLAY_VERSION + " — Crimson Command"
        )
        info = QLabel(
            "Crimson Command HUD with online AI, permission-controlled Windows tools and manual commands.\n"
            "Vosk capture is local and explicitly activated. Windows speech is detected automatically.\n"
            "Created by ASH. Personal data is local under your Windows account; provider keys use Windows DPAPI. Proprietary — All Rights Reserved. EULA draft awaiting review.\n"
            "Project: https://github.com/zx-divine/nexis\n"
            "Ctrl+K: manual drawer · Ctrl+2: Chat · Ctrl+3: Voice · F11: full screen · Esc: exit/stop/collapse"
        )
        info.setWordWrap(True)
        layout.addWidget(info)
        button("Open GitHub project", lambda: self.submit("open https://github.com/zx-divine/nexis"), layout)
        self.diagnostics = QPlainTextEdit()
        self.diagnostics.setReadOnly(True)
        layout.addWidget(self.diagnostics)
        button("Refresh local diagnostics", self.refresh_diagnostics, layout)
        button("Export safe diagnostics…", self.export_diagnostics, layout)
        self.add_page("About", about)
        self.build_deck(root)
        self.navigation.currentTextChanged.connect(self.navigate)
        self.sensor_timer = QTimer(self)
        self.sensor_timer.setInterval(1000)
        self.sensor_timer.timeout.connect(self.sample_system)
        self.settle_timer = QTimer(self)
        self.settle_timer.setSingleShot(True)
        self.settle_timer.timeout.connect(self.settle_state)
        self.apply_theme()
        self.refresh()
        self.construction_ms = (perf_counter() - started) * 1000
        self.refresh_diagnostics()
        QShortcut(QKeySequence("Ctrl+K"), self, activated=self.focus_command)
        QShortcut(QKeySequence("Ctrl+1"), self, activated=lambda: self.navigate("Dashboard"))
        QShortcut(QKeySequence("Ctrl+2"), self, activated=lambda: self.navigate("Chat"))
        QShortcut(QKeySequence("Ctrl+3"), self, activated=lambda: self.navigate("Voice Chat"))
        QShortcut(QKeySequence("F11"), self, activated=self.toggle_fullscreen)
        QShortcut(QKeySequence("Escape"), self, activated=self.escape_action)
        QShortcut(QKeySequence("Ctrl+Shift+M"), self, activated=self.toggle_microphone_mute)
        QShortcut(QKeySequence("Ctrl+,"), self, activated=self.open_settings)
        self.show_launch_mode()
        self.set_state("IDLE")

    @staticmethod
    def small_label(text):
        label = QLabel(text)
        label.setObjectName("technical")
        return label

    def build_header(self, root):
        panel = QWidget()
        panel.setObjectName("appHeader")
        row = QHBoxLayout()
        row.setContentsMargins(8, 4, 8, 4)
        row.addWidget(BrandLogo(40, symbol=True))
        brand = QLabel("NEXIS")
        brand.setObjectName("brand")
        row.addWidget(brand)
        row.addStretch()
        self.mode_switches = {}
        for label, target in (("Home", "Welcome"), ("Voice", "Voice Chat"), ("Chat", "Chat"), ("Manual", "Dashboard")):
            control = button(label, lambda checked=False, page=target: self.switch_mode(page), row)
            control.setCheckable(True)
            control.setAccessibleName(label + " mode")
            self.mode_switches[target] = control
        self.always_active_button = button('Always Active', lambda: self.navigate('Desktop Companion'), row)
        self.always_active_button.setAccessibleName('Always Active settings and wake listening status')
        self.system_readout = self.small_label("CPU  N/A    MEM  N/A")
        row.addWidget(self.system_readout)
        self.clock = self.small_label(datetime.now().strftime("%H:%M:%S"))
        self.clock.setObjectName("goldText")
        row.addWidget(self.clock)
        self.header_state = self.small_label("●  IDLE")
        row.addWidget(self.header_state)
        self.settings_button = button("⚙", self.open_settings, row)
        self.settings_button.setAccessibleName("Open Settings Hub")
        self.settings_button.setToolTip("Settings Hub · Ctrl+,")
        panel.setLayout(row)
        root.addWidget(panel)

    def toggle_tools(self):
        opened = not self.navigation.isVisible()
        self.navigation.setVisible(opened)
        self.tools_button.setChecked(opened)
        if opened:
            self.navigation.setFocus()

    def switch_mode(self, page):
        self.focus_command() if page == "Dashboard" else self.navigate(page)

    def show_launch_mode(self):
        mode = self.db.setting("default_launch_mode")
        self.switch_mode({"welcome": "Welcome", "voice": "Voice Chat", "chat": "Chat", "manual": "Dashboard"}[mode])

    def build_dashboard(self):
        dashboard = QWidget()
        dashboard.setObjectName("dashboard")
        outer = QVBoxLayout(dashboard)
        outer.setContentsMargins(0, 0, 0, 0)
        self.hud_body = QHBoxLayout()
        self.hud_body.setSpacing(14)
        self.left_wing = QWidget()
        self.left_wing.setMinimumWidth(210)
        self.left_wing.setMaximumWidth(285)
        left = QVBoxLayout(self.left_wing)
        left.setContentsMargins(0, 0, 0, 0)
        metrics = HUDPanel("SYSTEM TELEMETRY", "01")
        self.cpu_meter, self.memory_meter = (
            SegmentedMeter("PROCESSOR"),
            SegmentedMeter("PHYSICAL MEMORY"),
        )
        metrics.body.addWidget(self.cpu_meter)
        metrics.body.addWidget(self.memory_meter)
        self.system_graph = SystemGraph()
        metrics.body.addWidget(self.system_graph, 1)
        self.uptime = self.small_label("UPTIME  N/A")
        metrics.body.addWidget(self.uptime)
        left.addWidget(metrics, 3)
        activity_panel = HUDPanel("RECENT OPERATIONS", "02")
        self.activity = QPlainTextEdit()
        self.activity.setReadOnly(True)
        self.activity.setMinimumHeight(55)
        self.activity.setMaximumHeight(130)
        activity_panel.body.addWidget(self.activity, 1)
        self.application_status = QLabel(
            "COMMAND WORKER / IDLE\nFILE SEARCH / IDLE\nMICROPHONE / OFF"
        )
        self.application_status.setObjectName("technical")
        activity_panel.body.addWidget(self.application_status)
        button("Inspect history", lambda: self.navigate("History"), activity_panel.body)
        left.addWidget(activity_panel, 2)
        self.hud_body.addWidget(self.left_wing, 2)
        center = QVBoxLayout()
        center.setSpacing(1)
        title = QLabel("N E X I S  /  C O M M A N D  R E A C T O R")
        title.setAlignment(Qt.AlignCenter)
        title.setObjectName("hudLabel")
        center.addWidget(title)
        self.reactor = ReactorWidget()
        self.reactor.activated.connect(self.focus_command)
        center.addWidget(self.reactor, 1)
        footer = QLabel("CORE INTERFACE VISUALIZATION  /  ENTER TO OPEN COMMAND DECK")
        footer.setWordWrap(True)
        footer.setAlignment(Qt.AlignCenter)
        footer.setObjectName("technical")
        center.addWidget(footer)
        self.hud_body.addLayout(center, 5)
        self.right_wing = QWidget()
        self.right_wing.setMinimumWidth(210)
        self.right_wing.setMaximumWidth(285)
        right = QVBoxLayout(self.right_wing)
        right.setContentsMargins(0, 0, 0, 0)
        radar = HUDPanel("ACTIVITY FIELD", "03")
        self.radar = RadarWidget()
        radar.body.addWidget(self.radar, 1)
        note = QLabel(
            "System activity visualization.\nSweep is decorative; dots mark local commands.\nNo object, network or threat detection."
        )
        note.setObjectName("technical")
        note.setWordWrap(True)
        radar.body.addWidget(note)
        right.addWidget(radar, 3)
        command_panel = HUDPanel("EXECUTION MONITOR", "04")
        self.active_command = QLabel("ACTIVE ACTION / NONE")
        self.active_command.setWordWrap(True)
        self.active_command.setTextFormat(Qt.PlainText)
        self.permission_status = QLabel("PERMISSIONS / ENFORCED")
        self.permission_status.setWordWrap(True)
        self.workflow_status = QLabel("WORKFLOW / IDLE")
        self.recent_result = QPlainTextEdit()
        self.recent_result.setReadOnly(True)
        self.recent_result.setMinimumHeight(55)
        self.recent_result.setMaximumHeight(100)
        self.recent_result.setPlaceholderText("No command result yet.")
        for label in (self.active_command, self.permission_status, self.workflow_status):
            label.setObjectName("technical")
            command_panel.body.addWidget(label)
        command_panel.body.addWidget(self.recent_result, 1)
        right.addWidget(command_panel, 2)
        self.hud_body.addWidget(self.right_wing, 2)
        outer.addLayout(self.hud_body, 1)
        self.drawer = HUDPanel("MANUAL COMMAND DECK", "TRUSTED PIPELINE")
        self.drawer.setMaximumHeight(215)
        row = QHBoxLayout()
        self.command = QLineEdit()
        self.command.setMaxLength(1000)
        self.command.setAccessibleName("Command input")
        self.command.setPlaceholderText("Enter a registered command… e.g. open notepad")
        self.command.returnPressed.connect(lambda: self.submit())
        row.addWidget(self.command, 1)
        self.execute = button("Execute", lambda: self.submit(), row)
        self.execute.setObjectName("execute")
        self.stop = button("Stop", self.stop_command, row)
        self.stop.setEnabled(False)
        self.pause_workflow_button = button("Pause workflow", self.pause_workflow, row)
        self.pause_workflow_button.setEnabled(False)
        button("Collapse", lambda: self.toggle_drawer(False), row)
        self.drawer.body.addLayout(row)
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.document().setMaximumBlockCount(1000)
        self.output.setPlainText("Ready. Type help for registered commands.")
        self.drawer.body.addWidget(self.output, 1)
        outer.addWidget(self.drawer)
        self.drawer.hide()
        self.add_page("Dashboard", dashboard)

    def build_deck(self, root):
        self.deck = CommandDeck()
        self.deck.chat_requested.connect(lambda: self.navigate("Chat"))
        self.deck.voice_requested.connect(lambda: self.navigate("Voice Chat"))
        self.deck.manual_requested.connect(self.toggle_manual)
        self.chat_button, self.voice_button, self.manual_button = (
            self.deck.chat,
            self.deck.voice,
            self.deck.manual,
        )
        root.addWidget(self.deck)
        self.footer = QWidget()
        foot = QHBoxLayout(self.footer)
        foot.setContentsMargins(0, 0, 0, 0)
        foot.addWidget(self.small_label("NEXIS V1  ·  YOUR PERMISSIONS, YOUR CONTROL"))
        foot.addStretch()
        self.motion_label = self.small_label("IDLE MOTION 8 FPS / ACTIVE TARGET 30 FPS")
        foot.addWidget(self.motion_label)
        root.addWidget(self.footer)

    def add_page(self, label, widget):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(widget)
        if label not in ("Dashboard", "Chat", "Voice Chat"):
            widget.setObjectName("contentPage")
        self.pages[label] = self.stack.addWidget(scroll)
        self.navigation.addItem(label)

    def navigate(self, label):
        if label not in self.pages:
            return
        if label != "Settings" and hasattr(self, "settings_page"):
            microphone = self.settings_page.voice_setup.microphone
            if microphone.worker and microphone.worker.isRunning():
                microphone.stop()
        # Leaving voice always requests capture stop; it never continues invisibly.
        if (
            hasattr(self, "voice")
            and label != "Voice Chat"
            and (
                self.voice.worker
                and self.voice.worker.isRunning()
                or self.voice.turn.state.value
                in {"LISTENING", "TRANSCRIBING", "THINKING", "SPEAKING"}
            )
        ):
            self.voice.stop()
        self.stack.setCurrentIndex(self.pages[label])
        blocked = self.navigation.blockSignals(True)
        self.navigation.setCurrentText(label)
        self.navigation.blockSignals(blocked)
        for page, control in self.mode_switches.items():
            control.setChecked(label == page)
        if hasattr(self, "deck"):
            self.deck.setVisible(label == "Dashboard")
            self.footer.setVisible(label != "Welcome")
        self.tools_button.setVisible(label != "Welcome")
        self.mute_button.setVisible(label != "Welcome" or self.db.setting('wake_word_enabled'))
        self.nav_hint.setVisible(label != "Welcome" and self.width() >= 1150)
        if label == "Chat":
            self.chat.input.setFocus()
        if hasattr(self, "deck"):
            self.chat_button.setChecked(label == "Chat")
            self.voice_button.setChecked(label == "Voice Chat")
            self.manual_button.setChecked(label == "Dashboard" and self.drawer.isVisible())
        self.responsive_layout()

    def open_settings(self, section="General"):
        self.navigate("Settings")
        self.settings_page.open_section(section if isinstance(section, str) else "General")

    def toggle_manual(self):
        visible = self.drawer.isVisible() and self.stack.currentIndex() == self.pages["Dashboard"]
        self.navigate("Dashboard")
        self.toggle_drawer(not visible)

    def toggle_drawer(self, opened):
        self.drawer.setVisible(opened)
        self.manual_button.setChecked(opened)
        self.responsive_layout()
        if opened:
            self.command.setFocus()

    def focus_command(self):
        self.navigate("Dashboard")
        self.toggle_drawer(True)
        self.command.setFocus()

    def configure_launcher(self):
        from nexis.ui.global_launcher import GlobalLauncher

        if self.global_launcher is None:
            self.global_launcher = GlobalLauncher(self.launch_command_bar)
        result = self.global_launcher.configure(self.db.setting("global_launcher_hotkey"), self.db.setting("global_launcher_enabled"))
        self.settings_page.launcher_status.setText(result.message)
        if result.active_chord and result.active_chord != self.db.setting("global_launcher_hotkey"):
            self.settings_page.launcher_status.setText(result.message + " Current active shortcut: " + result.active_chord)
        return result

    def launch_command_bar(self):
        if self.closing:
            return
        self.showNormal() if self.isMinimized() or not self.isVisible() else None
        self.raise_()
        self.activateWindow()
        self.focus_command()

    def responsive_layout(self):
        if not hasattr(self, "drawer"):
            return
        wings = self.width() >= 1100 and not (self.drawer.isVisible() and self.height() < 950)
        self.left_wing.setVisible(wings)
        self.right_wing.setVisible(wings)
        is_welcome = self.stack.currentIndex() == self.pages.get("Welcome", -1)
        self.nav_hint.setVisible(not is_welcome and self.width() >= 1150)
        self.system_readout.setVisible(self.width() >= 1100 and not is_welcome)
        self.clock.setVisible(self.width() >= 1100 and not is_welcome)
        if is_welcome:
            self.navigation.hide()
            self.tools_button.setChecked(False)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.responsive_layout()

    def toggle_fullscreen(self):
        self.showMaximized() if self.isFullScreen() else self.showFullScreen()

    def toggle_maximized(self):
        self.showNormal() if self.isMaximized() or self.isFullScreen() else self.showMaximized()

    def escape_action(self):
        if self.isFullScreen():
            self.showMaximized()
        elif self.worker and self.worker.isRunning():
            self.stop_command()
        elif self.voice.worker and self.voice.worker.isRunning():
            self.voice.stop()
        elif any(job.isRunning() for job in self.ai_jobs):
            for job in self.ai_jobs:
                job.cancel.set()
            self.set_state("IDLE")
        elif self.drawer.isVisible():
            self.toggle_drawer(False)
        else:
            self.navigate("Dashboard")

    def apply_theme(self, selected=None, custom=None):
        from nexis.ui.themes import apply

        if selected is not None:
            values = self.db.setting("custom_theme") if custom is None else custom
            apply(selected, values)
            self._theme_preview = (selected, values)
        else:
            apply(*getattr(self, "_theme_preview", (self.db.setting("theme"), self.db.setting("custom_theme"))))
        reduced, fps = self.db.setting("reduced_motion"), self.db.setting("animation_fps")
        for reactor in (self.reactor, self.voice.reactor, self.welcome.reactor):
            reactor.set_reduced_motion(reduced)
            reactor.set_fps(fps)
        self.deck.set_reduced_motion(reduced)
        if hasattr(self, "desktop_experience"):
            self.desktop_experience.apply_preferences()
        self.radar.reduced_motion = reduced
        self.radar.sync_timer()
        self.motion_label.setText(
            "REDUCED MOTION" if reduced else f"IDLE 8 FPS / ACTIVE TARGET {fps} FPS"
        )

    def sample_system(self):
        sample = self.sampler.sample()
        self.cpu_meter.set_value(sample.cpu)
        self.memory_meter.set_value(sample.memory)
        self.system_graph.add_sample(sample.cpu, sample.memory)
        cpu = "N/A" if sample.cpu is None else f"{sample.cpu:.1f}%"
        memory = "N/A" if sample.memory is None else f"{sample.memory:.0f}%"
        self.system_readout.setText(f"CPU {cpu}   MEM {memory}")
        self.clock.setText(datetime.now().strftime("%H:%M:%S"))
        if sample.uptime_seconds is not None:
            hours, remainder = divmod(sample.uptime_seconds, 3600)
            self.uptime.setText(f"OS UPTIME  {hours:03d}H {remainder // 60:02d}M")
        self.update_application_status()

    def update_application_status(self):
        command = bool(self.worker and self.worker.isRunning())
        files = bool(self.files.worker and self.files.worker.isRunning())
        voice = bool(self.voice.worker and self.voice.worker.isRunning())
        apps = (
            "SCAN"
            if any(job.isRunning() for job in self.discovery.jobs)
            else str(len(self.discovery.entries))
        )
        self.application_status.setText(
            f"COMMAND / {'ACTIVE' if command else 'IDLE'}\n"
            f"APPS {apps} / FILES {'ACTIVE' if files else 'IDLE'}\n"
            f"VOICE WORKER / {'ACTIVE' if voice else 'OFF'}"
        )

    def suspend_visuals(self, paused):
        if not hasattr(self, "sensor_timer"):
            return
        for reactor in (self.reactor, self.voice.reactor, self.welcome.reactor):
            reactor.set_paused(paused)
        self.radar.paused = paused
        self.radar.sync_timer()
        if paused:
            self.sensor_timer.stop()
        else:
            self.sampler.reset()
            self.sample_system()
            self.sensor_timer.start()

    def showEvent(self, event):
        super().showEvent(event)
        self.suspend_visuals(self.isMinimized())

    def hideEvent(self, event):
        self.suspend_visuals(True)
        if hasattr(self, "settings_page"):
            self.settings_page.voice_setup.microphone.stop()
        if hasattr(self, "voice"):
            self.voice.stop()
        if hasattr(self, "screen_awareness"):
            self.screen_awareness.discard()
        super().hideEvent(event)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.WindowStateChange:
            if self.isMinimized() and hasattr(self, "voice"):
                self.voice.stop()
                self.settings_page.voice_setup.microphone.stop()
                self.screen_awareness.discard()
                if self.db.setting("minimize_to_tray") and hasattr(self, "desktop_experience"):
                    QTimer.singleShot(0, self.desktop_experience.collapse)
            self.suspend_visuals(self.isMinimized())

    def set_state(self, state):
        if self.closing:
            return
        if state == "PAUSED":
            self.set_state("IDLE")
            self.header_state.setText("●  WORKFLOW PAUSED")
            return
        state = {"THINKING": "PROCESSING", "TRANSCRIBING": "PROCESSING", "CANCELLED": "IDLE"}.get(
            state, state
        )
        # Permission review wins over nested worker events. Hard mute suppresses
        # all microphone/speech activity. Playback outranks a completion settle.
        review = getattr(self, "_approval_cancel", None)
        if review is not None and not review.is_set():
            state = "WAITING_PERMISSION"
        elif self.microphone_muted and state in {"IDLE", "LISTENING", "SPEAKING"}:
            state = "MUTED"
        elif self.voice.speech_playing and state not in {"WAITING_PERMISSION", "ERROR"}:
            state = "SPEAKING"
        elif state == "LISTENING" and not (self.voice.capture_active or
                getattr(self.desktop_experience.wake, "microphone_active", False)):
            state = "PROCESSING"
        elif state == "SPEAKING" and not self.voice.speech_playing:
            state = "PROCESSING"
        elif state == "IDLE" and (self.voice.capture_active or
                getattr(self.desktop_experience.wake, "microphone_active", False)):
            state = "LISTENING"
        self.assistant_state = ReactorState(state)
        self.reactor.set_state(self.assistant_state)
        self.welcome.reactor.set_state(self.assistant_state)
        self.voice.reactor.set_state(self.assistant_state)
        self.header_state.setText("●  " + self.assistant_state.value)

    def onboarding_finished(self):
        """Always introduce all three modes once; keep the saved future launch preference."""
        self.refresh()
        self.settings_page.provider.reload_saved()
        self.settings_page.reload_profile()
        self.apply_theme()
        self.navigate("Welcome")

    def voice_state(self, state):
        if not (self.worker and self.worker.isRunning()):
            self.set_state(state)

    def set_audio_level(self, level):
        if self.closing:
            return
        if self.microphone_muted:
            level = None
        for core in (self.reactor, self.welcome.reactor, self.voice.reactor):
            core.set_audio_level(level)
        if hasattr(self, "desktop_experience") and self.desktop_experience.orb:
            self.desktop_experience.orb.reactor.set_audio_level(level)

    def settle_state(self):
        if (not self.closing and not (self.worker and self.worker.isRunning())
                and not any(job.isRunning() for job in self.ai_jobs)):
            self.set_state(ReactorState.IDLE)

    def selected_profile(self):
        try:
            return self.providers.manager.active()
        except ValueError:
            return None  # Preserve unreadable encrypted configuration; never replace it.

    def refresh_provider_identity(self):
        label = "SELECTED: " + provider_label(self.selected_profile())
        self.nav_hint.setText(label[:95])
        self.nav_hint.setToolTip(label + "\nSaved configuration, not a live model verification. An active request keeps its original provider snapshot.")
        self.chat.provider_status.setText(label)

    def conversation_request(self, text, origin):
        text = sanitize_request(text)
        if self.closing:
            return
        if origin == "chat":
            self.chat.pending_prompt = text
        if text.casefold().strip(' .!?') in {'what is my name', "what's my name", 'what should you call me'}:
            name = self.db.setting('preferred_name')
            self.ai_reply(f"I'll call you {name}." if name else 'Tell me your preferred name in Settings > General.', origin)
            return
        # A single website request can work without a paid/cloud planner. The
        # normal Engine still validates permissions, approval and cancellation.
        from nexis.core.websites import website_command
        from nexis.core.intents import local_command

        try:
            local_website = website_command(text) or local_command(text)
        except ValueError as exc:
            self.local_page_reply(str(exc), origin)
            return
        if local_website:
            if origin == "voice":
                self.voice.thinking()
            self.submit(local_website, origin)
            return
        memory_request = re.fullmatch(r"(remember|forget)(?:\s+this)?(?::\s*|\s+)(.+)", text, re.IGNORECASE | re.DOTALL)
        memory_review = text.strip().casefold().rstrip(".?!") in {"show my saved memories", "show my memories", "review my memories"}
        screen_request = text.strip().casefold().rstrip(".?!") in {"explain this error on my screen", "explain my screen", "analyze my screen"}
        local_only = bool(memory_request or memory_review or screen_request)
        if not local_only and (not self.conversation_history or self.conversation_history[-1] != {
            "role": "user",
            "content": text[:1000],
        }):
            self.conversation_history.append({"role": "user", "content": text[:1000]})
        self.conversation_history = self.conversation_history[-24:]
        if origin == "voice":
            self.voice.thinking()
        if memory_review:
            self.navigate("Local Memory")
            self.local_page_reply("Your saved memories are available locally for review. Nothing was sent to AI.", origin)
            return
        if screen_request:
            self.screen_awareness.question.setText(text[:1000])
            self.navigate("Screen Awareness")
            self.local_page_reply("Screen Awareness is ready for your explicit action. Enable the feature and screen permission if needed, click Capture preview, inspect it, then separately approve the destination before sending. Nothing has been captured or transmitted.", origin)
            return
        if memory_request and memory_request[1].casefold() == "remember":
            self.memories.draft(memory_request[2].strip())
            self.navigate("Local Memory")
            self.local_page_reply("Memory draft prepared locally. Review it in Local Memory and click Save approved memory. Nothing has been saved or sent to AI.", origin)
            return
        if memory_request and memory_request[1].casefold() == "forget":
            self.memories.query.setText(memory_request[2].strip()[:300])
            self.navigate("Local Memory")
            self.local_page_reply("Matching memories are shown locally. Select the intended note and confirm Delete selected. Nothing has been deleted or sent to AI.", origin)
            return
        if is_identity_question(text) and not any(job.isRunning() for job in self.ai_jobs):
            # Local application facts do not need a cloud key or tool permissions.
            # Ordinary and compound requests still follow the existing operator.
            self.ai_reply(identity_reply(self.selected_profile()), origin)
            return
        start_chat(self, text, origin)

    def local_page_reply(self, text, origin):
        # Navigating away cancels the voice generation. Do not start hidden speech
        # or a hands-free follow-up from a memory-management acknowledgement.
        # Local commands and acknowledgements never become later cloud history.
        self.chat.add_message("NEXIS", text)
        if origin == "voice":
            self.voice.response.setPlainText(text)
            self.voice.change_state("IDLE")

    def ai_reply(self, text, origin=None):
        text = sanitize_request(text)
        if self.closing:
            return
        origin = origin or self.ai_origin
        self.conversation_history.append({"role": "assistant", "content": text[:16000]})
        if origin == "chat":
            self.chat.finish_stream()
            self.chat.add_message("NEXIS", text)
            self.set_state("IDLE")
        else:
            self.voice.receive_reply(text)

    def ai_error(self, text, origin):
        if self.closing:
            return
        self.set_state("ERROR")
        if origin == "voice":
            self.voice.failure(text)
            self.voice.response.setPlainText(text)
        else:
            self.chat.finish_stream(completed=False)
            self.chat.add_message("NEXIS", text)
        if str(text).startswith(("CONNECTION:", "DNS:", "NETWORK:")):
            self.set_state("OFFLINE")

    def ai_partial(self, text, origin):
        if origin == "chat":
            self.chat.show_stream(text)
        elif not text.lstrip().startswith(("{", "[", "`")):
            self.voice.response.setPlainText(
                "AI response in progress (no action completion implied):\n"
                + sanitize_request(text[:16000])
            )

    def online_phase(self, phase, origin):
        if phase in {"THINKING", "CANCELLED"}:
            self.set_state(phase)
        elif phase.startswith("EXECUTING"):
            self.set_state("EXECUTING")
        if origin == "voice" and phase == "THINKING":
            self.voice.thinking()

    def online_finished(self, job, origin):
        self.execute.setEnabled(True)
        self.chat.send_button.setEnabled(True)
        self.chat.input.setEnabled(True)
        if self.current_ai is job and job.cancel.is_set() and not self.closing:
            if origin == "voice":
                self.voice.cancelled()
            else:
                self.chat.finish_stream(completed=False)
                self.chat.add_message(
                    "NEXIS", "Request cancelled; your prompt is retained for Retry."
                )
        if job in self.ai_jobs:
            self.ai_jobs.remove(job)
        if self.current_ai is job:
            self.current_ai = None
            if job.cancel.is_set() and not self.closing:
                self.set_state("IDLE")

    @safe_ui
    def start_services(self):
        if self.closing:
            return
        self.configure_launcher()
        path = detect_model(self.db.setting("voice_model_path"), self.data_dir)
        if path:
            self.db.set_setting("voice_model_path", path)
        self.voice.refresh_setup()
        self.settings_page.voice_setup.refresh_model()
        self.settings_page.voice_setup.start_speech()
        self.desktop_experience.start_if_enabled()
        self.updates_page.start()
        if self.discovery.stale():
            self.discovery.scan()
        self.discovery_timer = QTimer(self)
        self.discovery_timer.setInterval(6 * 60 * 60 * 1000)
        self.discovery_timer.timeout.connect(self.rescan_if_stale)
        self.discovery_timer.start()

    def rescan_if_stale(self):
        if not self.closing and self.discovery.stale():
            self.discovery.scan()

    def background_jobs(self):
        setup = self.settings_page
        return [
            self.worker,
            self.files.worker,
            *self.files.index_jobs,
            *self.memories.jobs,
            *self.health.jobs,
            *self.workflow_studio.jobs,
            *self.screen_awareness.jobs,
            *self.updates_page.jobs,
            *self.doctor.jobs,
            self.voice.worker,
            *self.desktop_experience.wake.jobs,
            *self.ai_jobs,
            *self.discovery.jobs,
            *setup.provider.jobs,
            *setup.voice_setup.jobs,
            setup.voice_setup.speech,
            setup.voice_setup.microphone.worker,
        ]

    def update_mute_label(self):
        self.microphone_muted = self.db.setting("microphone_muted")
        self.mute_button.setText("Wake / enable microphone" if self.db.setting("microphone_muted") else "Hard mute / sleep")
        if hasattr(self, "welcome"):
            self.set_state("IDLE")
            self.voice.reactor.set_state(self.assistant_state)
        if hasattr(self, "desktop_experience") and self.desktop_experience.orb:
            self.desktop_experience.orb.set_state(self.assistant_state.value)

    def toggle_microphone_mute(self):
        self.set_microphone_muted(not self.db.setting("microphone_muted"))

    def set_microphone_muted(self, muted):
        # Cancel first: persisting a preference must not delay a capture-stop request.
        if muted:
            self.desktop_experience.wake.pause()
            self.voice.stop()
            self.settings_page.voice_setup.microphone.stop()
            self.stop_command()
            for job in self.ai_jobs:
                job.cancel.set()
                if hasattr(job, "respond"):
                    job.respond(False)
            self.workflow_studio.cancel()
            self.screen_awareness.discard()
            self.updates_page.cancel()
            self.doctor.cancel()
            self.settings_page.voice_setup.stop_speech()
            dialogs.reject_pending(self)
        self.db.set_setting("microphone_muted", bool(muted))
        self.update_mute_label()
        self.voice.status.setText(
            "Hard mute / sleep: capture and speech stopped; queued actions cancelled. Wake requires an explicit click."
            if muted else "Awake. Your opted-in Hey NEXIS listener may resume; otherwise microphone stays off until Talk."
        )
        self.desktop_experience.wake.refresh()

    def submit(self, text=None, origin="manual"):
        self.desktop_experience.wake.pause()
        if any(job.isRunning() for job in self.ai_jobs):
            message = "An AI request is still running. Cancel it or wait before starting a manual action; no command was executed."
            self.output.appendPlainText(message)
            if origin == "chat":
                self.chat.add_message("NEXIS", message)
            elif origin == "voice":
                self.voice.response.setPlainText(message)
            return
        if self.worker and self.worker.isRunning():
            message = "A command is still running. Stop it or wait for completion."
            self.output.appendPlainText(message)
            if origin == "chat":
                self.chat.add_message("NEXIS", message)
            elif origin == "voice":
                self.voice.response.setPlainText(message)
            return
        text = self.command.text() if text is None else text
        from nexis.core.parser import parse
        from nexis.core.catalog import Catalog

        try:
            request = parse(text)
            matches = Catalog(self.db).matches(request.argument) if request.action == "open" else []
            if len(matches) > 1:
                choices = [entry["name"] + " — " + entry["target"] for entry in matches]
                selected, accepted = QInputDialog.getItem(
                    self,
                    "Choose application",
                    "Multiple applications match. Which one should open?",
                    choices,
                    0,
                    False,
                )
                if not accepted:
                    return
                text = "open app:" + matches[choices.index(selected)]["id"]
        except ValueError:
            pass
        self.origin = origin
        if origin == "manual":
            self.focus_command()
        self.output.setPlainText("Processing command…")
        self.execute.setEnabled(False)
        self.stop.setEnabled(True)
        self.chat.send_button.setEnabled(False)
        self.settle_timer.stop()
        self.set_state(ReactorState.PROCESSING)
        self.active_command.setText("ACTIVE ACTION / " + text.partition(" ")[0].upper())
        self.permission_status.setText("PERMISSIONS / VALIDATING")
        self.workflow_status.setText(
            "WORKFLOW / VALIDATING" if text.lower().startswith("run ") else "WORKFLOW / IDLE"
        )
        for resource in [*self.resources, self.settings_page]:
            resource.setEnabled(False)
        self.radar.add_event()
        self.worker = CommandWorker(self.db, text, self.platform,
                                    allow_radio=origin != "voice" or getattr(self.voice, "radio_reviewed", False))
        self.pause_workflow_button.setText("Pause workflow")
        self.pause_workflow_button.setEnabled(text.lower().startswith("run "))
        worker = self.worker

        def active():
            return self.worker is worker and not worker.cancel.is_set() and not self.closing

        self.worker.permission.connect(lambda preview: self.permission(preview) if active() else worker.respond(False))
        self.worker.phase.connect(lambda phase: self.set_state(phase) if active() else None)
        self.worker.step.connect(lambda index, result: self.step_result(index, result) if active() else None)
        self.worker.finished_result.connect(lambda result: self.result(result) if active() else None)
        self.worker.finished.connect(lambda: self.command_finished() if self.worker is worker else None)
        self.worker.start()

    def permission(self, preview):
        self.permission_status.setText("PERMISSIONS / AWAITING REVIEW")
        worker = self.worker
        if not worker or worker.cancel.is_set():
            if worker:
                worker.respond(False)
            return
        self._approval_cancel = worker.cancel
        self.set_state("WAITING_PERMISSION")
        try:
            allowed = dialogs.confirm(self, preview)
        finally:
            self._approval_cancel = None
        self.permission_status.setText(
            "PERMISSIONS / APPROVED" if allowed else "PERMISSIONS / DENIED"
        )
        worker.respond(allowed and not worker.cancel.is_set())
        self.set_state("PROCESSING" if allowed and not worker.cancel.is_set() else "IDLE")

    def apply_payload(self, result):
        if self.closing or (self.worker and self.worker.cancel.is_set()):
            return
        if result.ok and "clipboard" in result.data:
            QApplication.clipboard().setText(result.data["clipboard"])
            result.message = result.message.replace("ready for clipboard", "copied to clipboard")
        if result.ok and "search" in result.data:
            self.navigate("Files")
            self.files.query.setText(result.data["search"])
            self.files.start()

    def step_result(self, index, result):
        self.apply_payload(result)
        self.workflow_status.setText(f"WORKFLOW / STEP {index} / {'OK' if result.ok else 'FAILED'}")
        self.output.appendPlainText(f"Step {index}: {result.message}")
        if self.origin == "chat":
            self.chat.add_message("STEP " + str(index), result.message)

    def result(self, result):
        self.apply_payload(result)
        self.output.appendPlainText(("✓ " if result.ok else "✕ ") + result.message)
        self.recent_result.setPlainText(result.message)
        self.set_state(ReactorState.SUCCESS if result.ok else ReactorState.ERROR)
        if (
            "AWAITING" not in self.permission_status.text()
            and "DENIED" not in self.permission_status.text()
        ):
            self.permission_status.setText("PERMISSIONS / ENFORCED")
        if self.origin == "chat":
            self.chat.add_message("NEXIS", result.message)
        elif self.origin == "voice":
            if not self.closing and not (self.worker and self.worker.cancel.is_set()):
                self.voice.receive_reply(result.message)
            else:
                self.voice.response.setPlainText("Command cancelled. Already-submitted Windows requests cannot be recalled.")
        self.refresh()
        self.settle_timer.start(2200)

    def command_finished(self):
        self.execute.setEnabled(True)
        self.stop.setEnabled(False)
        self.pause_workflow_button.setEnabled(False)
        self.chat.send_button.setEnabled(True)
        for resource in [*self.resources, self.settings_page]:
            resource.setEnabled(True)
        self.update_application_status()

    def stop_command(self):
        if self.worker and self.worker.isRunning():
            self.worker.cancel.set()
            self.worker.respond(False)
            self.set_state("IDLE")
            self.output.appendPlainText(
                "Stop requested. Already launched applications remain open."
            )

    def pause_workflow(self):
        if self.worker and self.worker.isRunning() and self.pause_workflow_button.isEnabled():
            if self.worker.pause.is_set():
                self.worker.pause.clear()
                self.pause_workflow_button.setText("Pause workflow")
                self.output.appendPlainText("Workflow resume requested; permissions are checked again before the next step.")
            else:
                self.worker.pause.set()
                self.pause_workflow_button.setText("Resume workflow")
                self.output.appendPlainText("Pause requested at the next step boundary. An action already submitted to Windows is not undone.")

    def refresh(self):
        self.welcome.refresh()
        for page in self.resources:
            page.refresh()
        self.history_page.refresh()
        rows = self.db.rows("SELECT timestamp,command,status FROM history ORDER BY id DESC LIMIT 4")
        self.activity.setPlainText(
            "\n".join(f"{r['command'].upper()}  /  {r['status']}" for r in rows)
            or "No activity recorded.\nCommands remain under your control."
        )

    def diagnostic_data(self):
        import platform

        return {
            "version": __version__,
            "python": platform.python_version(),
            "platform": platform.system(),
            "schema": self.db.rows("PRAGMA user_version")[0]["user_version"],
            "approved_folder_count": len(self.db.setting("search_roots")),
            "window_construction_ms": round(getattr(self, "construction_ms", 0), 1),
            "history_enabled": self.db.setting("history_enabled"),
            "telemetry": False,
            "catalog_applications": len(self.discovery.entries),
            "windows_voice_count": max(0, self.settings_page.voice_setup.voices.count() - 1),
            "provider_saved": self.providers.manager.path.is_file()
            or self.providers.manager.legacy.path.is_file(),
        }

    def refresh_diagnostics(self):
        logs = self.data_dir / "nexis.log"
        # Logs contain only fixed messages and exception class names; no paths or input.
        text = (
            logs.read_text(encoding="utf-8")[-20000:] if logs.exists() else "No local log entries."
        )
        self.diagnostics.setPlainText(
            json.dumps(self.diagnostic_data(), indent=2) + "\n\nLOCAL LOG\n" + text
        )

    def export_diagnostics(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Safe diagnostic export", "nexis-diagnostics.json", "JSON (*.json)"
        )
        if path:
            if Path(path).resolve().is_relative_to(self.data_dir.resolve()):
                raise ValueError("Export outside the NEXIS data directory.")
            if Path(path).suffix.lower() != ".json":
                raise ValueError("Choose a .json export filename.")
            Path(path).write_text(json.dumps(self.diagnostic_data(), indent=2), encoding="utf-8")
            QMessageBox.information(
                self,
                "Diagnostics",
                "Exported version and aggregate settings only. "
                "No paths, logs, snippets or command arguments included.",
            )

    def closeEvent(self, event):
        self.updates_page.shutdown()
        if not self.closing:
            self.voice.capture_active = self.voice.speech_playing = False
            self.desktop_experience.wake.microphone_active = False
            self.set_audio_level(None)
            self.set_state("IDLE")
        self.suspend_visuals(True)
        self.closing = True
        self.desktop_experience.wake.stop()
        if self.global_launcher:
            self.global_launcher.stop()
        self.voice.stop()
        self.settings_page.voice_setup.stop_speech()
        self.settings_page.voice_setup.microphone.stop()
        workers = [w for w in self.background_jobs() if w and w.isRunning()]
        if workers:
            for worker in workers:
                worker.cancel.set()
                if isinstance(worker, CommandWorker):
                    worker.respond(False)
            self.output.setPlainText("Stopping background work safely…")
            QTimer.singleShot(200, self.close)
            event.ignore()
            return
        self.sensor_timer.stop()
        if hasattr(self, "discovery_timer"):
            self.discovery_timer.stop()
        self.settle_timer.stop()
        self.suspend_visuals(True)
        self.desktop_experience.shutdown()
        event.accept()
