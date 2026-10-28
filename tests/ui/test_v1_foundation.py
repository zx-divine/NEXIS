from types import SimpleNamespace
from threading import Event

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWizard

from nexis.ui.branding import WelcomeWizard
from nexis.ui.main_window import MainWindow
from nexis.ui.reactor import ReactorState
from nexis.storage.database import Database


@pytest.fixture
def window(qtbot, db, tmp_path, platform):
    widget = MainWindow(db, tmp_path, platform)
    qtbot.addWidget(widget)
    widget.show()
    yield widget
    widget.close()
    qtbot.waitUntil(lambda: not any(job and job.isRunning() for job in widget.background_jobs()), timeout=10000)


def test_launch_is_personalized_three_mode_choice_and_preserves_native_frame(window, db):
    db.set_setting("preferred_name", "ASH <owner>")
    window.welcome.refresh()
    assert window.windowTitle() == "NEXIS"
    assert not window.windowFlags() & Qt.FramelessWindowHint
    assert window.stack.currentIndex() == window.pages["Welcome"]
    assert window.welcome.greeting.text() == "Welcome to NEXIS, ASH <owner>."
    assert window.welcome.greeting.textFormat() == Qt.PlainText
    assert set(window.welcome.mode_buttons) == {"voice", "chat", "manual"}
    assert window.settings_button.isVisible()
    assert not window.navigation.isVisible() and not window.deck.isVisible()
    assert not window.voice.worker and not window.ai_jobs
    assert window.reactor.cursor().shape() == Qt.ArrowCursor
    assert window.voice.reactor.cursor().shape() == Qt.ArrowCursor


def test_mode_switches_keep_context_and_stop_voice_without_recording(window):
    window.chat.input.setText("unfinished request")
    window.chat.add_message("YOU", "retained message")
    window.conversation_history.append({"role": "user", "content": "retained context"})
    for mode, page in (("voice", "Voice Chat"), ("chat", "Chat"), ("manual", "Dashboard")):
        window.welcome.mode_buttons[mode].click()
        assert window.stack.currentIndex() == window.pages[page]
        assert window.settings_button.isVisible()
    assert window.chat.input.text() == "unfinished request"
    assert "retained message" in window.chat.messages.item(window.chat.messages.count() - 1).text()
    assert window.conversation_history[-1]["content"] == "retained context"
    assert not window.voice.worker
    assert window.drawer.isVisible()


def test_settings_identity_and_launch_mode_are_persistent(window, db):
    page = window.settings_page
    assert page.category_order == ("General", "AI Providers", "Voice", "Appearance", "Permissions", "Memory and Privacy", "Integrations", "Advanced")
    page.preferred_name.setText("Ananya")
    page.launch_mode.setCurrentIndex(page.launch_mode.findData("chat"))
    page.save()
    assert db.setting("preferred_name") == "Ananya"
    window.show_launch_mode()
    assert window.stack.currentIndex() == window.pages["Chat"]
    assert "Ananya" in window.welcome.greeting.text()
    for title in page.category_order:
        window.open_settings(title)
        assert page.sections.currentIndex() == page.section_indices[title]


def test_real_mute_permission_and_connection_failures_drive_orb(window, db, monkeypatch):
    window.set_microphone_muted(True)
    assert window.reactor.state == ReactorState.MUTED
    assert window.voice.reactor.state == ReactorState.MUTED
    window.set_state("IDLE")
    assert window.reactor.state == ReactorState.MUTED
    window.set_microphone_muted(False)
    assert window.reactor.state == ReactorState.IDLE
    assert not window.voice.worker
    captured = []
    worker = SimpleNamespace(cancel=Event(), respond=captured.append, isRunning=lambda: False)
    window.worker = worker
    def confirm(*args):
        assert window.reactor.state == ReactorState.WAITING_PERMISSION
        return False
    monkeypatch.setattr("nexis.ui.main_window.dialogs.confirm", confirm)
    window.permission(object())
    assert captured == [False]
    window.worker = None
    window.ai_error("CONNECTION: Selected endpoint is unavailable.", "chat")
    assert window.reactor.state == ReactorState.OFFLINE
    window.ai_error("AUTHENTICATION: Check account configuration.", "chat")
    assert window.reactor.state == ReactorState.ERROR


def test_delayed_visual_settle_does_not_reopen_storage_or_run_during_shutdown(window, monkeypatch):
    window.set_state("SUCCESS")
    with monkeypatch.context() as scoped:
        scoped.setattr(window.db, "setting", lambda *args: pytest.fail("Delayed visuals must not read a possibly closed database"))
        window.settle_state()
        assert window.reactor.state == ReactorState.IDLE
    window.closing = True
    window.set_state("EXECUTING")
    assert window.reactor.state == ReactorState.IDLE
    window.closing = False


def test_onboarding_identity_screen_theme_completion_and_no_automatic_capture(qtbot, tmp_path):
    db = Database(tmp_path / "fresh.db")
    wizard = WelcomeWizard(db)
    qtbot.addWidget(wizard)
    wizard.show()
    assert not wizard.jobs and not wizard.microphone_worker and not wizard.speech
    for _ in range(2):
        wizard.next()
    assert wizard.currentId() == 0  # Name must be reviewed before proceeding.
    wizard.preferred_name.setText("ASH")
    wizard.next()
    wizard.next()
    assert wizard.currentId() == 2
    assert wizard.button(QWizard.CustomButton1).isVisible()
    assert not any(c.isChecked() for c in wizard.access.choices.values())
    wizard.access.acknowledged.setChecked(True)
    wizard.access.choices["screen_capture"].setChecked(True)
    wizard.screen_enabled.setChecked(True)
    wizard.appearance.theme.setCurrentIndex(wizard.appearance.theme.findData("cyber"))
    wizard.api_setup_choice.setCurrentIndex(wizard.api_setup_choice.findData('later'))
    assert db.setting("theme") == "og"
    wizard.accept()
    assert db.setting("welcome_completed")
    assert db.setting("preferred_name") == "ASH"
    assert db.setting("screen_awareness_enabled")
    assert db.setting("theme") == "cyber"
    db.close()


def test_onboarding_microphone_requires_explicit_grant_and_mute_is_immediate(qtbot, db):
    wizard = WelcomeWizard(db)
    qtbot.addWidget(wizard)
    wizard.access.choices["microphone_access"].setChecked(False)
    wizard.test_microphone()
    assert wizard.microphone_worker is None
    assert "Enable Microphone" in wizard.microphone.text()
    wizard.cancel_microphone()
    assert db.setting("microphone_muted")
    wizard.test_microphone()
    assert "Hard mute" in wizard.microphone.text()
    wizard.phrase_result("hey nexis can you hear me")
    assert "recognized locally" in wizard.mic_transcript.text()
    wizard.phrase_result("")
    assert "No speech" in wizard.mic_transcript.text()
    wizard.reject()
