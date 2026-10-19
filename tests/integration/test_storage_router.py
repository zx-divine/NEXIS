from threading import Event
import pytest

from nexis.core.router import Engine
from nexis.core.permissions import Permissions
from nexis.storage.database import Database, StorageError
from nexis.storage.repository import Repository


def test_database_persists_and_migrates(tmp_path):
    path = tmp_path / "data.db"
    db = Database(path)
    db.set_setting("theme", "light")
    Repository(db).save_snippet("intro", "Work", "Hello!")
    db.close()
    db = Database(path)
    assert db.setting("theme") == "light"
    assert db.rows("SELECT text FROM snippets")[0]["text"] == "Hello!"
    assert db.rows("PRAGMA user_version")[0]["user_version"] == 3
    db.close()


def test_corrupt_database_preserved(tmp_path):
    path = tmp_path / "broken.db"
    path.write_bytes(b"not a sqlite file")
    with pytest.raises(StorageError):
        Database(path)
    assert path.read_bytes() == b"not a sqlite file"


def test_settings_validation_and_recovery(db):
    with pytest.raises(ValueError):
        db.set_setting("history_limit", 0)
    with pytest.raises(ValueError):
        db.set_setting("theme", "bogus")
    db.execute("UPDATE settings SET value=? WHERE key='search_roots'", ("[1]",))
    assert db.setting("search_roots") == []
    db.execute("UPDATE settings SET value=? WHERE key='theme'", ("broken json",))
    assert db.setting("theme") == "dark"


def test_retention_and_disabled_history(db):
    db.set_setting("history_limit", 2)
    for _ in range(4):
        db.record("open", True)
    assert len(db.rows("SELECT * FROM history")) == 2
    db.set_setting("history_enabled", False)
    db.record("copy", True)
    assert len(db.rows("SELECT * FROM history")) == 2


def test_routing_and_snippets(db, platform):
    engine = Engine(db, platform)
    assert engine.execute("open notepad").ok
    assert platform.calls == [("launch", "notepad", True)]
    assert engine.execute("open github").ok
    Repository(db).save_snippet("intro", "Work", "Hello")
    result = engine.execute("copy intro")
    assert result.ok and result.data["clipboard"] == "Hello"
    Repository(db).save_snippet("intro", "Personal", "Updated")
    assert engine.execute("copy intro").data["clipboard"] == "Updated"
    Repository(db).delete("snippets", "intro")
    assert not engine.execute("copy intro").ok
    assert not engine.execute("unsupported secret").ok
    assert not engine.execute("help extra").ok


def test_history_confirmation_enforced(db, platform):
    engine = Engine(db, platform)
    engine.execute("help")
    assert not engine.execute("clear history").ok
    assert db.rows("SELECT * FROM history")
    engine.permissions = Permissions(lambda preview: True)
    assert engine.execute("clear history").ok
    assert not db.rows("SELECT * FROM history")


def test_workflow_stop_and_step_validation(db, platform):
    repo = Repository(db)
    repo.save_workflow("morning", ["open notepad", "open missing", "open calculator"])
    engine = Engine(db, platform, Permissions(lambda p: True))
    assert not engine.execute("run morning").ok
    assert platform.calls == []  # all targets validated before any step
    repo.save_workflow("morning", ["open notepad", "open calculator"])
    results = []
    assert engine.execute("run morning", on_step=lambda i, r: results.append(r)).ok
    assert len(results) == 2
    cancel = Event()
    platform.calls.clear()
    assert not engine.execute("run morning", cancel, lambda i, r: cancel.set()).ok
    assert len(platform.calls) == 1


def test_workflow_failure_policy(db, platform):
    Repository(db).save_workflow("test", ["open notepad", "open calculator"])

    def fail(*args, **kwargs):
        raise PermissionError("private path")

    platform.launch = fail
    seen = []
    result = Engine(db, platform, Permissions(lambda p: True)).execute(
        "run test", on_step=lambda i, r: seen.append(r)
    )
    assert not result.ok and len(seen) == 1
    assert "private path" not in result.message


def test_shortcuts_export_reset(db):
    repo = Repository(db)
    repo.save_shortcut("docs", "website", "https://example.com")
    repo.save_snippet("intro", "Work", "Hello")
    repo.save_workflow("work", ["open docs"])
    exported = db.export()
    assert exported["snippets"][0]["text"] == "Hello"
    db.reset()
    for table in ("shortcuts", "snippets", "workflows", "history"):
        assert not db.rows("SELECT * FROM " + table)
    assert db.setting("history_enabled")
