from datetime import datetime, timedelta, timezone
from threading import Event
from types import SimpleNamespace

import pytest

from nexis.core.update_service import Release, UpdateError
from nexis.ui.main_window import MainWindow


@pytest.fixture
def window(qtbot, db, tmp_path, platform):
    widget = MainWindow(db, tmp_path, platform)
    qtbot.addWidget(widget)
    widget.show()
    yield widget
    widget.close()
    qtbot.waitUntil(lambda: not any(job and job.isRunning() for job in widget.background_jobs()), timeout=10000)


def candidate():
    return Release("1.1.1", "1.4.3", "v1.1.1", "NEXIS-1.1.1-1.4.3-Windows-x64-Setup.exe",
                   "Signed release notes\n<no HTML execution>", 1024 * 1024)


def test_general_controls_share_preferences_and_preserve_prior_opt_out(window, db):
    panel = window.settings_page.software_updates
    assert panel.automatic.isChecked() and panel.downloads.isChecked()
    panel.automatic.setChecked(False)
    panel.downloads.setChecked(False)
    assert not db.setting("update_checks_enabled") and not db.setting("update_downloads_enabled")
    assert not window.updates_page.automatic.isChecked()
    assert not panel.restart_button.isVisible()


def test_manual_check_works_with_automatic_disabled_and_repeat_startup_is_bounded(window, qtbot, monkeypatch, db):
    page, calls = window.updates_page, []
    monkeypatch.setattr(page.service, "check", lambda cancel: calls.append(1) and None)
    page.automatic.setChecked(False)
    page.check()
    qtbot.waitUntil(lambda: bool(calls) and not page.busy())
    assert "up to date" in page.status.text()
    page.auto_check_if_due()
    assert calls == [1]
    page.automatic.setChecked(True)
    page.auto_check_if_due()
    assert calls == [1]
    db.set_setting("update_last_check", (datetime.now(timezone.utc) - timedelta(days=2)).isoformat())
    page.auto_check_if_due()
    qtbot.waitUntil(lambda: len(calls) == 2 and not page.busy())


def test_startup_automatically_checks_and_downloads_but_never_installs(window, qtbot, monkeypatch):
    page = window.updates_page
    monkeypatch.setattr(page.service, "check", lambda cancel: candidate())
    monkeypatch.setattr(page.service, "download", lambda release, cancel, progress: release)
    monkeypatch.setattr("nexis.ui.updates_page.WindowsInstaller", lambda *args: pytest.fail("Automatic installation"))
    page.start()
    qtbot.waitUntil(lambda: page.ready and not page.busy(), timeout=5000)
    assert page.notes.toPlainText() == candidate().notes
    assert page.restart_button.isEnabled()
    page.remind_later()
    assert not page.notice.isVisible()
    assert page.ready


def test_download_preference_progress_and_voice_restart_guard(window, monkeypatch):
    page = window.updates_page
    page.auto_download.setChecked(False)
    page.loaded(candidate())
    assert not page.pending_download and page.download_button.isEnabled()
    page.on_progress('{"transferred":524288,"total":1048576,"speed":262144}')
    assert page.progress.value() == 50 and "/s" in page.transfer.text()
    page.restored(candidate())
    window.voice.capture_active = True
    monkeypatch.setattr("nexis.ui.updates_page.WindowsInstaller", lambda *args: pytest.fail("Voice interrupted"))
    page.restart_install()
    assert "Finish active voice" in page.status.text()
    window.voice.capture_active = False


def test_offline_check_failure_keeps_app_usable_and_retry_succeeds(window, qtbot, monkeypatch):
    page = window.updates_page

    def offline(cancel):
        raise UpdateError("Offline fixture. Retry when connected.")

    monkeypatch.setattr(page.service, "check", offline)
    page.start()
    qtbot.waitUntil(lambda: "Offline fixture" in page.status.text() and not page.busy())
    assert not window.closing and window.settings_button.isEnabled()
    monkeypatch.setattr(page.service, "check", lambda cancel: None)
    page.check()
    qtbot.waitUntil(lambda: "up to date" in page.status.text() and not page.busy())


def test_running_work_defers_notifications_and_installer(window):
    page = window.updates_page
    worker = SimpleNamespace(isRunning=lambda: True, cancel=Event())
    window.ai_jobs.append(worker)
    page.auto_download.setChecked(False)
    page.loaded(candidate())
    assert page.notice is None
    page.restored(candidate())
    page.restart_install()
    assert "Finish active voice" in page.status.text()
    window.ai_jobs.clear()
    page.show_notice_if_idle()
    assert page.notice.isVisible()
