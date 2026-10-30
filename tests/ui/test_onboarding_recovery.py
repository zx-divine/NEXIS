import sqlite3
from threading import Event
from types import SimpleNamespace

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWizard

from nexis.storage.database import Database
from nexis.ui.branding import WelcomeWizard
from nexis.ui.main_window import MainWindow


def advance(qtbot, wizard):
    qtbot.mouseClick(wizard.button(QWizard.NextButton), Qt.LeftButton)


@pytest.mark.parametrize("persisted", [False, True])
@pytest.mark.parametrize("keyboard", [False, True])
def test_actual_acknowledgment_navigation(qtbot, tmp_path, persisted, keyboard):
    db = Database(tmp_path / "fresh.db")
    db.set_setting("system_access_acknowledged", persisted)
    wizard = WelcomeWizard(db)
    qtbot.addWidget(wizard)
    wizard.show()
    wizard.preferred_name.setText("Recovery fixture")
    advance(qtbot, wizard)
    advance(qtbot, wizard)
    assert wizard.currentId() == 2
    if not persisted:
        assert not wizard.button(QWizard.NextButton).isEnabled()
        assert "Required" in wizard.access_page.subTitle()
        wizard.access.acknowledged.setFocus()
        qtbot.keyClick(wizard.access.acknowledged, Qt.Key_Space)
    assert wizard.button(QWizard.NextButton).isEnabled()
    if keyboard:
        wizard.button(QWizard.NextButton).setFocus()
        qtbot.keyClick(wizard.button(QWizard.NextButton), Qt.Key_Return)
    else:
        advance(qtbot, wizard)
    assert wizard.currentId() == 3
    assert not any(field.isChecked() for field in wizard.access.choices.values())
    wizard.reject()
    db.close()


def test_interruption_resume_and_restart_keep_optional_grants_off(qtbot, tmp_path, platform, monkeypatch):
    db = Database(tmp_path / "fresh.db")
    monkeypatch.setattr("nexis.ui.branding.detect_model", lambda *args: None)
    wizard = WelcomeWizard(db)
    qtbot.addWidget(wizard)
    wizard.show()
    wizard.preferred_name.setText("ASH")
    advance(qtbot, wizard)
    advance(qtbot, wizard)
    wizard.access.acknowledged.setChecked(True)
    advance(qtbot, wizard)
    assert wizard.currentId() == 3
    assert wizard.model_button.isEnabled()  # Missing optional speech model cannot trap Manual mode.
    wizard.reject()
    assert not db.setting("welcome_completed")
    assert not db.setting("system_access_acknowledged")
    resumed = WelcomeWizard(db)
    qtbot.addWidget(resumed)
    resumed.show()
    assert resumed.currentId() == 3
    assert resumed.preferred_name.text() == "ASH"
    while resumed.currentId() < 5:
        advance(qtbot, resumed)
    advance(qtbot, resumed)
    assert resumed.currentId() == 5 and "Save a provider" in resumed.api_status.text()
    resumed.api_setup_choice.setCurrentIndex(resumed.api_setup_choice.findData("later"))
    while resumed.currentId() < 8:
        advance(qtbot, resumed)
    commits = []
    original = db.set_settings

    def commit(values):
        commits.append(values)
        original(values)

    monkeypatch.setattr(db, "set_settings", commit)
    for _ in range(10):
        resumed.accept()
    assert len(commits) == 1 and resumed.result() == QWizard.Accepted
    assert db.setting("onboarding_progress") == {}
    assert not any(db.setting("access_permissions").values())
    window = MainWindow(db, tmp_path, platform)
    window.show_launch_mode()
    assert window.stack.currentIndex() == window.pages["Welcome"]
    assert set(window.welcome.mode_buttons) == {"voice", "chat", "manual"}
    window.close()
    db.close()
    reopened = Database(tmp_path / "fresh.db")
    assert reopened.setting("welcome_completed") and reopened.setting("preferred_name") == "ASH"
    reopened.close()


def test_completion_write_failure_preserves_profile_and_allows_retry(qtbot, db, monkeypatch):
    wizard = WelcomeWizard(db)
    qtbot.addWidget(wizard)
    wizard.show()
    wizard.preferred_name.setText("ASH")
    wizard.api_setup_choice.setCurrentIndex(wizard.api_setup_choice.findData("later"))
    original = db.set_settings
    monkeypatch.setattr(db, "set_settings", lambda values: (_ for _ in ()).throw(sqlite3.OperationalError("fixture")))
    wizard.accept()
    assert not db.setting("welcome_completed")
    assert not db.setting("preferred_name")
    assert not wizard._closing_setup
    monkeypatch.setattr(db, "set_settings", original)
    wizard.accept()
    assert db.setting("welcome_completed")


def test_settings_batch_is_atomic(db):
    with pytest.raises(ValueError):
        db.set_settings({"welcome_completed": True, "preferred_name": ""})
    assert not db.setting("welcome_completed")


def test_complete_keyboard_only_progression(qtbot, tmp_path):
    db = Database(tmp_path / "keyboard.db")
    wizard = WelcomeWizard(db)
    qtbot.addWidget(wizard)
    wizard.show()
    wizard.preferred_name.setFocus()
    qtbot.keyClicks(wizard.preferred_name, "ASH")
    for target in range(1, 9):
        if wizard.currentId() == 2:
            wizard.access.acknowledged.setFocus()
            qtbot.keyClick(wizard.access.acknowledged, Qt.Key_Space)
        if wizard.currentId() == 5:
            wizard.api_setup_choice.setFocus()
            qtbot.keyClick(wizard.api_setup_choice, Qt.Key_End)
        wizard.button(QWizard.NextButton).setFocus()
        qtbot.keyClick(wizard.button(QWizard.NextButton), Qt.Key_Return)
        assert wizard.currentId() == target
    wizard.button(QWizard.FinishButton).setFocus()
    qtbot.keyClick(wizard.button(QWizard.FinishButton), Qt.Key_Return)
    assert db.setting("welcome_completed")
    db.close()


def test_completed_setup_shows_all_modes_and_keeps_future_launch_preference(qtbot, db, tmp_path, platform):
    db.set_setting("default_launch_mode", "chat")
    window = MainWindow(db, tmp_path, platform)
    qtbot.addWidget(window)
    window.onboarding_finished()
    assert window.stack.currentIndex() == window.pages["Welcome"]
    assert set(window.welcome.mode_buttons) == {"voice", "chat", "manual"}
    assert db.setting("default_launch_mode") == "chat"
    window.show_launch_mode()
    assert window.stack.currentIndex() == window.pages["Chat"]
    window.close()


def test_pending_finish_rechecks_consent_after_worker_stops(qtbot, db):
    wizard = WelcomeWizard(db)
    qtbot.addWidget(wizard)
    wizard.show()
    wizard.preferred_name.setText("ASH")
    wizard.api_setup_choice.setCurrentIndex(wizard.api_setup_choice.findData("later"))
    running = [True]
    task = SimpleNamespace(cancel=Event(), isRunning=lambda: running[0])
    wizard.jobs.append(task)
    wizard.accept()
    assert wizard._closing_setup and task.cancel.is_set()
    for _ in range(10):
        wizard.accept()
    wizard.access.acknowledged.setChecked(False)
    running[0] = False
    qtbot.waitUntil(lambda: not wizard._closing_setup)
    assert not db.setting("welcome_completed")
    wizard.access.acknowledged.setChecked(True)
    wizard.accept()
    assert db.setting("welcome_completed")


@pytest.mark.parametrize("persisted", [False, True])
def test_saved_capabilities_never_invert_consent_gate(qtbot, tmp_path, persisted):
    db = Database(tmp_path / "selected-permissions.db")
    db.set_setting("system_access_acknowledged", persisted)
    db.set_setting("access_permissions", {
        key: key != "terminal_commands" for key in db.setting("access_permissions")
    })
    wizard = WelcomeWizard(db)
    qtbot.addWidget(wizard)
    wizard.show()
    wizard.preferred_name.setText("Consent regression")
    advance(qtbot, wizard)
    advance(qtbot, wizard)
    for checked in (False, True, False, True):
        wizard.access.acknowledged.setChecked(checked)
        assert wizard.button(QWizard.NextButton).isEnabled() == checked
        if checked:
            advance(qtbot, wizard)
            assert wizard.currentId() == 3
            wizard.back()
            assert wizard.currentId() == 2
        else:
            advance(qtbot, wizard)
            assert wizard.currentId() == 2
            assert "Required" in wizard.access_page.subTitle()
        assert all(field.isChecked() for field in wizard.access.choices.values() if field.isEnabled())
    wizard.reject()
    db.close()
