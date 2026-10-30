import json
import math
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from nexis.core.access import DEFAULT_GRANTS, CATEGORIES
from nexis.core.themes import THEMES, CUSTOM_DEFAULT, theme_id, validate_custom


DEFAULTS = {
    "welcome_completed": False,
    "onboarding_progress": {},
    "preferred_name": "",
    "default_launch_mode": "welcome",
    "global_launcher_enabled": True,
    "global_launcher_hotkey": "Ctrl+Space",
    "theme": "og",
    "custom_theme": CUSTOM_DEFAULT,
    "start_minimised": False,
    "history_enabled": True,
    "memory_enabled": True,
    "history_limit": 500,
    "search_roots": [],
    "confirm_low_risk": False,
    "reduced_motion": False,
    "animation_fps": 30,
    "start_maximized": True,
    "voice_model_path": "",
    "catalog_scanned_at": "",
    "tts_voice": "",
    "tts_output": "",
    "tts_enabled": True,
    "audio_input": "",
    "microphone_muted": False,
    "voice_hands_free": False,
    "wake_word_enabled": False,
    "wake_word_confidence": 85,
    "ai_setup_choice": "unreviewed",
    "workflow_drafting_enabled": False,
    "screen_awareness_enabled": False,
    "floating_orb_enabled": False,
    "minimize_to_tray": False,
    "orb_position": [],
    "orb_always_on_top": True,
    "update_checks_enabled": True,
    "update_downloads_enabled": True,
    "update_last_check": "",
    "update_remind_after": "",
    "mic_sensitivity": 100,
    "mic_noise_floor": 0.001,
    "mic_calibration_device": "",
    "mic_end_silence_ms": 1400,
    "mic_normalize": True,
    "system_access_acknowledged": False,
    "access_permissions": DEFAULT_GRANTS,
    "browser_adapter_port": 0,
}
SITES = {
    "youtube": "https://www.youtube.com",
    "github": "https://github.com",
    "chatgpt": "https://chatgpt.com",
}


def read_appearance(path):
    """Read only appearance for an independent diagnostic window; never migrate/write."""
    from contextlib import closing
    if not path.is_file():
        return "og", dict(CUSTOM_DEFAULT)
    try:
        with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=.2)) as connection:
            rows = dict(connection.execute("SELECT key,value FROM settings WHERE key IN ('theme','custom_theme')"))
        selected = theme_id(json.loads(rows.get("theme", '"og"')))
        custom = validate_custom(json.loads(rows.get("custom_theme", json.dumps(CUSTOM_DEFAULT))))
        if selected not in THEMES:
            raise ValueError("Invalid saved appearance")
        return selected, custom
    except (ValueError, TypeError, OSError, sqlite3.Error):
        return "og", dict(CUSTOM_DEFAULT)


class StorageError(RuntimeError):
    pass


class Database:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.lock = RLock()
        try:
            self.connection = sqlite3.connect(path, timeout=5, check_same_thread=False)
            self.connection.row_factory = sqlite3.Row
            with self.connection:
                if self.connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                    raise StorageError(
                        "Database integrity check failed; preserve the file for recovery."
                    )
                version = self.connection.execute("PRAGMA user_version").fetchone()[0]
                if version > 5:
                    raise StorageError("This database requires a newer NEXIS version.")
                if version == 0:
                    self.connection.executescript("""
                        BEGIN;
                        CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                        CREATE TABLE snippets (name TEXT PRIMARY KEY, category TEXT NOT NULL,
                                               text TEXT NOT NULL);
                        CREATE TABLE shortcuts (name TEXT PRIMARY KEY, kind TEXT NOT NULL,
                                                target TEXT NOT NULL);
                        CREATE TABLE workflows (name TEXT PRIMARY KEY, steps TEXT NOT NULL);
                        CREATE TABLE history (id INTEGER PRIMARY KEY, timestamp TEXT NOT NULL,
                                              command TEXT NOT NULL, status TEXT NOT NULL,
                                              summary TEXT NOT NULL);
                        PRAGMA user_version=1;
                        COMMIT;
                    """)
                    for key, value in DEFAULTS.items():
                        self.connection.execute(
                            "INSERT INTO settings VALUES (?,?)", (key, json.dumps(value))
                        )
                    for key, value in SITES.items():
                        self.connection.execute(
                            "INSERT INTO shortcuts VALUES (?, 'website', ?)", (key, value)
                        )
            with self.connection:
                self.connection.execute(
                    "CREATE TABLE IF NOT EXISTS app_catalog (id TEXT PRIMARY KEY, name TEXT NOT NULL, target TEXT NOT NULL, kind TEXT NOT NULL, source TEXT NOT NULL, available INTEGER NOT NULL)"
                )
                self.connection.execute(
                    "CREATE TABLE IF NOT EXISTS app_preferences (id TEXT PRIMARY KEY, alias TEXT NOT NULL DEFAULT '', hidden INTEGER NOT NULL DEFAULT 0, removed INTEGER NOT NULL DEFAULT 0)"
                )
                self.connection.execute(
                    "CREATE TABLE IF NOT EXISTS tool_audit (id INTEGER PRIMARY KEY, timestamp TEXT NOT NULL, request_id TEXT NOT NULL, tool TEXT NOT NULL, category TEXT NOT NULL, risk TEXT NOT NULL, status TEXT NOT NULL)"
                )
                # These obsolete flags must never gate actual provider requests or audio.
                self.connection.execute(
                    "DELETE FROM settings WHERE key IN ('offline_mode','is_offline','connectivity_state','local_ai_fallback')"
                )
                self.connection.execute(
                    "CREATE TABLE IF NOT EXISTS local_memories (id TEXT PRIMARY KEY, kind TEXT NOT NULL, title TEXT NOT NULL, body TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"
                )
                self.connection.execute(
                    "CREATE TABLE IF NOT EXISTS document_index (path TEXT PRIMARY KEY, bytes INTEGER NOT NULL, modified_ns INTEGER NOT NULL, body TEXT NOT NULL)"
                )
                self.connection.execute("CREATE TABLE IF NOT EXISTS conversations (id TEXT PRIMARY KEY, title TEXT NOT NULL, messages TEXT NOT NULL, updated_at TEXT NOT NULL)")
                self.connection.execute("CREATE INDEX IF NOT EXISTS conversations_updated ON conversations(updated_at)")
                self.connection.execute("PRAGMA user_version=5")
        except StorageError:
            self.connection.close()
            raise
        except sqlite3.DatabaseError as exc:
            if hasattr(self, "connection"):
                self.connection.close()
            raise StorageError(
                "Cannot open local database. It may be locked, corrupt or inaccessible. "
                "The existing file was not replaced."
            ) from exc

    def execute(self, sql, args=()):
        with self.lock, self.connection:
            return self.connection.execute(sql, args)

    def rows(self, sql, args=()):
        with self.lock:
            return [dict(row) for row in self.connection.execute(sql, args).fetchall()]

    def setting(self, key):
        rows = self.rows("SELECT value FROM settings WHERE key=?", (key,))
        try:
            value = json.loads(rows[0]["value"]) if rows else DEFAULTS[key]
            default = json.loads(json.dumps(DEFAULTS[key]))
            if type(value) is not type(default):
                return default
            if key == "preferred_name" and value:
                from nexis.core.profile import preferred_name

                return preferred_name(value)
            if key == "default_launch_mode":
                from nexis.core.profile import LAUNCH_MODES

                return value if value in LAUNCH_MODES else default
            if key == "wake_word_confidence":
                return value if 50 <= value <= 95 else default
            if key == "ai_setup_choice":
                return value if value in {"unreviewed", "configured", "later"} else default
            if key == "global_launcher_hotkey":
                from nexis.platform.hotkeys import HOTKEYS

                return value if value in HOTKEYS else default
            if key == "history_limit" and not 1 <= value <= 10000:
                return default
            if key == "animation_fps" and not 10 <= value <= 30:
                return default
            if key == "mic_sensitivity" and not 50 <= value <= 200:
                return default
            if key == "mic_end_silence_ms" and not 700 <= value <= 3000:
                return default
            if key == "mic_noise_floor" and (not math.isfinite(value) or not 0.00001 <= value <= 0.25):
                return default
            if key == "theme" and theme_id(value) not in THEMES:
                return default
            if key == "custom_theme":
                return validate_custom(value)
            if key == "search_roots" and not all(isinstance(x, str) for x in value):
                return []
            if key == "access_permissions":
                return {k: value.get(k) is True for k in CATEGORIES}
            if key == "orb_position" and (len(value) not in (0, 2) or any(type(n) is not int or abs(n) > 100000 for n in value)):
                return []
            if key == "browser_adapter_port" and value != 0 and not 1024 <= value <= 65535:
                return 0
            if isinstance(value, (dict, list)):
                return json.loads(json.dumps(value))
            return value
        except (ValueError, TypeError):
            return json.loads(json.dumps(DEFAULTS[key]))

    def validated_setting(self, key, value):
        if key not in DEFAULTS or type(value) is not type(DEFAULTS[key]):
            raise ValueError("Invalid setting.")
        if key == "preferred_name":
            from nexis.core.profile import preferred_name

            value = preferred_name(value)
        if key == "default_launch_mode":
            from nexis.core.profile import LAUNCH_MODES

            if value not in LAUNCH_MODES:
                raise ValueError("Choose Welcome, Voice, Chat or Manual mode.")
        if key == "global_launcher_hotkey":
            from nexis.platform.hotkeys import HOTKEYS

            if value not in HOTKEYS:
                raise ValueError("Choose a supported launcher shortcut.")
        if key == "history_limit" and not 1 <= value <= 10000:
            raise ValueError("History limit must be 1–10000.")
        if key == "theme" and theme_id(value) not in THEMES:
            raise ValueError("Choose a built-in or custom theme.")
        if key == "custom_theme":
            value = validate_custom(value)
        if key == "animation_fps" and not 10 <= value <= 30:
            raise ValueError("Animation FPS must be 10–30.")
        if key == "access_permissions" and (
            set(value) - set(CATEGORIES) or any(type(v) is not bool for v in value.values())
        ):
            raise ValueError("Invalid permission choices.")
        if key == "browser_adapter_port" and value != 0 and not 1024 <= value <= 65535:
            raise ValueError(
                "Use 0 to disable the browser adapter, or a loopback port from 1024 to 65535."
            )
        if key == "orb_position" and (len(value) not in (0, 2) or any(type(n) is not int or abs(n) > 100000 for n in value)):
            raise ValueError("Invalid saved orb position.")
        if key == "voice_model_path" and value:
            path = Path(value)
            if not path.is_absolute() or not path.is_dir():
                raise ValueError("Choose an existing absolute model directory.")
            value = str(path.resolve(strict=True))
        if key == "search_roots":
            from nexis.utils.validation import approved_root

            value = [str(approved_root(p)) for p in value]
        return value

    def set_settings(self, values):
        """Validate everything before atomically committing a related set of preferences."""
        rows = [(key, json.dumps(self.validated_setting(key, value)))
                for key, value in values.items()]
        with self.lock, self.connection:
            self.connection.executemany("INSERT OR REPLACE INTO settings VALUES (?,?)", rows)

    def set_setting(self, key, value):
        self.set_settings({key: value})
        self.prune()

    def set_appearance(self, selected, custom):
        if selected not in THEMES:
            raise ValueError("Choose an appearance theme.")
        custom = validate_custom(custom)
        with self.lock, self.connection:
            self.connection.executemany("INSERT OR REPLACE INTO settings VALUES (?,?)",
                                        (("theme", json.dumps(selected)), ("custom_theme", json.dumps(custom))))

    def prune(self):
        self.execute(
            "DELETE FROM history WHERE id NOT IN (SELECT id FROM history ORDER BY id DESC LIMIT ?)",
            (self.setting("history_limit"),),
        )

    def record(self, action, ok):
        if not self.setting("history_enabled") or action in ("clear_history", "history"):
            return
        # Arguments and handler messages can contain private data. Never persist them.
        self.execute(
            "INSERT INTO history(timestamp,command,status,summary) VALUES (?,?,?,?)",
            (
                datetime.now(timezone.utc).isoformat(),
                action
                if action in {"open", "folder", "copy", "find", "run", "help"}
                else "unknown",
                "success" if ok else "failed",
                "Completed" if ok else "Not completed",
            ),
        )
        self.prune()

    def export(self):
        return {
            "version": 1,
            "settings": {k: self.setting(k) for k in DEFAULTS},
            **{
                table: self.rows("SELECT * FROM " + table)
                for table in ("snippets", "shortcuts", "workflows", "history", "conversations")
            },
        }

    def reset(self):
        with self.lock, self.connection:
            self.connection.execute("PRAGMA secure_delete=ON")
            for table in (
                "snippets",
                "shortcuts",
                "workflows",
                "history",
                "settings",
                "app_catalog",
                "app_preferences",
                "tool_audit",
                "local_memories",
                "document_index",
                "conversations",
            ):
                self.connection.execute("DELETE FROM " + table)
            for key, value in DEFAULTS.items():
                self.connection.execute(
                    "INSERT INTO settings VALUES (?,?)", (key, json.dumps(value))
                )
            self.connection.execute("PRAGMA secure_delete=ON")
        self.execute("VACUUM")

    def close(self):
        with self.lock:
            self.connection.close()
