import json
from threading import Event

import pytest

from nexis.core import doctor
from nexis.storage.memory import LocalMemory


def test_doctor_keeps_private_data_out_of_reports_and_does_not_capture_or_send(db, tmp_path, monkeypatch):
    import sounddevice
    import urllib.request
    monkeypatch.setattr(sounddevice, "RawInputStream", lambda *a, **kw: pytest.fail("No diagnostic capture"))
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **kw: pytest.fail("No automatic cloud test"))
    secret = "PRIVATE-DIAGNOSTIC-SENTINEL"
    LocalMemory(db).save({"kind": "memory", "title": "Private", "body": secret})
    (tmp_path / secret).mkdir()
    db.set_setting("search_roots", [str(tmp_path / secret)])
    profile = {"provider": "OpenAI-compatible", "endpoint": "https://example.com/v1", "model": secret, "key": secret}
    report = doctor.collect(db, tmp_path, Event(), profile=profile)
    text = json.dumps(report)
    assert secret not in text and str(tmp_path) not in text
    assert report["network_requests_in_this_check"] == 0
    assert all(row["status"] in doctor.STATUSES for row in report["checks"])
    assert next(row for row in report["checks"] if row["check"] == "Wake word")["status"] == "NOT TESTED"
    assert next(row for row in report["checks"] if row["check"] == "Authentication / model / network")["status"] == "NOT TESTED"
    destination = tmp_path / "safe-report.json"
    doctor.export_report(report, destination, tmp_path / "data")
    assert json.loads(destination.read_text()) == report
    with pytest.raises(ValueError):
        doctor.export_report(report, destination, tmp_path / "data")
    with pytest.raises(ValueError):
        doctor.export_report(report, tmp_path / "data/invalid.json", tmp_path / "data")


def test_doctor_detects_corrupt_types_and_mute_worker_conflict(db, tmp_path):
    db.execute("UPDATE settings SET value=? WHERE key=?", ('"bad-type"', "theme"))
    db.execute("UPDATE settings SET value=? WHERE key=?", ('"bad-type"', "microphone_muted"))
    report = doctor.collect(db, tmp_path, Event())
    assert next(row for row in report["checks"] if row["check"] == "Configuration")["status"] == "WARNING"
    db.set_setting("microphone_muted", True)
    report = doctor.collect(db, tmp_path, Event(), runtime={"capture_active": True})
    assert next(row for row in report["checks"] if row["check"] == "Hard Mute")["status"] == "FAIL"


def test_cancelled_doctor_returns_no_new_report(db, tmp_path):
    cancel = Event()
    cancel.set()
    with pytest.raises(ValueError, match="cancelled"):
        doctor.collect(db, tmp_path, cancel)


def test_provider_diagnostic_has_no_tools_history_or_memories(db, monkeypatch):
    calls = []
    monkeypatch.setattr("nexis.core.provider_manager.generate", lambda profile, messages, cancel: calls.append(messages) or {"text": "fixture reply"})
    profile = {"provider": "OpenAI-compatible", "endpoint": "https://example.com/v1", "model": "fixture", "key": "fixture"}
    row = doctor.provider_test(db, profile, Event())
    assert row["status"] == "PASS" and len(calls) == 1 and len(calls[0]) == 1
    db.set_setting("access_permissions", {})
    with pytest.raises(ValueError, match="Permission denied"):
        doctor.provider_test(db, profile, Event())
    assert len(calls) == 1


def test_memory_off_preserves_notes_and_blocks_new_writes(db):
    memory = LocalMemory(db)
    identifier = memory.save({"kind": "preference", "title": "Theme", "body": "Dark mode"})
    data = memory.export_text()
    db.set_setting("memory_enabled", False)
    with pytest.raises(ValueError, match="Memory is off"):
        memory.save({"kind": "memory", "title": "New", "body": "Blocked"})
    with pytest.raises(ValueError, match="Memory is off"):
        memory.import_text(data)
    assert memory.search()[0]["id"] == identifier
    assert memory.export_text() == data
    memory.delete(identifier)
    assert not memory.search()
