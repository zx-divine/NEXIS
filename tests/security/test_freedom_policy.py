from threading import Event
import pytest
from nexis.core.permissions import Permissions, decision
from nexis.core.results import Preview, Risk
from nexis.core.router import Engine
from nexis.core.tools import ToolExecutor, validate_steps
from nexis.storage.repository import Repository


def never(preview):
    pytest.fail("Unnecessary approval for " + preview.action)


@pytest.mark.parametrize("target", ["youtube.com", "google.com", "github.com", "reddit", "https://example.com/page?q=test", "http://example.com"])
def test_validated_websites_automatic_across_engine_tool_shortcut_workflow(db, platform, target):
    engine = Engine(db, platform, Permissions(never))
    assert engine.execute("open " + target).ok
    result = ToolExecutor(db, db.path.parent, platform, never).run({"tool": "website_open", "arguments": {"site": target}}, Event())
    assert result["loaded_page_verified"] is False
    Repository(db).save_shortcut("routine site", "website", target if "." in target else "https://www.reddit.com")
    assert engine.execute("open routine site").ok
    Repository(db).save_workflow("routine", ["open " + target, "open notepad"])
    assert engine.execute("run routine").ok


@pytest.mark.parametrize("command", ["open Calculator", "open Notepad", "open Paint", "open File Explorer", "open Task Manager"])
def test_builtin_launches_automatic(db, platform, command):
    assert Engine(db, platform, Permissions(never)).execute(command).ok


@pytest.mark.parametrize("tool,args", [("settings_open", {"page": "display"}), ("utility_open", {"utility": "task_manager"}),
                                      ("system_information", {}), ("pc_health", {})])
def test_safe_system_tools_do_not_prompt(db, platform, monkeypatch, tool, args):
    executor = ToolExecutor(db, db.path.parent, platform, never)
    effects = []
    monkeypatch.setattr(executor, "dispatch", lambda name, arguments, cancel: effects.append(name) or {"request_accepted": True})
    executor.run({"tool": tool, "arguments": args}, Event())
    assert effects == [tool]


@pytest.mark.parametrize("page", ["password", "accounts", "security", "pin", "system_recovery"])
def test_sensitive_settings_fresh_approval_and_denial(db, platform, page, monkeypatch):
    previews = []
    executor = ToolExecutor(db, db.path.parent, platform, lambda preview: previews.append(preview) or False)
    monkeypatch.setattr(executor, "dispatch", lambda *args: pytest.fail("Denied setting executed"))
    with pytest.raises(ValueError, match="denied"):
        executor.run({"tool": "settings_open", "arguments": {"page": page}}, Event())
    assert len(previews) == 1 and previews[0].risk >= Risk.HIGH
    assert "Windows" in previews[0].reason


def test_risk_capability_authorization_and_os_privilege_are_separate(db, platform):
    assert decision(Preview("run", "bounded", "steps", Risk.MEDIUM)).requirement == "automatic"
    assert decision(Preview("unrecognized", "data", "modify", Risk.MEDIUM)).requirement == "approval"
    assert not Permissions(lambda p: True).authorise(Preview("format", "drive", "erase", Risk.CRITICAL))
    grants = db.setting("access_permissions")
    grants["browser_control"] = False
    db.set_setting("access_permissions", grants)
    assert not Engine(db, platform, Permissions(never)).execute("open youtube.com").ok


@pytest.mark.parametrize("kind,state", [("wifi", "on"), ("wifi", "off"), ("bluetooth", "on"), ("bluetooth", "off")])
def test_radios_require_exact_user_intent_and_voice_review(db, platform, monkeypatch, kind, state):
    calls = []
    monkeypatch.setattr("nexis.platform.radios.set_state", lambda *args: calls.append(args[:2]) or {"verified": True})
    step = {"tool": "radio_set", "arguments": {"kind": kind, "state": state}}
    with pytest.raises(ValueError, match="explicit"):
        ToolExecutor(db, db.path.parent, platform, never, request_text="summarize a document").run(step, Event())
    assert not Engine(db, platform, Permissions(never), allow_radio=False).execute(f"radio {kind} {state}").ok
    assert not calls
    assert Engine(db, platform, Permissions(never)).execute(f"turn {kind} {state}").ok
    assert calls == [(kind, state)]


def test_remote_off_and_cancel_do_not_submit(monkeypatch):
    from nexis.platform import radios
    monkeypatch.setattr(radios, "remote_session", lambda: True)
    monkeypatch.setattr(radios.subprocess, "Popen", lambda *a, **k: pytest.fail("Remote radio off submitted"))
    with pytest.raises(ValueError, match="disconnect"):
        radios.set_state("wifi", "off", Event())
    cancel = Event()
    cancel.set()
    with pytest.raises(ValueError, match="cancelled"):
        radios.set_state("wifi", "on", cancel)


@pytest.mark.parametrize("target", ["javascript:alert(1)", "file:///C:/bad.exe", "https://example.com/\"&calc", "data:text/html,bad"])
def test_dangerous_website_schemes_and_injection_blocked(db, platform, target):
    assert not Engine(db, platform, Permissions(lambda p: True)).execute("open " + target).ok
    assert not platform.calls


def test_scripts_nested_workflows_and_unregistered_tool_arguments_blocked(db, platform):
    for text in ("open powershell", "open notepad && calc", "powershell do-something", "run missing"):
        assert not Engine(db, platform, Permissions(lambda p: True)).execute(text).ok
    with pytest.raises(ValueError):
        Repository(db).save_workflow("nested", ["run another"])
    with pytest.raises(ValueError):
        validate_steps([{"tool": "radio_set", "arguments": {"kind": "wifi", "state": "off;calc"}}])
    assert not platform.calls


def test_approved_document_and_folder_validation_precedes_automatic_launch(db, platform, tmp_path, monkeypatch):
    from nexis.actions import operator_files
    root = tmp_path / "approved"
    root.mkdir()
    document = root / "ordinary.txt"
    document.write_text("ordinary fixture", encoding="utf-8")
    db.set_setting("search_roots", [str(root)])
    effects = []
    monkeypatch.setattr(operator_files.os, "startfile", lambda path: effects.append(path))
    executor = ToolExecutor(db, db.path.parent, platform, never)
    # The fixture data directory is separate from the explicitly approved folder.
    executor.run({"tool": "file_open", "arguments": {"path": str(document)}}, Event())
    assert effects == [str(document)]
    assert Engine(db, platform, Permissions(never)).execute("open " + str(document)).ok
    executor.run({"tool": "folder_open", "arguments": {"path": str(root)}}, Event())
    for target in (root / "missing.txt", root / "unsafe.ps1", tmp_path / "outside.txt"):
        target.write_text("fixture", encoding="utf-8") if target.name != "missing.txt" else None
        with pytest.raises((ValueError, OSError)):
            executor.run({"tool": "file_open", "arguments": {"path": str(target)}}, Event())


def test_sensitive_workflow_step_prompts_once_and_denial_stops_following_steps(db, platform):
    Repository(db).save_workflow("sensitive", ["open notepad", "settings security", "open calculator"])
    approvals = []
    result = Engine(db, platform, Permissions(lambda preview: approvals.append(preview) or False)).execute("run sensitive")
    assert not result.ok
    assert len(approvals) == 1 and approvals[0].action == "settings_open"
    assert platform.calls == [("launch", "notepad", True)]


def test_cancel_during_confirmation_prevents_effect(db, platform, monkeypatch):
    cancel = Event()
    def approve(preview):
        cancel.set()
        return True
    executor = ToolExecutor(db, db.path.parent, platform, approve)
    monkeypatch.setattr(executor, "dispatch", lambda name, args, deadline: pytest.fail("Cancelled action executed"))
    # run() must stop before even entering a late delivery callback, not only in dispatch().
    with pytest.raises(ValueError, match="cancelled"):
        executor.run({"tool": "settings_open", "arguments": {"page": "password"}}, cancel)


@pytest.mark.parametrize("identity,trusted", [("ordinary", False), ("powershell", True), ("python", True), ("wscript", True), ("", True)])
def test_installed_location_and_renaming_do_not_establish_trust(tmp_path, monkeypatch, identity, trusted):
    from nexis.core.launch_policy import launch_risk
    path = tmp_path / "Program Files" / "InnocentName.exe"
    path.parent.mkdir()
    data = bytearray(128)
    data[:2], data[60:64], data[64:68] = b"MZ", (64).to_bytes(4, "little"), b"PE\0\0"
    path.write_bytes(data)
    monkeypatch.setenv("ProgramFiles", str(path.parent))
    monkeypatch.setattr("nexis.core.launch_policy.original_filename", lambda target: identity)
    monkeypatch.setattr("nexis.core.launch_policy.trusted_signature", lambda target: trusted)
    if identity in {"powershell", "python", "wscript"}:
        with pytest.raises(ValueError, match="script hosts"):
            launch_risk(path)
    else:
        assert launch_risk(path) == Risk.HIGH


def test_operator_expiry_invalidates_delayed_callbacks(db, platform, monkeypatch):
    from nexis.core.operator import OperatorWorker
    worker = OperatorWorker(db, db.path.parent, "fixture", platform)
    clock = iter((0, 181))
    monkeypatch.setattr("nexis.core.operator.monotonic", lambda: next(clock))
    monkeypatch.setattr(worker.answer, "wait", lambda interval: False)
    assert not worker.confirm(Preview("sensitive", "resource", "change", Risk.HIGH))
    assert worker.cancel.is_set()


@pytest.mark.parametrize("tool", ["password_change", "account_modify", "security_disable", "drive_format", "script_execute"])
def test_unsupported_sensitive_changes_cannot_be_injected_after_safe_steps(tool):
    with pytest.raises(ValueError, match="unsupported tool"):
        validate_steps([{"tool": "app_open", "arguments": {"name": "notepad"}},
                        {"tool": tool, "arguments": {}}])


def test_sensitive_name_cannot_hide_renamed_interpreter_even_with_approval(tmp_path, db, platform, monkeypatch):
    path = tmp_path / "NiceTerminal.exe"
    path.write_bytes(b"fixture: never executed")
    monkeypatch.setattr("nexis.core.launch_policy.original_filename", lambda path: "python")
    Repository(db).save_shortcut("renamed host", "application", str(path))
    result = Engine(db, platform, Permissions(lambda p: True)).execute("open renamed host")
    assert not result.ok and "script hosts" in result.message
    assert not platform.calls
