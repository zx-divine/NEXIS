import pytest
from PySide6.QtWidgets import QApplication
from nexis.core.themes import THEMES
from nexis.ui.main_window import MainWindow
from nexis.ui.reactor import ReactorState
from nexis.ui.themes import current


@pytest.fixture
def window(qtbot, db, tmp_path, platform):
    widget = MainWindow(db, tmp_path, platform)
    qtbot.addWidget(widget)
    widget.show()
    yield widget
    widget.close()


@pytest.mark.parametrize("theme", list(THEMES))
def test_running_theme_preview_repaints_hud_and_orb_without_saving(window, db, theme, qtbot):
    db.set_setting("reduced_motion", True)
    window.desktop_experience.enabled.setChecked(True)
    window.apply_theme()
    window.navigate("Settings")
    window.settings_page.open_section("Desktop & Appearance")
    panel = window.settings_page.appearance
    panel.theme.setCurrentIndex(panel.theme.findData(theme))
    assert panel.preview()
    qtbot.wait(20)
    assert db.setting("theme") == "og"
    assert "@background" not in QApplication.instance().styleSheet()
    assert current()["text"] == QApplication.instance().palette().windowText().color().name().upper()
    assert not window.reactor.timer.isActive()
    assert not window.desktop_experience.orb.reactor.timer.isActive()
    for reactor in (window.reactor, window.voice.reactor, window.desktop_experience.orb.reactor):
        for state in (ReactorState.IDLE, ReactorState.ERROR, ReactorState.SUCCESS):
            reactor.set_state(state)
            assert not reactor.grab().isNull()
    panel.save()
    assert db.setting("theme") == theme
    panel.reset()
    assert db.setting("theme") == theme
    panel.revert()
    assert panel.theme.currentData() == theme


def test_invalid_custom_preview_keeps_current_palette_and_saved_preferences(window, db):
    panel = window.settings_page.appearance
    panel.theme.setCurrentIndex(panel.theme.findData("custom"))
    previous = dict(current())
    panel.colors["text"].setText("#080304")
    assert not panel.preview()
    panel.save()
    assert current() == previous
    assert db.setting("theme") == "og"
    assert "4.5" in panel.status.text()


def test_live_switch_invalidates_static_reactor_cache(window):
    window.reactor.grab()
    old = window.reactor.static_geometry(250).toImage()
    window.apply_theme("arctic")
    assert window.reactor.static_geometry(250).toImage() != old
    assert QApplication.instance().palette().window().color().lightness() > 200


def test_general_save_keeps_unsaved_appearance_preview(window, db):
    panel = window.settings_page.appearance
    panel.theme.setCurrentIndex(panel.theme.findData("cyber"))
    expected = dict(current())
    window.settings_page.reduced.setChecked(True)
    window.settings_page.save()
    assert current() == expected
    assert db.setting("theme") == "og"
    assert not window.reactor.timer.isActive()
