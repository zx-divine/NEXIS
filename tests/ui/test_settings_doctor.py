from threading import Event
from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QApplication

from nexis.core.results import Result
from nexis.ui.main_window import MainWindow


@pytest.fixture
def window(qtbot, db, tmp_path, platform):
    widget = MainWindow(db, tmp_path, platform)
    qtbot.addWidget(widget)
    widget.show()
    yield widget
    widget.close()
    qtbot.waitUntil(lambda: not any(job and job.isRunning() for job in widget.background_jobs()), timeout=10000)


def test_gear_category_navigation_and_persistence(window, qtbot, db):
    window.settings_button.click()
    assert window.navigation.currentText() == "Settings"
    for category in window.settings_page.section_indices:
        window.open_settings(category)
        assert window.settings_page.categories.currentText() == category
    window.open_settings("General")
    window.settings_page.minimize_to_tray.setChecked(True)
    window.settings_page.save()
    assert db.setting("minimize_to_tray")
    assert not db.setting("floating_orb_enabled")
    assert not window.voice.worker and not window.ai_jobs


def test_doctor_is_explicit_offline_and_export_excludes_notes(window, qtbot, tmp_path, monkeypatch):
    page = window.doctor
    assert not page.jobs and page.report is None
    window.navigate("NEXIS Doctor")
    assert not page.jobs  # Merely navigating never starts diagnostics.
    page.run_checks()
    qtbot.waitUntil(lambda: page.report is not None, timeout=15000)
    assert page.report["network_requests_in_this_check"] == 0
    assert "USER ACTION REQUIRED" in page.results.toPlainText()
    assert not window.voice.worker and not window.ai_jobs
    destination = tmp_path / "doctor-report.json"
    monkeypatch.setattr("nexis.ui.doctor_page.QFileDialog.getSaveFileName", lambda *args: (str(destination), ""))
    # The test's tmp_path is also the application data directory: it is rejected.
    page.export()
    assert not destination.exists() and "outside" in page.status.text()


def test_natural_website_chat_works_without_provider_and_has_no_cloud_history(window, qtbot, platform, monkeypatch):
    monkeypatch.setattr("nexis.ui.main_window.start_chat", lambda *args: pytest.fail("No cloud planner for a single website"))
    window.conversation_request("NEXIS, open GitHub.", "chat")
    qtbot.waitUntil(lambda: window.worker is not None and not window.worker.isRunning())
    qtbot.waitUntil(lambda: window.execute.isEnabled())
    assert platform.calls[-1] == ("website", "https://github.com")
    assert not window.conversation_history


def test_natural_memory_commands_and_off_switch_never_leak_into_later_context(window, monkeypatch):
    seen = []
    monkeypatch.setattr("nexis.ui.main_window.start_chat", lambda window, text, origin: seen.extend(window.conversation_history))
    window.conversation_request("Remember I prefer dark mode.", "chat")
    assert "dark mode" in window.memories.body.toPlainText()
    assert not window.memories.store.search()
    window.memories.save()
    window.memories.enabled.setChecked(False)
    window.conversation_request("Show my saved memories.", "chat")
    assert window.navigation.currentText() == "Local Memory"
    assert len(window.memories.store.search()) == 1
    window.conversation_request("Explain Python", "chat")
    assert seen == [{"role": "user", "content": "Explain Python"}]


def test_cancelled_queued_clipboard_result_does_not_apply_or_speak(window, monkeypatch):
    clipboard = QApplication.clipboard()
    clipboard.setText("existing")
    cancel = Event()
    cancel.set()
    worker = SimpleNamespace(cancel=cancel, isRunning=lambda: False)
    window.worker = worker
    window.origin = "voice"
    monkeypatch.setattr(window.voice, "receive_reply", lambda *args: pytest.fail("No late voice playback"))
    window.result(Result(True, "Snippet ready for clipboard", {"clipboard": "must not be delivered"}))
    assert clipboard.text() == "existing"
    window.worker = None
    clipboard.clear()


def test_leaving_voice_settings_stops_hidden_calibration(window, monkeypatch):
    stopped = []
    monkeypatch.setattr(window.settings_page.voice_setup.microphone, "stop", lambda: stopped.append(True))
    window.open_settings("Voice")
    window.settings_page.open_section("General")
    assert stopped


def test_always_active_orb_topmost_and_muted_state_are_persistent(window, db, monkeypatch):
    from PySide6.QtCore import Qt
    monkeypatch.setattr("nexis.ui.desktop_page.notification_state", lambda: 5)
    desktop = window.desktop_experience
    desktop.enabled.setChecked(True)
    assert desktop.orb.windowFlags() & Qt.WindowStaysOnTopHint
    desktop.always_on_top.setChecked(False)
    assert not db.setting("orb_always_on_top")
    assert not desktop.orb.windowFlags() & Qt.WindowStaysOnTopHint
    window.set_microphone_muted(True)
    assert "HARD MUTED" in desktop.orb.caption.text()
    assert not window.voice.worker
