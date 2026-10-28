import pytest
from PySide6.QtCore import Qt, QThread
from PySide6.QtWidgets import QApplication
from nexis.ui.main_window import MainWindow
from nexis.ui.reactor import ReactorState, ReactorWidget
from nexis.ui import dialogs
from nexis.storage.repository import Repository


@pytest.fixture
def hud(qtbot, db, tmp_path, platform, monkeypatch):
    from nexis.core.provider_manager import ProviderManager

    manager = ProviderManager(tmp_path)
    selected = manager.save(
        {
            "provider": "Compatible gateway",
            "endpoint": "http://127.0.0.1:20128/v1",
            "model": "fixture",
            "key": "fixture",
        }
    )
    manager.select(selected)

    def plan(profile, messages, cancel, **kwargs):
        import json

        request = next(m["content"] for m in reversed(messages) if m["role"] == "user").split(
            "\nOwner-approved context:"
        )[0]
        name = (
            "trusted" if "trusted" in request else "notepad & calc" if "&" in request else "notepad"
        )
        return {
            "text": json.dumps(
                {
                    "message": "",
                    "steps": [{"tool": "app_open", "arguments": {"name": name}}],
                    "needs_more": False,
                }
            ),
            "calls": [],
        }

    monkeypatch.setattr("nexis.core.operator.generate", plan)
    widget = MainWindow(db, tmp_path, platform)
    qtbot.addWidget(widget)
    widget.show()
    yield widget
    for worker in (widget.worker, widget.files.worker, widget.voice.worker):
        if worker:
            worker.cancel.set()
            if hasattr(worker, "respond"):
                worker.respond(False)
            worker.wait(3000)
    widget.close()


def test_reactor_states_timing_and_accessibility(qtbot):
    reactor = ReactorWidget()
    qtbot.addWidget(reactor)
    reactor.resize(450, 450)
    reactor.show()
    assert reactor.timer.isActive()
    for state in ReactorState:
        reactor.set_state(state)
        assert reactor.state == state
        assert not reactor.grab().isNull()
    reactor.set_state(ReactorState.LISTENING)
    assert reactor.audio_level is None
    reactor.set_audio_level(0.5)
    assert reactor.audio_level == 0.5
    with qtbot.waitSignal(reactor.activated):
        qtbot.keyClick(reactor, Qt.Key_Return)
    phase = reactor.phase
    qtbot.waitUntil(lambda: reactor.phase != phase, timeout=1000)
    reactor.set_reduced_motion(True)
    phase = reactor.phase
    qtbot.wait(100)
    assert not reactor.timer.isActive() and reactor.phase == phase
    reactor.set_reduced_motion(False)
    reactor.hide()
    assert not reactor.timer.isActive()
    reactor.show()
    assert reactor.timer.isActive()
    reactor.set_paused(True)
    assert not reactor.timer.isActive()


@pytest.mark.parametrize("size", [(1366, 768), (1600, 900), (1920, 1080)])
def test_dashboard_layout_and_deck(hud, qtbot, size):
    hud.navigate("Dashboard")
    hud.resize(*size)
    QApplication.processEvents()
    for button in (hud.chat_button, hud.voice_button, hud.manual_button):
        assert button.isVisible() and button.width() > 200
        assert button.mapTo(hud, button.rect().bottomRight()).y() < hud.height()
    assert hud.reactor.isVisible() and hud.reactor.width() > 300
    assert hud.left_wing.isVisible() and hud.right_wing.isVisible()
    qtbot.mouseClick(hud.chat_button, Qt.LeftButton)
    assert hud.stack.currentIndex() == hud.pages["Chat"]
    hud.navigate("Dashboard")
    qtbot.mouseClick(hud.voice_button, Qt.LeftButton)
    assert hud.stack.currentIndex() == hud.pages["Voice Chat"]
    assert hud.voice.worker is None  # Navigation must never enable the microphone.
    qtbot.mouseClick(hud.mode_switches["Dashboard"], Qt.LeftButton)
    assert hud.drawer.isVisible() and hud.reactor.isVisible()
    qtbot.keyClick(hud, Qt.Key_Escape)
    assert not hud.drawer.isVisible()


def test_chat_executes_and_returns_results(hud, qtbot, platform):
    hud.navigate("Chat")
    hud.chat.input.setText("please open notepad")
    qtbot.keyClick(hud.chat.input, Qt.Key_Return)
    qtbot.waitUntil(lambda: hud.execute.isEnabled(), timeout=5000)
    assert platform.calls == [("launch", "notepad", True)]
    assert "Launch request accepted" in hud.chat.messages.item(hud.chat.messages.count() - 1).text()
    assert hud.stack.currentIndex() == hud.pages["Chat"]
    hud.chat.messages.setCurrentRow(hud.chat.messages.count() - 1)
    hud.chat.copy_message()
    assert "Launch request" in QApplication.clipboard().text()
    QApplication.clipboard().clear()
    hud.chat.messages.clear()
    assert hud.chat.messages.count() == 0


@pytest.mark.parametrize("origin", ["chat", "voice"])
def test_new_entry_points_enforce_permissions(
    hud, db, qtbot, platform, monkeypatch, tmp_path, origin
):
    path = tmp_path / "trusted.exe"
    path.touch()
    Repository(db).save_shortcut("trusted", "application", str(path))
    requests = []
    monkeypatch.setattr(
        dialogs, "confirm", lambda parent, preview: requests.append(preview) or False
    )
    hud.navigate("Chat" if origin == "chat" else "Voice Chat")
    if origin == "voice":
        hud.voice.transcript.setText("open trusted")
        hud.voice.submit_transcript()
    else:
        hud.conversation_request("please open trusted", origin)
    qtbot.waitUntil(lambda: hud.execute.isEnabled(), timeout=5000)
    assert requests and not platform.calls
    assert hud.assistant_state == ReactorState.ERROR
    assert "DENIED" in hud.permission_status.text()


@pytest.mark.parametrize("origin", ["chat", "voice"])
def test_shell_input_cannot_bypass_engine(hud, qtbot, platform, origin):
    hud.conversation_request("open notepad & calc", origin)
    qtbot.waitUntil(lambda: hud.execute.isEnabled(), timeout=5000)
    assert not platform.calls
    assert hud.assistant_state == ReactorState.ERROR


def test_voice_unavailable_is_honest_and_inactive(hud, qtbot, monkeypatch):
    monkeypatch.setattr(
        "nexis.ui.conversation.setup_status",
        lambda path: (False, "Install optional offline voice dependencies"),
    )
    hud.voice.refresh_setup()
    hud.navigate("Voice Chat")
    assert not hud.voice.push.isEnabled()
    assert "optional" in hud.voice.status.text()
    assert hud.voice.worker is None
    assert hud.voice.reactor.state == ReactorState.IDLE
    hud.voice.return_to_hud()
    assert hud.stack.currentIndex() == hud.pages["Dashboard"]


def test_voice_stop_on_navigation_and_shutdown(hud, qtbot, monkeypatch):
    class Capture(QThread):
        def __init__(self):
            super().__init__()
            from threading import Event

            self.cancel = Event()

        def run(self):
            self.cancel.wait(3)

    capture = Capture()
    hud.voice.worker = capture
    capture.start()
    qtbot.waitUntil(capture.isRunning)
    hud.navigate("Dashboard")
    assert capture.cancel.is_set()
    assert capture.wait(1000)
    hud.close()
    assert not hud.sensor_timer.isActive()
    assert not hud.reactor.timer.isActive()


def test_reduced_motion_settings_and_minimize(hud, db, qtbot):
    hud.settings_page.reduced.setChecked(True)
    hud.settings_page.fps.setValue(15)
    hud.settings_page.save()
    assert db.setting("reduced_motion") and db.setting("animation_fps") == 15
    assert not hud.reactor.timer.isActive() and not hud.radar.timer.isActive()
    hud.settings_page.reduced.setChecked(False)
    hud.settings_page.save()
    hud.navigate("Dashboard")
    hud.showMinimized()
    QApplication.processEvents()
    assert not hud.sensor_timer.isActive() and not hud.reactor.timer.isActive()
    hud.showNormal()
    QApplication.processEvents()
    assert hud.sensor_timer.isActive() and hud.reactor.timer.isActive()


def test_full_screen_has_escape(hud, qtbot):
    hud.toggle_fullscreen()
    assert hud.isFullScreen()
    hud.escape_action()
    assert not hud.isFullScreen()


def test_sensor_graph_has_no_synthetic_history(hud):
    hud.sensor_timer.stop()
    hud.system_graph.cpu.clear()
    hud.system_graph.memory.clear()
    assert len(hud.system_graph.cpu) == 0
    hud.sample_system()
    assert len(hud.system_graph.cpu) == 1


def test_reduced_motion_keeps_audio_core_static(qtbot):
    reactor = ReactorWidget()
    qtbot.addWidget(reactor)
    reactor.resize(450, 450)
    reactor.show()
    reactor.set_state(ReactorState.LISTENING)
    reactor.set_reduced_motion(True)
    reactor.set_audio_level(0)
    first = reactor.grab().toImage().copy(180, 180, 90, 90)
    reactor.set_audio_level(1)
    second = reactor.grab().toImage().copy(180, 180, 90, 90)
    assert first == second


def test_active_action_is_plain_text(hud, qtbot):
    hud.submit("<b>untrusted</b>")
    qtbot.waitUntil(lambda: hud.execute.isEnabled(), timeout=5000)
    assert hud.active_command.textFormat() == Qt.PlainText


def test_snippet_editor_rejects_rich_paste(hud, qtbot):
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QTextEdit

    seen = []

    def inspect():
        dialog = QApplication.activeModalWidget()
        editor = dialog.findChild(QTextEdit)
        seen.append(editor.acceptRichText())
        dialog.reject()

    QTimer.singleShot(20, inspect)
    assert dialogs.edit(hud, "Plain text", {"Text": "example"}, ("Text",)) is None
    assert seen == [False]
