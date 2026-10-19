import pytest
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QDialog
from nexis.ui.main_window import MainWindow
from nexis.ui import dialogs
from nexis.core.results import Preview, Risk
from nexis.storage.repository import Repository


@pytest.fixture
def window(qtbot, db, tmp_path, platform):
    widget = MainWindow(db, tmp_path, platform)
    qtbot.addWidget(widget)
    widget.show()
    yield widget
    if widget.worker:
        widget.stop_command()
        widget.worker.wait(3000)
    if widget.files.worker:
        widget.files.cancel()
        widget.files.worker.wait(3000)


def test_navigation_sizes(window, qtbot):
    for size in [(820, 600), (1180, 790), (1440, 900)]:
        window.resize(*size)
        for name, index in window.pages.items():
            window.navigate(name)
            assert window.stack.currentIndex() == index
            assert window.stack.width() > 500
    window.focus_command()
    assert window.stack.currentIndex() == window.pages["Dashboard"]


def test_command_submission_and_errors(window, qtbot, platform):
    window.command.setText("open notepad")
    qtbot.keyClick(window.command, Qt.Key_Return)
    qtbot.waitUntil(lambda: window.execute.isEnabled(), timeout=5000)
    assert platform.calls == [("launch", "notepad", True)]
    window.submit("unknown command")
    qtbot.waitUntil(lambda: window.execute.isEnabled(), timeout=5000)
    assert "Unknown command" in window.output.toPlainText()


def test_clipboard_copy(window, qtbot, db):
    Repository(db).save_snippet("intro", "Test", "hello test")
    window.submit("copy intro")
    qtbot.waitUntil(lambda: window.execute.isEnabled(), timeout=5000)
    assert QApplication.clipboard().text() == "hello test"
    QApplication.clipboard().clear()


def test_permission_cancel_dialog(qtbot, window):
    def reject():
        dialog = QApplication.activeModalWidget()
        assert isinstance(dialog, QDialog)
        dialog.reject()

    QTimer.singleShot(20, reject)
    assert not dialogs.confirm(window, Preview("delete", "history", "erase", Risk.HIGH))


def test_sensitive_command_cancel(window, qtbot, db, monkeypatch):
    monkeypatch.setattr(dialogs, "confirm", lambda *args: False)
    db.record("help", True)
    window.submit("clear history")
    qtbot.waitUntil(lambda: window.execute.isEnabled(), timeout=5000)
    assert db.rows("SELECT * FROM history")
    assert "Cancelled" in window.output.toPlainText()


def test_settings_persistence(window, db):
    page = window.settings_page
    page.theme.setCurrentText("light")
    page.limit.setValue(12)
    page.history.setChecked(False)
    page.save()
    assert db.setting("theme") == "light"
    assert db.setting("history_limit") == 12
    assert not db.setting("history_enabled")


def test_async_file_search(window, qtbot, db, tmp_path):
    folder = tmp_path / "approved"
    folder.mkdir()
    (folder / "report.txt").touch()
    db.set_setting("search_roots", [str(folder)])
    window.files.query.setText("report")
    window.files.start()
    qtbot.waitUntil(lambda: window.files.start_button.isEnabled(), timeout=5000)
    assert window.files.results.count() == 1


def test_edit_snippet_and_delete(window, db, monkeypatch):
    page = next(p for p in window.resources if p.table_name == "snippets")
    monkeypatch.setattr(
        dialogs, "edit", lambda *a, **k: {"Name": "intro", "Category": "Work", "Text": "hello"}
    )
    page.add()
    assert db.rows("SELECT text FROM snippets")[0]["text"] == "hello"
    page.list.selectRow(0)
    monkeypatch.setattr(
        dialogs, "edit", lambda *a, **k: {"Name": "renamed", "Category": "Work", "Text": "updated"}
    )
    page.edit()
    assert db.rows("SELECT name FROM snippets")[0]["name"] == "renamed"
    page.list.selectRow(0)
    monkeypatch.setattr(dialogs, "confirm", lambda *a: False)
    page.delete()
    assert db.rows("SELECT * FROM snippets")
    monkeypatch.setattr(dialogs, "confirm", lambda *a: True)
    page.delete()
    assert not db.rows("SELECT * FROM snippets")


def test_replacement_requires_confirmation(window, db, monkeypatch):
    Repository(db).save_snippet("intro", "General", "original")
    page = next(p for p in window.resources if p.table_name == "snippets")
    monkeypatch.setattr(
        dialogs, "edit", lambda *a, **k: {"Name": "intro", "Category": "Work", "Text": "new"}
    )
    monkeypatch.setattr(dialogs, "confirm", lambda *a: False)
    page.add()
    assert db.rows("SELECT text FROM snippets")[0]["text"] == "original"


def test_permission_accept_dialog(qtbot, window):
    QTimer.singleShot(20, lambda: QApplication.activeModalWidget().accept())
    assert dialogs.confirm(window, Preview("open", "approved", "launch", Risk.MEDIUM))


def test_window_refuses_close_until_worker_finishes(window, qtbot, monkeypatch, platform):
    import time

    platform.launch = lambda *a, **k: time.sleep(0.2)
    window.submit("open notepad")
    window.close()
    assert window.isVisible()
    qtbot.waitUntil(lambda: window.execute.isEnabled(), timeout=5000)
