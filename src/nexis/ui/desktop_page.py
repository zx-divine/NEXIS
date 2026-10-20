"""Optional orb/tray lifecycle. No automatic recording or hidden voice mode."""

from PySide6.QtCore import QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QCheckBox, QLabel, QSystemTrayIcon, QMenu, QApplication

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
        heading(layout, "DESKTOP COMPANION", "Experimental and optional. Reuses the Crimson reactor. Showing or dragging it never records. Talk opens visible Voice Chat and uses its normal permissions, model and selected provider. Hiding/minimizing the main window stops voice capture.")
        self.enabled = QCheckBox("Enable floating reactor and Windows tray controls")
        self.enabled.setChecked(window.db.setting("floating_orb_enabled"))
        self.enabled.toggled.connect(self.toggle)
        layout.addWidget(self.enabled)
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
        if self.enabled.isChecked():
            self.toggle(True)

    def toggle(self, enabled):
        self.window.db.set_setting("floating_orb_enabled", enabled)
        if not enabled:
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
            self.tray.setToolTip("NEXIS — explicit Talk only; no background microphone")
            menu = QMenu(self)
            for title, callback in (("Open NEXIS", self.restore), ("Push to talk (opens Voice Chat)", self.orb.talk),
                    ("Collapse main to tray / orb", self.collapse), ("Show orb", self.show_orb),
                    ("Hide orb", self.hide_orb), ("Hard mute / sleep", lambda: self.window.set_microphone_muted(True)),
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
        if state == 5:
            self.orb.show()
            self.status.setText("Orb enabled. Microphone remains off until explicit Talk. " + ("Windows tray controls available." if self.tray and self.tray.isVisible() else "Tray unavailable; collapsing is disabled so the main window remains accessible."))
        else:
            self.orb.hide()
            self.status.setText("Orb temporarily hidden: Windows reports fullscreen/presentation/quiet/locked state, or eligibility is unavailable. Tray/main controls remain available. No microphone was started.")
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
        self.cleanup()
        if self.orb:
            self.orb.close()
