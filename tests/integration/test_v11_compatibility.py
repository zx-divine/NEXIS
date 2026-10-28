from nexis.storage.database import Database
from nexis.storage.repository import Repository
from nexis.core.permissions import Permissions
from nexis.core.router import Engine


def test_v10_database_settings_and_resources_survive(tmp_path):
    path = tmp_path / "existing.db"
    db = Database(path)
    Repository(db).save_snippet("intro", "Work", "keep me")
    Repository(db).save_shortcut("docs", "website", "https://example.com")
    Repository(db).save_workflow("work", ["open docs"])
    db.set_setting("theme", "light")
    db.set_setting("history_limit", 72)
    db.record("help", True)
    # Recreate the absence of v1.1 preference rows in a genuine schema-v1 database.
    for key in ("reduced_motion", "animation_fps", "voice_model_path", "start_maximized"):
        db.execute("DELETE FROM settings WHERE key=?", (key,))
    db.close()
    db = Database(path)
    assert db.rows("PRAGMA user_version")[0]["user_version"] == 5
    assert db.setting("theme") == "light" and db.setting("history_limit") == 72
    assert not db.setting("reduced_motion") and db.setting("animation_fps") == 30
    assert db.rows("SELECT text FROM snippets")[0]["text"] == "keep me"
    assert db.rows("SELECT name FROM workflows")[0]["name"] == "work"
    assert db.rows("SELECT * FROM history")
    db.set_setting("reduced_motion", True)
    db.set_setting("animation_fps", 15)
    db.close()
    db = Database(path)
    assert db.setting("reduced_motion") and db.setting("animation_fps") == 15
    db.close()


def test_execution_phase_only_follows_authorisation(db, platform):
    phases = []
    denied = Engine(db, platform, Permissions(lambda preview: False))
    assert not denied.execute("clear history", on_phase=phases.append).ok
    assert phases == ["PROCESSING"]
    phases.clear()
    assert Engine(db, platform).execute("open notepad", on_phase=phases.append).ok
    assert phases == ["PROCESSING", "EXECUTING"]
