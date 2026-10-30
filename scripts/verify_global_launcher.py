"""Native Windows shortcut lifecycle/dispatch probe. Does not inject keyboard input."""

import argparse
import ctypes
import json
import os
from pathlib import Path
from threading import Thread

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

from nexis.platform.hotkeys import HotkeyRegistration, HOTKEYS, WM_HOTKEY
from nexis.ui.global_launcher import GlobalLauncher


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    if os.name != "nt":
        raise SystemExit("This probe requires Windows.")
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    calls, contenders = [], []
    registration = HotkeyRegistration()
    launcher = GlobalLauncher(lambda: calls.append("activated"), registration)
    result = launcher.configure("Ctrl+Alt+K", True)
    report = {"registration_ok": result.ok, "registration_message": result.message,
              "physical_keyboard_verified": False, "cursor_changes": False}
    try:
        if result.ok:
            def contend():
                other = HotkeyRegistration()
                contender = other.configure("Ctrl+Alt+K")
                contenders.append({"ok": contender.ok, "message": contender.message})
                other.stop()

            thread = Thread(target=contend)
            thread.start()
            thread.join(3)
            if thread.is_alive():
                raise RuntimeError("Competing registration did not finish")
            report["competing_thread_registration"] = contenders
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            from ctypes import wintypes

            user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
            user32.PostThreadMessageW.restype = wintypes.BOOL
            kernel32.GetCurrentThreadId.restype = wintypes.DWORD
            modifiers, key = HOTKEYS["Ctrl+Alt+K"]
            posted = user32.PostThreadMessageW(kernel32.GetCurrentThreadId(), WM_HOTKEY, registration.identifier, modifiers | key << 16)
            report["test_message_posted_to_own_thread"] = bool(posted)
            loop = QEventLoop()
            QTimer.singleShot(500, loop.quit)
            loop.exec()
            report["native_dispatch_callbacks"] = len(calls)
    finally:
        report["unregistered"] = launcher.stop()
    report["passed_available_checks"] = bool(result.ok and contenders and not contenders[0]["ok"] and len(calls) == 1 and report["unregistered"])
    (args.output / "native-launcher.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["passed_available_checks"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
