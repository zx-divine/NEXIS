"""Security and side-effect tests use only disposable approved folders."""

import json
from pathlib import Path
from threading import Event
import pytest

from nexis.core.access import CATEGORIES, require_access
from nexis.core.operator import OperatorWorker, parse_plan
from nexis.core.tools import TOOLS, ToolExecutor, validate_steps
from nexis.core.provider_manager import ProviderManager
from nexis.core.providers import ProviderStore
from nexis.storage.database import Database
from nexis.actions.operator_files import safe_path


@pytest.fixture
def executor(db, tmp_path, platform):
    folder = tmp_path / "approved"
    folder.mkdir()
    db.set_setting("search_roots", [str(folder)])
    return ToolExecutor(db, db.path.parent, platform, lambda preview: True)


def step(tool, **arguments):
    return {"tool": tool, "arguments": arguments}


def test_fresh_permissions_are_denied_and_separate_from_credentials(tmp_path):
    database = Database(tmp_path / "fresh.db")
    try:
        assert not any(database.setting("access_permissions").values())
        assert not database.setting("system_access_acknowledged")
        with pytest.raises(ValueError, match="SYSTEM ACCESS"):
            require_access(database, "network_actions")
    finally:
        database.close()


@pytest.mark.parametrize(
    "tool,arguments",
    [
        ("powershell", {"command": "anything"}),
        ("volume_set", {"percent": True}),
        ("volume_set", {"percent": 101}),
        ("volume_set", {"percent": -1}),
        ("window_close", {"window_id": -1}),
        ("app_open", {"name": "notepad", "shell": True}),
        ("file_create_text", {"path": "x"}),
        ("settings_open", {"page": "disable_security"}),
        ("browser_open_tabs", {"sites": ["github"] * 11}),
    ],
)
def test_typed_schema_rejects_unsafe_or_unexpected_arguments(tool, arguments):
    with pytest.raises(ValueError):
        validate_steps([step(tool, **arguments)])


def test_tool_registry_contains_required_metadata():
    for spec in TOOLS.values():
        assert spec.category in CATEGORIES
        assert spec.timeout > 0 and spec.compatibility and spec.audit
        assert spec.verification and spec.cancellation and spec.preconditions
        assert spec.parameters["additionalProperties"] is False


def test_provider_prose_cannot_execute_commands():
    plan = parse_plan({"text": "powershell Remove-Item stuff", "calls": []})
    assert plan["steps"] == []
    with pytest.raises(ValueError):
        parse_plan({"text": '{"steps":[{"tool":"shell","arguments":{}}]}', "calls": []})


def test_create_copy_move_rename_and_preview_are_real_disposable_operations(executor, db):
    root = Path(db.setting("search_roots")[0])
    file = root / "hello.txt"
    assert executor.run(step("file_create_text", path=str(file), text="नमस्ते NEXIS"), Event())[
        "verified"
    ]
    assert executor.run(step("file_preview", path=str(file)), Event())["text"] == "नमस्ते NEXIS"
    folder = root / "organized"
    assert executor.run(step("folder_create", path=str(folder)), Event())["verified"]
    copy = folder / "copy.txt"
    assert executor.run(step("file_copy", path=str(file), destination=str(copy)), Event())[
        "verified"
    ]
    moved = root / "moved.txt"
    assert executor.run(step("file_move", path=str(copy), destination=str(moved)), Event())[
        "verified"
    ]
    renamed = root / "renamed.txt"
    assert executor.run(step("file_rename", path=str(moved), destination=str(renamed)), Event())[
        "verified"
    ]
    assert renamed.read_text(encoding="utf-8") == "नमस्ते NEXIS" and not moved.exists()
    assert executor.run(step("file_search", query="renamed"), Event())["paths"] == [str(renamed)]


def test_no_overwrites_or_out_of_scope_paths(executor, db, tmp_path):
    root = Path(db.setting("search_roots")[0])
    file = root / "keep.txt"
    file.write_text("original")
    for destination in (str(file), str(tmp_path / "outside.txt")):
        with pytest.raises(ValueError):
            executor.run(step("file_create_text", path=destination, text="replacement"), Event())
    assert file.read_text() == "original"


@pytest.mark.parametrize("filename", ["con.txt", "aux.txt", "file:stream.txt", "bad. "])
def test_reserved_paths_are_rejected(executor, db, filename):
    with pytest.raises((ValueError, OSError)):
        safe_path(
            str(Path(db.setting("search_roots")[0]) / filename),
            db.setting("search_roots"),
            new=True,
        )


def test_cancellation_stops_before_side_effect(executor, db):
    target = Path(db.setting("search_roots")[0]) / "cancelled.txt"
    cancel = Event()
    cancel.set()
    with pytest.raises(ValueError, match="cancel"):
        executor.run(step("file_create_text", path=str(target), text="should not exist"), cancel)
    assert not target.exists()


def test_revocation_between_preview_and_execution_blocks_action(executor, db):
    root = Path(db.setting("search_roots")[0])

    def revoke(preview):
        grants = db.setting("access_permissions")
        grants["file_modifications"] = False
        db.set_setting("access_permissions", grants)
        return True

    executor.confirm = revoke
    target = root / "blocked.txt"
    with pytest.raises(ValueError, match="Permission denied"):
        executor.run(step("file_create_text", path=str(target), text="no"), Event())
    assert not target.exists()


def test_high_action_denied_without_fresh_confirmation(executor, db):
    file = Path(db.setting("search_roots")[0]) / "keep.txt"
    file.write_text("keep")
    executor.confirm = lambda preview: False
    with pytest.raises(ValueError, match="denied"):
        executor.run(step("file_recycle", path=str(file)), Event())
    assert file.exists()


def test_protected_settings_only_handoff_and_do_not_collect_secrets(executor, monkeypatch):
    calls = []
    monkeypatch.setattr(
        "nexis.platform.operator_windows.open_settings",
        lambda page: (
            calls.append(page)
            or {
                "request_accepted": True,
                "setting_changed": False,
                "user_completion_required": True,
            }
        ),
    )
    result = executor.run(step("settings_open", page="pin"), Event())
    assert calls == ["pin"] and not result["setting_changed"]
    with pytest.raises(ValueError):
        executor.run(step("settings_open", page="pin", pin="1234"), Event())


def test_audit_contains_no_paths_or_content(executor, db):
    target = Path(db.setting("search_roots")[0]) / "secret-name.txt"
    executor.run(step("file_create_text", path=str(target), text="sensitive contents"), Event())
    data = json.dumps(db.rows("SELECT * FROM tool_audit"))
    assert "secret-name" not in data and "sensitive contents" not in data
    assert "file_create_text" in data


def test_no_connectivity_setting_can_gate_audio_or_provider(db):
    db.execute("INSERT OR REPLACE INTO settings VALUES ('offline_mode','true')")
    db.execute("INSERT OR REPLACE INTO settings VALUES ('is_offline','true')")
    require_access(db, "network_actions")
    require_access(db, "microphone_access")
    migrated = Database(db.path)
    assert not migrated.rows("SELECT * FROM settings WHERE key IN ('offline_mode','is_offline')")
    migrated.close()


def test_manager_migrates_legacy_without_rewriting_it_and_never_auto_switches(tmp_path):
    original = {
        "provider": "OmniRoute",
        "endpoint": "http://127.0.0.1:20128/v1",
        "key": "fixture-original-key",
        "model": "owner-model",
    }
    legacy = ProviderStore(tmp_path)
    legacy.save(original)
    original_bytes = legacy.path.read_bytes()
    manager = ProviderManager(tmp_path)
    assert manager.active()["key"] == original["key"]
    new_id = manager.save(
        {
            "provider": "Google Gemini",
            "endpoint": "https://generativelanguage.googleapis.com",
            "model": "runtime-selected-fixture",
            "key": "fixture-new-key",
        }
    )
    assert manager.active()["provider"] == "OmniRoute"
    assert legacy.path.read_bytes() == original_bytes
    assert b"fixture-new-key" not in manager.path.read_bytes()
    manager.select(new_id)
    assert ProviderManager(tmp_path).active()["provider"] == "Google Gemini"
    manager.remove(new_id)
    assert manager.active() is None and legacy.path.read_bytes() == original_bytes


def test_manager_corruption_preserves_original(tmp_path):
    manager = ProviderManager(tmp_path)
    manager.path.write_bytes(b"corrupt encrypted profile")
    with pytest.raises(ValueError, match="preserved"):
        manager.active()
    assert manager.path.read_bytes() == b"corrupt encrypted profile"


def test_window_identity_is_checked_before_any_native_change(monkeypatch):
    import win32gui
    import win32process
    from nexis.platform.operator_windows import change_window

    calls = []
    monkeypatch.setattr(win32gui, "IsWindow", lambda handle: True)
    monkeypatch.setattr(win32gui, "IsWindowVisible", lambda handle: True)
    monkeypatch.setattr(win32process, "GetWindowThreadProcessId", lambda handle: (1, 222))
    monkeypatch.setattr(win32gui, "ShowWindow", lambda *args: calls.append(args))
    with pytest.raises(ValueError, match="identity changed"):
        change_window(42, "minimize", Event(), 111)
    assert not calls


def test_unsafe_browser_control_address_rejected_before_socket(monkeypatch):
    from nexis.platform.browser import BrowserAdapter

    adapter = BrowserAdapter(9222)
    monkeypatch.setattr(
        adapter,
        "selected",
        lambda identifier: {
            "webSocketDebuggerUrl": "ws://untrusted.example:9222/devtools/page/abc"
        },
    )
    with pytest.raises(ValueError, match="unsafe"):
        adapter.control("abc", "navigate", Event(), "https://example.com")


def test_invalid_second_plan_step_prevents_first_action(qtbot, db, tmp_path, platform, monkeypatch):
    manager = ProviderManager(tmp_path)
    selected = manager.save(
        {
            "provider": "Compatible gateway",
            "endpoint": "http://127.0.0.1:20128/v1",
            "model": "fixture",
            "key": "fixture",
        }
    )
    manager.select(selected)
    plan = {
        "message": "",
        "steps": [step("app_open", name="notepad"), step("raw_shell", command="anything")],
        "needs_more": False,
    }
    monkeypatch.setattr(
        "nexis.core.operator.generate", lambda *a, **k: {"text": json.dumps(plan), "calls": []}
    )
    worker = OperatorWorker(db, tmp_path, "test", platform)
    with qtbot.waitSignal(worker.failed):
        worker.start()
    assert worker.wait(2000) and not platform.calls


@pytest.mark.parametrize(
    "text,secret",
    [
        ("change my pin to 1234", "1234"),
        ("my PIN is 876543", "876543"),
        ("my password is private-password", "private-password"),
        ("recovery code: ABCDE-12345", "ABCDE-12345"),
        ("my key is sk-fixtureabcdefghijkl", "sk-fixtureabcdefghijkl"),
    ],
)
def test_protected_credentials_are_redacted_before_conversation(text, secret):
    from nexis.core.privacy import sanitize_request

    sanitized = sanitize_request(text)
    assert secret not in sanitized and "redacted" in sanitized


def test_settings_help_does_not_require_or_invent_credentials():
    from nexis.core.privacy import sanitize_request

    text = "Help me change my Windows PIN"
    assert sanitize_request(text) == text
