"""Drafting is data validation, never an execution authority."""

import json
from threading import Event, Thread

import pytest

from nexis.core.workflow_drafts import parse_draft, draft_workflow, dry_run
from nexis.core.router import Engine
from nexis.core.permissions import Permissions
from nexis.storage.repository import Repository


@pytest.mark.parametrize("value", [
    '{"steps":["powershell anything"]}', '{"steps":["run nested"]}',
    '{"steps":["open notepad"],"execute":true}', '{"steps":[]}',
    '{"steps":["folder ../escape"]}',
])
def test_drafts_reject_unsupported_or_unresolvable_commands(value, db, platform):
    with pytest.raises(ValueError):
        commands = parse_draft(value)
        dry_run(db, "\n".join(commands), platform)
    assert not platform.calls


def test_dry_run_uses_existing_target_validation_without_side_effects(db, platform):
    rows = dry_run(db, "open notepad\nopen youtube", platform)
    assert len(rows) == 2 and rows[0]["risk"] == "LOW"
    assert not platform.calls
    assert not db.rows("SELECT * FROM history")


def test_draft_generation_has_no_tools_and_does_not_save_or_execute(db, platform, monkeypatch):
    profile = {"provider": "OmniRoute", "endpoint": "http://127.0.0.1:20128/v1", "model": "fixture"}
    seen = []

    def generate(config, messages, cancel):
        seen.extend(messages)
        return {"text": json.dumps({"steps": ["open notepad"]}), "calls": []}

    monkeypatch.setattr("nexis.core.workflow_drafts.generate", generate)
    assert draft_workflow(db, profile, "Open notepad when I study", Event()) == ["open notepad"]
    assert "created by ASH" in seen[0]["content"] and "Draft only" in seen[0]["content"]
    assert len(seen) == 2 and not platform.calls
    assert not db.rows("SELECT * FROM workflows")
    cancelled = Event()
    cancelled.set()
    with pytest.raises(ValueError, match="cancelled"):
        draft_workflow(db, profile, "Open notepad", cancelled)


@pytest.mark.parametrize("outcome", ["resume", "cancel", "revoke"])
def test_pause_respects_cancel_and_revocation_before_next_step(db, platform, outcome):
    Repository(db).save_workflow("study", ["open notepad", "open calculator"])
    cancel, pause, paused = Event(), Event(), Event()
    results = []
    engine = Engine(db, platform, Permissions(lambda preview: True))

    def on_step(index, result):
        if index == 1:
            pause.set()

    def phase(value):
        if value == "PAUSED":
            paused.set()

    thread = Thread(target=lambda: results.append(engine.execute("run study", cancel, on_step, phase, pause)))
    thread.start()
    try:
        assert paused.wait(3) and len(platform.calls) == 1
        if outcome == "resume":
            pause.clear()
        elif outcome == "cancel":
            cancel.set()
        else:
            grants = db.setting("access_permissions")
            grants["workflow_execution"] = False
            db.set_setting("access_permissions", grants)
        thread.join(3)
        assert not thread.is_alive()
        assert len(platform.calls) == (2 if outcome == "resume" else 1)
        assert results[0].ok is (outcome == "resume")
    finally:
        cancel.set()
        thread.join(3)


def test_paused_workflow_has_bounded_deadline(db, platform, monkeypatch):
    Repository(db).save_workflow("study", ["open notepad"])
    ticks = iter([0, 121])
    monkeypatch.setattr("nexis.core.router.monotonic", lambda: next(ticks))
    pause = Event()
    pause.set()
    result = Engine(db, platform, Permissions(lambda preview: True)).execute("run study", pause=pause)
    assert not result.ok and "deadline" in result.message
    assert not platform.calls
