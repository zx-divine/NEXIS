from PySide6.QtWidgets import QMessageBox

from nexis.ui.main_window import MainWindow
from nexis.ui.workers import CommandWorker


def test_workflow_studio_is_optional_and_saves_only_after_review(qtbot, db, tmp_path, platform, monkeypatch):
    window = MainWindow(db, tmp_path, platform)
    qtbot.addWidget(window)
    studio = window.workflow_studio
    assert not studio.enabled.isChecked() and not studio.generate_button.isEnabled()
    studio.loaded(["open notepad", "open youtube"])
    assert not db.rows("SELECT * FROM workflows") and not platform.calls
    preview = []
    monkeypatch.setattr(QMessageBox, "information", lambda *args: preview.append(args[2]))
    studio.preview()
    assert "NO EXECUTION" in preview[0] and not platform.calls
    studio.title.setText("study")
    studio.save()
    assert db.rows("SELECT name FROM workflows")[0]["name"] == "study"
    assert not platform.calls
    studio.enabled.setChecked(True)
    assert db.setting("workflow_drafting_enabled")
    window.set_microphone_muted(True)
    assert not studio.jobs
    window.close()


def test_manual_approval_wait_is_bounded_and_late_acceptance_cannot_execute(db, platform, monkeypatch):
    ticks = iter([0, 1000])
    monkeypatch.setattr("nexis.ui.workers.monotonic", lambda: next(ticks))
    worker = CommandWorker(db, "open notepad", platform)
    assert not worker.confirm(None)
    assert worker.cancel.is_set() and not platform.calls


def test_old_permission_profiles_do_not_gain_screen_access(db):
    grants = db.setting("access_permissions")
    grants.pop("screen_capture")
    db.set_setting("access_permissions", grants)
    assert not db.setting("access_permissions")["screen_capture"]
