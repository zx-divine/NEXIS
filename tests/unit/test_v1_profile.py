import pytest

from nexis.core.profile import greeting, preferred_name
from nexis.storage.database import Database


@pytest.mark.parametrize("name", ["ASH", "अनन्या", "रवि Kumar", "A & <B>"])
def test_preferred_identity_preserves_multilingual_plain_text(db, name):
    db.set_setting("preferred_name", "  " + name + "  ")
    assert db.setting("preferred_name") == name
    assert greeting(name) == f"Welcome to NEXIS, {name}."


@pytest.mark.parametrize("name", ["", "   ", "a" * 81, "Ash\nadmin", "Ash\u202eexe", "x\x00y"])
def test_identity_rejects_empty_overlong_and_control_characters(name, db):
    with pytest.raises(ValueError):
        preferred_name(name)
    with pytest.raises(ValueError):
        db.set_setting("preferred_name", name)


def test_profile_survives_restart_and_invalid_saved_mode_falls_back(db):
    db.set_setting("preferred_name", "ASH")
    db.set_setting("default_launch_mode", "manual")
    reopened = Database(db.path)
    assert reopened.setting("preferred_name") == "ASH"
    assert reopened.setting("default_launch_mode") == "manual"
    reopened.execute("INSERT OR REPLACE INTO settings VALUES ('default_launch_mode', ?)", ('"shell"',))
    assert reopened.setting("default_launch_mode") == "welcome"
    reopened.close()
    with pytest.raises(ValueError):
        db.set_setting("default_launch_mode", "shell")
