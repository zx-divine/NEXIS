import json
import logging
import pytest
from nexis.core.router import Engine
from nexis.core.permissions import Permissions
from nexis.storage.repository import Repository
from nexis.actions.files import scoped, search


@pytest.mark.parametrize(
    "text",
    [
        "open notepad & calc",
        "open cmd",
        "open powershell",
        "open calc.exe;whoami",
        "open ../../bad.exe",
        "open C:/bad.exe",
        "exec print(1)",
        "open $(calc)",
        "open x|calc",
    ],
)
def test_no_shell_input(db, platform, text):
    assert not Engine(db, platform).execute(text).ok
    assert not platform.calls


def test_sql_injection_is_data(db):
    Repository(db).save_snippet("intro", "'); DROP TABLE snippets;--", "safe")
    assert db.rows("SELECT text FROM snippets")[0]["text"] == "safe"


def test_untrusted_workflow_denied(db, platform):
    db.execute("INSERT INTO workflows VALUES (?,?)", ("evil", json.dumps(["powershell attack"])))
    assert not Engine(db, platform, Permissions(lambda p: True)).execute("run evil").ok
    assert not platform.calls


def test_launch_revalidates_corrupt_shortcut(db, platform):
    db.execute("INSERT INTO shortcuts VALUES (?,?,?)", ("evil", "website", "javascript:bad"))
    assert not Engine(db, platform).execute("open evil").ok
    assert not platform.calls


def test_custom_executable_requires_permission(db, platform, tmp_path):
    executable = tmp_path / "editor.exe"
    executable.touch()
    Repository(db).save_shortcut("editor", "application", str(executable))
    assert not Engine(db, platform).execute("open editor").ok
    assert not platform.calls


def test_private_payload_not_logged_or_recorded(db, platform, caplog):
    secret = "TOP_SECRET_PAYLOAD"
    Repository(db).save_snippet("intro", "Work", secret)
    with caplog.at_level(logging.WARNING, logger="nexis"):
        engine = Engine(db, platform)
        engine.execute("copy intro")
        engine.execute("unknown " + secret)
    assert secret not in caplog.text
    assert secret not in str(db.rows("SELECT * FROM history"))
    assert "intro" not in str(db.rows("SELECT * FROM history"))


def test_scope_and_cancellation(tmp_path):
    from threading import Event

    root = tmp_path / "approved"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "report.PDF").write_text("inside")
    (outside / "report.pdf").write_text("outside")
    roots = [str(root)]
    result = search(roots, "report", ".pdf")
    assert result.paths == [str(root / "report.PDF")]
    with pytest.raises(ValueError):
        scoped(root / ".." / "outside", roots)
    with pytest.raises(ValueError):
        search(roots, "../report")
    stop = Event()
    stop.set()
    assert search(roots, "report", cancel=stop).cancelled


def test_symlink_escape(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").touch()
    try:
        (root / "link").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Creating symlinks requires Windows developer mode or privilege")
    assert not search([str(root)], "secret").paths


def test_subprocess_arrays(monkeypatch, tmp_path):
    from nexis.platform.windows import Windows

    calls = []
    monkeypatch.setattr(
        "nexis.platform.windows.subprocess.Popen", lambda *a, **k: calls.append((a, k))
    )
    executable = tmp_path / "safe.exe"
    executable.touch()
    Windows().launch(str(executable))
    args, options = calls[0]
    assert args[0] == [str(executable.resolve())]
    assert options["shell"] is False


def test_missing_root_does_not_block_valid_root(tmp_path):
    root = tmp_path / "approved"
    root.mkdir()
    assert scoped(root, [str(tmp_path / "missing"), str(root)]) == root.resolve()


def test_search_limits_and_missing_root(tmp_path):
    root = tmp_path / "approved"
    root.mkdir()
    for i in range(3):
        (root / f"report{i}.txt").touch()
    result = search([str(tmp_path / "missing"), str(root)], "report", limit=2)
    assert len(result.paths) == 2 and result.limited and result.inaccessible == 1


def test_windows_junction_escape(tmp_path):
    winapi = pytest.importorskip("_winapi")
    root = tmp_path / "root"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (outside / "secret.txt").touch()
    junction = root / "junction"
    winapi.CreateJunction(str(outside), str(junction))
    try:
        assert not search([str(root)], "secret").paths
    finally:
        junction.rmdir()
