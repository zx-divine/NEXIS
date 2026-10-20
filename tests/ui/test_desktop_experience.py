from threading import Event
from types import SimpleNamespace

from PySide6.QtCore import QPoint, QRect, QSize

from nexis.ui.main_window import MainWindow
from nexis.ui.orb import clamp_position
from nexis.ui.setup_services import start_chat


def test_no_default_orb_microphone_or_update_request(qtbot, db, tmp_path, platform):
    window = MainWindow(db, tmp_path, platform)
    qtbot.addWidget(window)
    assert window.desktop_experience.orb is None
    assert not window.desktop_experience.timer.isActive()
    assert not window.updates_page.automatic.isChecked() and not window.updates_page.jobs
    assert not window.voice.worker and not window.screen_awareness.image
    assert not window.updates_page.download_button.isEnabled()
    window.close()


def test_orb_visibility_policy_reduced_motion_and_repeated_hide_show_never_capture(qtbot, db, tmp_path, platform, monkeypatch):
    state = [5]
    monkeypatch.setattr("nexis.ui.desktop_page.notification_state", lambda: state[0])
    window = MainWindow(db, tmp_path, platform)
    qtbot.addWidget(window)
    desktop = window.desktop_experience
    desktop.enabled.setChecked(True)
    assert desktop.orb.isVisible() and not window.voice.worker
    db.set_setting("reduced_motion", True)
    window.apply_theme()
    assert not desktop.orb.reactor.timer.isActive()
    for _ in range(20):
        desktop.hide_orb()
        assert not desktop.timer.isActive()
        desktop.show_orb()
    for blocked in (1, 2, 3, 4, 6, 7, None):
        state[0] = blocked
        desktop.refresh_visibility()
        assert not desktop.orb.isVisible() and not desktop.orb.reactor.timer.isActive()
    state[0] = 5
    desktop.refresh_visibility()
    assert desktop.orb.isVisible() and not window.voice.worker
    desktop.enabled.setChecked(False)
    assert not desktop.orb.isVisible() and not desktop.timer.isActive()
    window.close()


def test_monitor_clamping_handles_negative_coordinates_and_removed_monitors():
    left = SimpleNamespace(availableGeometry=lambda: QRect(-1920, 0, 1920, 1040))
    main = SimpleNamespace(availableGeometry=lambda: QRect(0, 0, 1366, 728))
    assert clamp_position(QPoint(-100, 1000), QSize(220, 280), [left, main]) == QPoint(-220, 760)
    assert clamp_position(QPoint(9999, 9999), QSize(220, 280), [main]) == QPoint(1146, 448)
    assert clamp_position(QPoint(-500, 100), QSize(220, 280), [main]) == QPoint(0, 100)


def test_manual_and_ai_requests_do_not_overlap(qtbot, db, tmp_path, platform):
    window = MainWindow(db, tmp_path, platform)
    qtbot.addWidget(window)
    busy = SimpleNamespace(isRunning=lambda: True, cancel=Event())
    window.ai_jobs.append(busy)
    window.submit("open notepad")
    assert window.worker is None and not platform.calls
    window.ai_jobs.clear()
    window.worker = busy
    start_chat(window, "hello", "chat")
    assert not window.ai_jobs and not platform.calls
    window.worker = None
    window.close()


def test_update_automatic_check_is_daily_opt_in_and_downloads_stay_disabled_without_releases(qtbot, db, tmp_path, platform, monkeypatch):
    window = MainWindow(db, tmp_path, platform)
    qtbot.addWidget(window)
    page, calls = window.updates_page, []
    monkeypatch.setattr("nexis.ui.updates_page.check_updates", lambda cancel: calls.append(1) or {"available": False, "tag": "", "page": "", "notes": "No release", "assets": []})
    page.auto_check_if_due()
    assert not calls
    page.automatic.setChecked(True)
    page.auto_check_if_due()
    qtbot.waitUntil(lambda: bool(page.release), timeout=3000)
    page.auto_check_if_due()
    assert calls == [1] and not page.download_button.isEnabled()
    window.close()
