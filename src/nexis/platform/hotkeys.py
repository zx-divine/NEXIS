"""Windows RegisterHotKey boundary. No keyboard hook, injection or shell commands."""

import ctypes
from ctypes import wintypes
import os
from dataclasses import dataclass

HOTKEYS = {
    "Ctrl+Space": (0x0002, 0x20),
    "Ctrl+Alt+Space": (0x0002 | 0x0001, 0x20),
    "Ctrl+Shift+Space": (0x0002 | 0x0004, 0x20),
    "Ctrl+Alt+K": (0x0002 | 0x0001, ord("K")),
}
WM_HOTKEY = 0x0312
MOD_NOREPEAT = 0x4000


@dataclass(frozen=True)
class RegistrationResult:
    ok: bool
    message: str
    active_chord: str


class HotkeyRegistration:
    def __init__(self, api=None):
        if api is None and os.name == "nt":
            api = ctypes.WinDLL("user32", use_last_error=True)
            api.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
            api.RegisterHotKey.restype = wintypes.BOOL
            api.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
            api.UnregisterHotKey.restype = wintypes.BOOL
        self.api = api
        self.identifier = None
        self.chord = ""

    def configure(self, chord, enabled=True):
        if chord not in HOTKEYS:
            raise ValueError("Choose a supported command-launcher shortcut.")
        if not enabled:
            released = self.stop()
            return RegistrationResult(released, "Global launcher disabled." if released else "Windows could not release the shortcut. Retry or exit NEXIS.", self.chord)
        if self.api is None:
            return RegistrationResult(False, "Global shortcuts require Windows. Ctrl+K works inside NEXIS.", "")
        if self.chord == chord and self.identifier is not None:
            return RegistrationResult(True, "Global launcher active: " + chord, self.chord)
        candidate = 0x4E31 if self.identifier != 0x4E31 else 0x4E32
        modifiers, virtual_key = HOTKEYS[chord]
        if not self.api.RegisterHotKey(None, candidate, modifiers | MOD_NOREPEAT, virtual_key):
            return RegistrationResult(False, "Windows could not register " + chord + "; another app or input method may be using it. Choose another shortcut. Ctrl+K remains available inside NEXIS.", self.chord)
        previous = self.identifier
        if previous is not None and not self.api.UnregisterHotKey(None, previous):
            self.api.UnregisterHotKey(None, candidate)
            return RegistrationResult(False, "Windows could not release the previous shortcut. Previous selection retained; retry or exit NEXIS.", self.chord)
        self.identifier, self.chord = candidate, chord
        return RegistrationResult(True, "Global launcher active: " + chord, chord)

    def stop(self):
        if self.identifier is not None:
            if not self.api.UnregisterHotKey(None, self.identifier):
                return False
            self.identifier, self.chord = None, ""
        return True
