import ctypes
from ctypes import wintypes
from types import SimpleNamespace

from PySide6.QtCore import QByteArray

from nexis.ui.global_launcher import GlobalLauncher
from nexis.platform.hotkeys import WM_HOTKEY, RegistrationResult
from nexis.ui.main_window import MainWindow


def test_native_dispatch_only_accepts_registered_id_and_drops_queued_shutdown(qtbot):
    calls = []
    registration = SimpleNamespace(identifier=0x4E31, stop=lambda: True)
    launcher = GlobalLauncher(lambda: calls.append("activated"), registration)
    packet = wintypes.MSG()
    packet.message, packet.wParam = WM_HOTKEY, 0x4E31
    assert launcher.nativeEventFilter(QByteArray(b"windows_dispatcher_MSG"), ctypes.addressof(packet)) == (True, 0)
    qtbot.waitUntil(lambda: calls == ["activated"])
    packet.wParam = 23
    assert launcher.nativeEventFilter(QByteArray(b"windows_dispatcher_MSG"), ctypes.addressof(packet)) == (False, 0)
    packet.wParam = 0x4E31
    launcher.nativeEventFilter(QByteArray(b"windows_dispatcher_MSG"), ctypes.addressof(packet))
    launcher.stop()
    qtbot.wait(20)
    assert calls == ["activated"]


def test_command_launcher_preserves_context_never_records_and_releases_on_close(qtbot, db, tmp_path, platform):
    window = MainWindow(db, tmp_path, platform)
    qtbot.addWidget(window)
    window.show()
    window.chat.input.setText("preserved draft")
    window.launch_command_bar()
    assert window.stack.currentIndex() == window.pages["Dashboard"]
    assert not window.drawer.isHidden()
    assert window.chat.input.text() == "preserved draft"
    assert not window.voice.worker and not window.ai_jobs and not platform.calls
    window.configure_launcher()
    assert "unavailable" in window.settings_page.launcher_status.text()
    window.close()
    assert window.global_launcher.stopped


def test_disabling_launcher_drops_an_already_queued_activation(qtbot):
    calls = []
    registration = SimpleNamespace(identifier=0x4E31, configure=lambda *args: RegistrationResult(True, "disabled", ""), stop=lambda: True)
    launcher = GlobalLauncher(lambda: calls.append("activated"), registration)
    packet = wintypes.MSG()
    packet.message, packet.wParam = WM_HOTKEY, 0x4E31
    launcher.nativeEventFilter(QByteArray(b"windows_dispatcher_MSG"), ctypes.addressof(packet))
    launcher.configure("Ctrl+Space", False)
    qtbot.wait(20)
    assert not calls


def test_ollama_is_explicit_does_not_start_or_install_a_server(qtbot, db, tmp_path, platform):
    window = MainWindow(db, tmp_path, platform)
    qtbot.addWidget(window)
    page = window.providers
    page.provider.setCurrentText("Ollama")
    assert page.address.text() == "http://127.0.0.1:11434/v1"
    assert page.auth.currentText() == "None"
    assert page.model.currentText() == ""
    assert not page.jobs and not platform.calls
    assert "cloud services" in page.status.text()
    page.model.setCurrentText("installed-local-fixture")
    assert page.profile()["protocol"] == "openai"
    assert page.profile()["key"] == ""
    window.close()
