import json
import pytest
from nexis.core.management import Management
from nexis.core.permissions import Permissions
from nexis.storage.repository import Repository


def test_management_denies_without_confirmation(db, platform, tmp_path):
    manager = Management(db, platform)
    Repository(db).save_snippet("private", "General", "private text")
    root = tmp_path / "approved"
    root.mkdir()
    for action in (
        lambda: manager.startup(True),
        manager.delete_all,
        lambda: manager.export(tmp_path / "export.json"),
        lambda: manager.approve_folder(root),
    ):
        with pytest.raises(ValueError, match="permission"):
            action()
    assert not platform.startup
    assert db.rows("SELECT * FROM snippets")
    assert not (tmp_path / "export.json").exists()
    assert db.setting("search_roots") == []


def test_management_approved_operations(db, platform, tmp_path):
    manager = Management(db, platform, Permissions(lambda preview: True))
    manager.startup(True)
    assert platform.startup
    root = tmp_path / "approved"
    root.mkdir()
    manager.approve_folder(root)
    assert db.setting("search_roots") == [str(root.resolve())]
    Repository(db).save_snippet("private", "General", "private text")
    path = tmp_path / "export.json"
    manager.export(path)
    assert json.loads(path.read_text())["snippets"][0]["text"] == "private text"
    with pytest.raises(ValueError, match="database"):
        manager.export(db.path)
    manager.delete_all()
    assert not platform.startup
    assert not db.rows("SELECT * FROM snippets")
