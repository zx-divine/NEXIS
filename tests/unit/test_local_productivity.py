"""Disposable local data tests; no private folders, recordings or network calls."""

import json
import os
from pathlib import Path
from threading import Event

import pytest

from nexis.storage.database import Database
from nexis.storage.memory import LocalMemory, validate_entry
from nexis.storage.document_index import DocumentIndex
from nexis.actions.files import SearchFilters, search
from nexis.platform.health import health_snapshot
from nexis.core.tools import validate_steps


def entry(body="Prefers a quiet workspace", title="Workspace", kind="preference"):
    return {"kind": kind, "title": title, "body": body}


def test_memory_persists_edits_searches_deletes_and_migrates(db):
    store = LocalMemory(db)
    identifier = store.save(entry("नमस्ते project", kind="project"))
    assert store.search("नमस्ते")[0]["id"] == identifier
    reopened = Database(db.path)
    try:
        assert reopened.rows("PRAGMA user_version")[0]["user_version"] == 4
        assert LocalMemory(reopened).search()[0]["body"] == "नमस्ते project"
    finally:
        reopened.close()
    store.save(entry("Updated preference"), identifier)
    assert not store.search("नमस्ते")
    store.delete(identifier)
    assert not store.search()
    store.save(entry())
    store.clear()
    assert not store.search()


@pytest.mark.parametrize("bad", [
    entry("password: fixture-not-a-real-secret"), entry("api key = fixture-dummy-value"),
    entry("-----BEGIN TEST PRIVATE KEY-----"), entry("x" * 8001),
    entry(kind=[]), {"kind": "project", "title": "x", "body": "x", "admin": True},
])
def test_memory_rejects_obvious_secrets_and_invalid_data(bad, db):
    with pytest.raises(ValueError):
        validate_entry(bad)
    assert not LocalMemory(db).search()


def test_import_validates_all_before_writes_and_deduplicates(db):
    store = LocalMemory(db)
    store.save(entry())
    exported = store.export_text()
    assert "providers" not in exported and "key" not in json.loads(exported)
    assert store.import_text(exported) == 0
    invalid = {"version": 1, "memories": [entry("valid", "new"), entry("password = fixture-invalid")]}
    with pytest.raises(ValueError):
        store.import_text(json.dumps(invalid))
    assert len(store.search()) == 1
    payload = {"version": 1, "memories": [entry("new approved context", "New"), entry("new approved context", "New")]}
    assert store.import_text(json.dumps(payload)) == 1
    with pytest.raises(ValueError):
        store.save(entry(), "missing")
    cancelled = Event()
    cancelled.set()
    with pytest.raises(ValueError, match="cancelled"):
        store.import_text(json.dumps({"version": 1, "memories": [entry("Not imported", "Cancelled")]}), cancelled)
    assert not store.search("Not imported")


def test_untrusted_tool_output_cannot_save_memory(db):
    with pytest.raises(ValueError, match="unsupported tool"):
        validate_steps([{"tool": "memory_save", "arguments": entry("Injected context")}])
    assert not LocalMemory(db).search()


def test_old_schema_upgrade_preserves_records_and_future_schema_is_rejected(tmp_path):
    path = tmp_path / "migration.db"
    original = Database(path)
    original.execute("INSERT INTO snippets VALUES (?,?,?)", ("keep", "Work", "Original"))
    original.execute("DROP TABLE local_memories")
    original.execute("DROP TABLE document_index")
    original.execute("PRAGMA user_version=3")
    original.close()
    upgraded = Database(path)
    assert upgraded.rows("SELECT text FROM snippets")[0]["text"] == "Original"
    assert LocalMemory(upgraded).save(entry())
    upgraded.execute("PRAGMA user_version=99")
    upgraded.close()
    with pytest.raises(Exception, match="newer NEXIS"):
        Database(path)


def test_filename_metadata_filters_ranking_and_safe_wildcard(tmp_path):
    root = tmp_path / "approved"
    root.mkdir()
    early = root / "report-first.txt"
    late = root / "report-later.txt"
    early.write_bytes(b"a" * 10)
    late.write_bytes(b"b" * 100)
    os.utime(early, (1000000000, 1000000000))
    os.utime(late, (1700000000, 1700000000))
    result = search([str(root)], "report", filters=SearchFilters(50, 200, 1600000000, 1800000000))
    assert result.paths == [str(late)] and result.metadata[str(late)]["bytes"] == 100
    assert len(search([str(root)], "*", ".txt").paths) == 2
    assert search([str(root)], "report").paths[0] == str(late)
    cancelled = Event()
    cancelled.set()
    assert search([str(root)], "*", cancel=cancelled).cancelled


@pytest.mark.parametrize("kwargs", [{"min_bytes": -1}, {"min_bytes": True},
    {"min_bytes": 10, "max_bytes": 1}, {"modified_after": float("nan")},
    {"modified_after": 20, "modified_before": 10}])
def test_invalid_search_bounds_rejected(kwargs):
    with pytest.raises(ValueError):
        SearchFilters(**kwargs)


def test_search_rechecks_access_during_enumeration(tmp_path):
    root = tmp_path / "approved"
    root.mkdir()
    (root / "x.txt").touch()
    calls = []

    def check():
        calls.append(1)
        if len(calls) > 1:
            raise ValueError("Permission revoked")

    with pytest.raises(ValueError, match="revoked"):
        search([str(root)], "*", access_check=check)


def test_index_is_opt_in_bounded_local_and_excludes_stale_unapproved_or_secret_text(db, tmp_path):
    root = tmp_path / "approved"
    root.mkdir()
    good = root / "notes.md"
    good.write_text("Useful approved context about a reactor", encoding="utf-8")
    (root / "secret.txt").write_text("password: fixture-invalid")
    (root / "large.txt").write_bytes(b"x" * 32769)
    (root / "unsupported.pdf").write_bytes(b"not parsed")
    db.set_setting("search_roots", [str(root)])
    index = DocumentIndex(db)
    assert not index.find("reactor", Event())
    report = index.build(Event())
    assert report["indexed"] == 1 and report["skipped"] == 2
    assert index.find("reactor", Event())[0]["path"] == str(good)
    assert "fixture-invalid" not in str(db.rows("SELECT * FROM document_index"))
    good.write_text("Changed document; old text must not appear")
    assert not index.find("reactor", Event())
    cancelled = Event()
    cancelled.set()
    with pytest.raises(ValueError, match="cancelled"):
        index.build(cancelled)
    assert db.rows("SELECT COUNT(*) AS count FROM document_index")[0]["count"] == 1
    db.set_setting("search_roots", [])
    assert not index.find("reactor", Event())
    index.clear()
    assert not db.rows("SELECT * FROM document_index")


def test_index_and_health_cancel_without_side_effects(db, tmp_path, monkeypatch):
    cancel = Event()
    cancel.set()
    assert health_snapshot(tmp_path, cancel) is None
    grants = db.setting("access_permissions")
    grants["approved_folder_access"] = False
    db.set_setting("access_permissions", grants)
    with pytest.raises(ValueError, match="Permission denied"):
        DocumentIndex(db).find("text", Event())


def test_health_degraded_sensors_are_reported_without_network_probe(tmp_path, monkeypatch):
    import nexis.platform.health as health
    monkeypatch.setattr(health, "power_status", lambda: "No system battery detected")
    monkeypatch.setattr(health, "network_status", lambda: "Windows reports no connection; reachability not verified")
    monkeypatch.setattr(health, "top_processes", lambda cancel: [])
    value = health_snapshot(tmp_path, Event())
    assert "Unavailable" in value["temperature"] and value["top_processes"] == []
    assert value["disk_total_gb"] > 0 and "not verified" in value["network"]
    assert Path(tmp_path).is_dir()
