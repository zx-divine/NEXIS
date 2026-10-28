"""Qt dispatch for a registered Windows shortcut; activation only opens local UI."""

from ctypes import wintypes

from PySide6.QtCore import QAbstractNativeEventFilter, QTimer
from PySide6.QtWidgets import QApplication

from nexis.platform.hotkeys import HotkeyRegistration, RegistrationResult, WM_HOTKEY


class GlobalLauncher(QAbstractNativeEventFilter):
    def __init__(self, callback, registration=None):
        super().__init__()
        self.callback = callback
        self.registration = registration or HotkeyRegistration()
        self.installed = False
        self.stopped = False

    def configure(self, chord, enabled):
        self.stopped = not enabled
        app = QApplication.instance()
        if enabled and app.platformName() != "windows":
            return RegistrationResult(False, "Global shortcut unavailable on this Qt platform. Ctrl+K works inside NEXIS.", "")
        result = self.registration.configure(chord, enabled)
        if result.ok and enabled and not self.installed:
            app.installNativeEventFilter(self)
            self.installed = True
        elif not enabled and result.ok and self.installed:
            app.removeNativeEventFilter(self)
            self.installed = False
        return result

    def nativeEventFilter(self, event_type, message):
        if not self.stopped and bytes(event_type) in {b"windows_generic_MSG", b"windows_dispatcher_MSG"}:
            packet = wintypes.MSG.from_address(int(message))
            if packet.message == WM_HOTKEY and packet.wParam == self.registration.identifier:
                QTimer.singleShot(0, self.activate)
                return True, 0
        return False, 0

    def activate(self):
        if not self.stopped:
            self.callback()

    def stop(self):
        self.stopped = True
        if self.installed:
            QApplication.instance().removeNativeEventFilter(self)
            self.installed = False
        return self.registration.stop()
