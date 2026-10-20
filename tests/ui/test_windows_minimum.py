"""Unsupported Windows stops before opening any user storage or services."""

from types import SimpleNamespace

from PySide6.QtWidgets import QApplication

import nexis.main as entry


def test_unsupported_windows_gets_clear_error_before_user_data(qtbot, monkeypatch):
    messages = []
    monkeypatch.setattr(entry, "QApplication", lambda argv: QApplication.instance())
    monkeypatch.setattr(entry.sys, "getwindowsversion", lambda: SimpleNamespace(build=19044))
    monkeypatch.setattr(entry.QMessageBox, "critical", lambda parent, title, message: messages.append(message))
    monkeypatch.setattr(entry.QStandardPaths, "writableLocation", lambda *args: (_ for _ in ()).throw(AssertionError("No storage access on unsupported OS")))
    assert entry.main() == 1
    assert "19045" in messages[0] and "Windows 11" in messages[0]
