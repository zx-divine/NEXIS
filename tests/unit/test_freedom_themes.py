import json
import pytest
from nexis.core.themes import THEMES, CUSTOM_DEFAULT, contrast, theme_id, tokens, validate_custom
from nexis.storage.database import Database


@pytest.mark.parametrize("theme", list(THEMES))
def test_semantic_colors_remain_readable(theme):
    values = tokens(theme)
    for surface in ("background", "panel", "hover"):
        assert contrast(values["text"], values[surface]) >= 4.5
        for foreground in ("primary", "accent", "muted", "success", "warning", "error"):
            assert contrast(values[foreground], values[surface]) >= 4.5
    assert contrast(values["on_primary"], values["primary"]) >= 4.5
    assert contrast(values["border"], values["background"]) >= 3


@pytest.mark.parametrize("invalid", ["red", "#FFF", "#GG0000", "#1234567", "#12345;", "#000000\n", None])
def test_custom_hex_is_strict(invalid):
    with pytest.raises(ValueError):
        validate_custom({**CUSTOM_DEFAULT, "accent": invalid})


def test_custom_text_is_guarded_but_accent_is_adjusted():
    with pytest.raises(ValueError, match="4.5"):
        validate_custom({**CUSTOM_DEFAULT, "text": CUSTOM_DEFAULT["background"]})
    custom = {**CUSTOM_DEFAULT, "primary": "#080304", "accent": "#080304"}
    assert contrast(tokens("custom", custom)["accent"], custom["background"]) >= 4.5


@pytest.mark.parametrize("legacy,expected", [("dark", "og"), ("light", "arctic")])
def test_legacy_settings_migration_preserves_resources(tmp_path, legacy, expected):
    path = tmp_path / "legacy.db"
    db = Database(path)
    db.set_setting("theme", legacy)
    db.set_setting("history_limit", 73)
    db.execute("DELETE FROM settings WHERE key='custom_theme'")
    db.execute("INSERT INTO snippets VALUES ('preserve','personal','private fixture')")
    db.close()
    db = Database(path)
    assert theme_id(db.setting("theme")) == expected
    assert db.setting("history_limit") == 73
    assert db.rows("SELECT text FROM snippets")[0]["text"] == "private fixture"
    assert db.setting("custom_theme") == CUSTOM_DEFAULT
    custom = {**CUSTOM_DEFAULT, "accent": "#aabbcc"}
    db.set_appearance("custom", custom)
    db.close()
    db = Database(path)
    assert db.setting("theme") == "custom"
    assert db.setting("custom_theme")["accent"] == "#AABBCC"
    db.execute("UPDATE settings SET value=? WHERE key='custom_theme'", (json.dumps({"bad": "#FFFFFF"}),))
    assert db.setting("custom_theme") == CUSTOM_DEFAULT
    db.close()


def test_invalid_save_is_atomic(db):
    original = db.setting("theme")
    with pytest.raises(ValueError):
        db.set_appearance("cyber", {**CUSTOM_DEFAULT, "text": "#080304"})
    assert db.setting("theme") == original


def test_independent_diagnostic_reads_appearance_without_profile_writes(db):
    import hashlib
    from nexis.storage.database import read_appearance
    db.set_appearance("cyber", CUSTOM_DEFAULT)
    before = hashlib.sha256(db.path.read_bytes()).digest()
    assert read_appearance(db.path) == ("cyber", CUSTOM_DEFAULT)
    assert hashlib.sha256(db.path.read_bytes()).digest() == before


def test_empty_custom_palette_is_invalid():
    with pytest.raises(ValueError):
        tokens("custom", {})
