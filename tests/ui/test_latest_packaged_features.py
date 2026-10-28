from nexis.diagnostics import latest_feature_check
from nexis.ui.main_window import MainWindow


def test_packaged_latest_feature_probe_exercises_current_ui_and_storage(qtbot, db, tmp_path, platform):
    db.set_setting("welcome_completed", True)
    db.set_setting("preferred_name", "Package verification")
    db.set_setting('ai_setup_choice', 'later')
    db.set_setting("access_permissions", {})
    window = MainWindow(db, tmp_path, platform)
    qtbot.addWidget(window)
    window.show()
    result = latest_feature_check(window, db)
    assert len(result) == 9 and set(result.values()) == {"PASS"}
    assert not platform.calls and not window.voice.worker and not window.ai_jobs
    window.close()
