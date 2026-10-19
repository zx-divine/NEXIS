import ctypes
import hashlib
import struct
import sys
from pathlib import Path

from nexis.branding import APP_USER_MODEL_ID, application_icon, asset, set_app_user_model_id
from nexis.ui.branding import BrandLogo, WelcomeWizard, splash_screen


def test_assets_are_preserved_and_cwd_independent(qapp, tmp_path, monkeypatch):
    canonical = Path(__file__).resolve().parents[2] / "assets/branding/NEXIS_logo.png"
    monkeypatch.chdir(tmp_path)
    assert (
        hashlib.sha256(canonical.read_bytes()).digest()
        == hashlib.sha256(asset("NEXIS_logo.png").read_bytes()).digest()
    )
    assert not application_icon().isNull()
    data = asset("NEXIS.ico").read_bytes()
    reserved, kind, count = struct.unpack_from("<HHH", data)
    assert (reserved, kind, count) == (0, 1, 7)
    assert {data[6 + index * 16] or 256 for index in range(count)} == {16, 24, 32, 48, 64, 128, 256}


def test_logo_surfaces_and_wizard_commits_only_on_finish(qtbot, db):
    logo = BrandLogo()
    qtbot.addWidget(logo)
    assert not logo.pixmap().isNull()
    splash = splash_screen()
    qtbot.addWidget(splash)
    assert not splash.pixmap().isNull()
    wizard = WelcomeWizard(db)
    qtbot.addWidget(wizard)
    wizard.history.setChecked(False)
    wizard.reject()
    assert db.setting("history_enabled")
    assert not db.setting("welcome_completed")
    wizard = WelcomeWizard(db)
    qtbot.addWidget(wizard)
    wizard.history.setChecked(False)
    wizard.motion.setChecked(True)
    wizard.accept()
    assert db.setting("welcome_completed")
    assert not db.setting("history_enabled")
    assert db.setting("reduced_motion")


def test_windows_process_identity():
    if sys.platform != "win32":
        return
    assert set_app_user_model_id()
    value = ctypes.c_wchar_p()
    getter = ctypes.windll.shell32.GetCurrentProcessExplicitAppUserModelID
    getter.argtypes = [ctypes.POINTER(ctypes.c_wchar_p)]
    getter.restype = ctypes.c_long
    assert getter(ctypes.byref(value)) == 0
    try:
        assert value.value == APP_USER_MODEL_ID
    finally:
        free = ctypes.windll.ole32.CoTaskMemFree
        free.argtypes = [ctypes.c_void_p]
        free(ctypes.cast(value, ctypes.c_void_p))
