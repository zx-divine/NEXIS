"""Risk-based executable launch consent. Installer execution remains sensitive."""
import os
import shutil
from pathlib import Path
from threading import Event

import pytest

from nexis.core.catalog import Catalog
from nexis.core.launch_policy import launch_risk
from nexis.core.permissions import Permissions
from nexis.core.results import Risk
from nexis.core.router import Engine
from nexis.core.tools import ToolExecutor
from nexis.platform.discovery import Application


def pe(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = bytearray(128)
    data[:2] = b"MZ"
    data[60:64] = (64).to_bytes(4, "little")
    data[64:68] = b"PE\0\0"
    path.write_bytes(data)
    return path


def installed(tmp_path, monkeypatch, db):
    # Trust APIs have separate native probes; this policy fixture represents a
    # verified ordinary installed application, never an executed synthetic PE.
    monkeypatch.setattr("nexis.core.launch_policy.trusted_signature", lambda path: True)
    monkeypatch.setattr("nexis.core.launch_policy.original_filename", lambda path: "browser")
    base = tmp_path / "Program Files"
    monkeypatch.setenv("ProgramFiles", str(base))
    path = base / "Browser" / "browser.exe"
    path.parent.mkdir(parents=True, exist_ok=True)
    # Copy a real Windows PE as fixture data only; FakePlatform never executes it.
    if os.name == "nt":
        shutil.copyfile(Path(os.environ["SystemRoot"]) / "System32/notepad.exe", path)
    else:
        pe(path)
    app = Application.create("Browser", str(path), "exe", "User Start Menu")
    Catalog(db).update([app.__dict__])
    return path


def test_explicit_installed_launch_does_not_prompt_repeatedly(tmp_path, monkeypatch, db, platform):
    installed(tmp_path, monkeypatch, db)
    confirmations = []
    engine = Engine(db, platform, Permissions(lambda preview: confirmations.append(preview) or False))
    assert engine.execute("open Browser").ok
    assert engine.execute("open Browser").ok
    assert not confirmations
    assert len(platform.calls) == 2


def test_installed_app_revocation_still_blocks(tmp_path, monkeypatch, db, platform):
    installed(tmp_path, monkeypatch, db)
    grants = db.setting("access_permissions")
    grants["application_launching"] = False
    db.set_setting("access_permissions", grants)
    assert not Engine(db, platform).execute("open Browser").ok
    assert not platform.calls


def test_downloaded_executable_keeps_fresh_approval(tmp_path, db, platform):
    path = pe(tmp_path / "Downloads" / "some-app.exe")
    db.execute("INSERT INTO shortcuts VALUES (?,?,?)", ("downloaded", "application", str(path)))
    assert not Engine(db, platform).execute("open downloaded").ok
    assert not platform.calls
    assert Engine(db, platform, Permissions(lambda p: True)).execute("open downloaded").ok


def test_installer_risk_never_reduced_by_install_location(tmp_path, monkeypatch):
    base = tmp_path / "Program Files"
    monkeypatch.setenv("ProgramFiles", str(base))
    path = pe(base / "ProductSetup.exe")
    assert launch_risk(path) == Risk.HIGH
    assert launch_risk("Microsoft.WindowsTerminal_8wekyb3d8bbwe!App", appx=True) == Risk.HIGH


def test_installer_requires_sensitive_category_and_fresh_confirmation(tmp_path, db, platform):
    path = pe(tmp_path / "Setup.exe")
    db.execute("INSERT INTO shortcuts VALUES (?,?,?)", ("installer", "application", str(path)))
    assert not Engine(db, platform).execute("open installer").ok
    assert not platform.calls
    assert Engine(db, platform, Permissions(lambda p: True)).execute("open installer").ok
    grants = db.setting("access_permissions")
    grants["sensitive_operations"] = False
    db.set_setting("access_permissions", grants)
    assert not Engine(db, platform, Permissions(lambda p: True)).execute("open installer").ok
    assert len(platform.calls) == 1


def test_optional_extra_confirmation_occurs_once_through_ai_wrapper(tmp_path, monkeypatch, db, platform):
    installed(tmp_path, monkeypatch, db)
    db.set_setting("confirm_low_risk", True)
    confirmations = []
    executor = ToolExecutor(db, tmp_path, platform, lambda p: confirmations.append(p) or True)
    result = executor.run({"tool": "app_open", "arguments": {"name": "Browser"}}, Event())
    assert result["request_accepted"]
    assert len(confirmations) == 1


def test_fake_installed_binary_cannot_become_low_risk(tmp_path, monkeypatch):
    monkeypatch.setenv("ProgramFiles", str(tmp_path))
    bad = tmp_path / "fake.exe"
    bad.write_text("not a PE")
    with pytest.raises(ValueError):
        launch_risk(bad)






def test_installed_elevated_program_still_requires_review(tmp_path, monkeypatch, db):
    path = installed(tmp_path, monkeypatch, db)
    monkeypatch.setattr("nexis.core.launch_policy.elevation_risk", lambda target: Risk.HIGH)
    if os.name == "nt":
        assert launch_risk(path) == Risk.HIGH


def test_system_utility_is_not_automatically_treated_as_ordinary_app(tmp_path, monkeypatch):
    monkeypatch.setenv("SystemRoot", str(tmp_path))
    path = pe(tmp_path / "System32" / "diskpart.exe")
    assert launch_risk(path) != Risk.LOW


def test_installation_directory_keeps_fresh_review(tmp_path, monkeypatch, db, platform):
    installed(tmp_path, monkeypatch, db)
    step = {"tool": "app_directory", "arguments": {"name": "Browser"}}
    with pytest.raises(ValueError, match="Permission denied"):
        ToolExecutor(db, tmp_path, platform, lambda preview: False).run(step, Event())
    assert not platform.calls
    assert ToolExecutor(db, tmp_path, platform, lambda preview: True).run(step, Event())["request_accepted"]
    assert platform.calls[0][0] == "folder"
