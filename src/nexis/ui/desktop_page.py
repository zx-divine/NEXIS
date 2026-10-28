"""Optional visible orb/tray lifecycle and separately opted-in local wake listening."""

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QCheckBox, QLabel, QSpinBox, QSystemTrayIcon, QMenu, QApplication

from nexis.branding import application_icon
from nexis.platform.desktop_state import notification_state
from nexis.ui.orb import FloatingOrb
from nexis.ui.pages import heading, button


class DesktopPage(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window, self.orb, self.tray = window, None, None
        self.hidden_by_user = False
        self.watched_screens = set()
        self.timer = QTimer(self)
        self.timer.setInterval(2000)
        self.timer.timeout.connect(self.refresh_visibility)
        layout = QVBoxLayout(self)
        heading(layout, "ALWAYS ACTIVE", "Keep NEXIS available in the tray and floating orb. Optionally enable local Hey NEXIS listening below. Windows sign-in startup remains a separate Settings → General choice.")
        self.enabled = QCheckBox("Always Active — enable standby, floating reactor and tray controls")
        self.enabled.setChecked(window.db.setting("floating_orb_enabled"))
        self.enabled.toggled.connect(self.toggle)
        layout.addWidget(self.enabled)
        self.wake_enabled = QCheckBox('Listen locally for “Hey NEXIS” while Always Active is enabled')
        self.wake_enabled.setChecked(window.db.setting('wake_word_enabled'))
        self.wake_enabled.toggled.connect(self.set_wake_enabled)
        layout.addWidget(self.wake_enabled)
        self.wake_threshold = QSpinBox()
        self.wake_threshold.setRange(50, 95)
        self.wake_threshold.setValue(window.db.setting('wake_word_confidence'))
        self.wake_threshold.setSuffix('% minimum word confidence')
        self.wake_threshold.setAccessibleName('Wake phrase confidence; higher reduces false activations')
        self.wake_threshold.valueChanged.connect(self.set_wake_threshold)
        layout.addWidget(self.wake_threshold)
        notice = QLabel('Opt-in microphone use: standby audio is processed locally in memory and discarded. Say “Hey NEXIS”, pause for the listening indicator, then speak. Only the command after activation may be sent to your selected AI provider. Hard mute stops capture; Windows busy/locked states pause it. Minimize keeps NEXIS available; Close exits. This uses Vosk phrase spotting; real-room accuracy must be tested on your microphone.')
        notice.setWordWrap(True)
        layout.addWidget(notice)
        self.wake_status = QLabel('Wake listening off — no microphone started.')
        self.wake_status.setWordWrap(True)
        self.wake_status.setTextFormat(Qt.PlainText)
        layout.addWidget(self.wake_status)
        from nexis.ui.wake_listening import WakeListening

        self.wake = WakeListening(self)
        button('Retry wake listening', self.wake.retry, layout)
        self.always_on_top = QCheckBox("Keep orb above other windows")
        self.always_on_top.setChecked(window.db.setting("orb_always_on_top"))
        self.always_on_top.toggled.connect(self.set_always_on_top)
        layout.addWidget(self.always_on_top)
        row = QHBoxLayout()
        button("Show orb", self.show_orb, row)
        button("Hide orb", self.hide_orb, row)
        button("Collapse main to tray / orb", self.collapse, row)
        button("Restore main window", self.restore, row)
        layout.addLayout(row)
        self.status = QLabel("Disabled by default. When enabled, a lightweight two-second Windows eligibility check hides the orb during reported fullscreen/presentation/lock/quiet states. No animation runs while hidden or in reduced-motion mode. If Windows eligibility is unavailable, the orb stays hidden; tray/main controls remain available.")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        layout.addStretch()

    def start_if_enabled(self):
        self.enabled.setChecked(self.window.db.setting('floating_orb_enabled'))
        self.wake_enabled.setChecked(self.window.db.setting('wake_word_enabled'))
        if self.enabled.isChecked():
            self.toggle(True)
        self.wake.start()

    def set_wake_enabled(self, enabled):
        self.window.db.set_setting('wake_word_enabled', enabled)
        self.wake.retry()

    def set_wake_threshold(self, value):
        self.window.db.set_setting('wake_word_confidence', value)
        self.wake.retry()

    def toggle(self, enabled):
        self.window.db.set_setting("floating_orb_enabled", enabled)
        self.window.always_active_button.setText('Always Active ●' if enabled else 'Always Active')
        if not enabled:
            self.wake.pause()
            self.cleanup()
            self.window.showNormal()
            return
        if self.orb is None:
            self.orb = FloatingOrb(self.window, self.hide_orb)
            self.window.reactor.state_changed.connect(self.orb.set_state)
            self.orb.set_state(self.window.assistant_state.value)
            QApplication.instance().screenAdded.connect(self.screen_added)
            QApplication.instance().screenRemoved.connect(self.screen_removed)
            for screen in QApplication.screens():
                self.screen_added(screen)
        if self.tray is None and QSystemTrayIcon.isSystemTrayAvailable():
            self.tray = QSystemTrayIcon(application_icon(), self)
            self.tray.setToolTip("NEXIS — Always Active; see listening status")
            menu = QMenu(self)
            for title, callback in (("Open NEXIS", self.restore), ("Push to talk (opens Voice Chat)", self.orb.talk),
                    ("Collapse main to tray / orb", self.collapse), ("Show orb", self.show_orb),
                    ("Hide orb", self.hide_orb), ("Hard mute / sleep", lambda: self.window.set_microphone_muted(True)),
                    ("Pause wake listening", lambda: self.wake_enabled.setChecked(False)),
                    ("Unmute / resume opted-in wake listening", lambda: self.window.set_microphone_muted(False)),
                    ("Settings Hub", self.window.open_settings),
                    ("Exit NEXIS", self.window.close)):
                action = QAction(title, menu)
                action.triggered.connect(callback)
                menu.addAction(action)
            self.tray.setContextMenu(menu)
            self.tray.activated.connect(lambda reason: self.restore() if reason == QSystemTrayIcon.Trigger else None)
            self.tray.show()
        if self.tray:
            self.tray.show()
        self.show_orb()

    def apply_preferences(self):
        if self.orb:
            self.orb.apply_preferences()

    def set_always_on_top(self, enabled):
        self.window.db.set_setting("orb_always_on_top", enabled)
        if self.orb:
            self.orb.apply_preferences()
            self.refresh_visibility()

    def reposition(self, *args):
        if self.orb:
            self.orb.reposition()

    def screen_added(self, screen):
        if screen not in self.watched_screens:
            self.watched_screens.add(screen)
            screen.availableGeometryChanged.connect(self.reposition)
            screen.logicalDotsPerInchChanged.connect(self.reposition)
        self.reposition()

    def screen_removed(self, screen):
        self.watched_screens.discard(screen)
        self.reposition()

    def refresh_visibility(self):
        if not self.enabled.isChecked() or self.window.closing or self.hidden_by_user or not self.orb:
            return
        state = notification_state()
        if state in {None, 1}:
            self.window.voice.stop()
            self.window.settings_page.voice_setup.microphone.stop()
            self.window.settings_page.voice_setup.stop_speech()
        if state == 5:
            self.orb.show()
            self.status.setText("Always Active enabled. Wake microphone status is shown above. " + ("Windows tray controls available." if self.tray and self.tray.isVisible() else "Tray unavailable; collapsing is disabled so the main window remains accessible."))
        else:
            self.orb.hide()
            self.status.setText("Orb temporarily hidden: Windows reports fullscreen/presentation/quiet/locked state, or eligibility is unavailable. Tray/main controls remain available. No microphone was started.")
        self.orb.set_state(self.window.assistant_state.value)
        if not QSystemTrayIcon.isSystemTrayAvailable() and not self.window.isVisible():
            self.window.showNormal()

    def show_orb(self):
        if not self.enabled.isChecked():
            self.status.setText("Enable the optional desktop companion first.")
            return
        if self.orb is None:
            self.toggle(True)
            return
        self.hidden_by_user = False
        self.orb.reposition()
        self.timer.start()
        self.refresh_visibility()

    def hide_orb(self):
        self.hidden_by_user = True
        self.timer.stop()
        if self.orb:
            self.orb.hide()
        if not self.window.isVisible():
            self.window.voice.stop()

    def collapse(self):
        if not self.enabled.isChecked() or not self.tray or not self.tray.isVisible():
            self.status.setText("Enable the companion with an available Windows tray before collapsing. The main window remains accessible.")
            return
        self.show_orb()
        self.window.hide()  # Existing hide handler stops microphone and speech.

    def restore(self):
        self.window.showNormal()
        self.window.raise_()
        self.window.activateWindow()

    def cleanup(self):
        self.timer.stop()
        if self.orb:
            self.orb.hide()
        if self.tray:
            self.tray.hide()

    def shutdown(self):
        self.wake.stop()
        self.cleanup()
        if self.orb:
            self.orb.close()
