"""Local UI actions; provider, process and hardware effects are not simulated passes."""

from nexis.ui.main_window import MainWindow


def test_remember_drafts_until_explicit_save_and_forget_requires_selection(qtbot, db, tmp_path, platform, monkeypatch):
    def unexpected(*args):
        raise AssertionError("Memory commands must remain local")

    monkeypatch.setattr("nexis.ui.main_window.start_chat", unexpected)
    window = MainWindow(db, tmp_path, platform)
    qtbot.addWidget(window)
    window.conversation_request("Remember this: My approved project uses Python", "chat")
    assert not window.memories.store.search()
    assert "My approved project" in window.memories.body.toPlainText()
    window.memories.save()
    assert len(window.memories.store.search("Python")) == 1
    window.conversation_request("Forget this: Python", "chat")
    assert window.memories.list.count() == 1
    assert len(window.memories.store.search()) == 1  # No automatic deletion.
    assert not window.ai_jobs and not platform.calls
    window.close()


def test_spoken_memory_command_never_starts_hidden_speech_or_ai(qtbot, db, tmp_path, platform, monkeypatch):
    window = MainWindow(db, tmp_path, platform)
    qtbot.addWidget(window)
    monkeypatch.setattr(window.voice, "receive_reply", lambda text: (_ for _ in ()).throw(AssertionError("Hidden playback")))
    window.conversation_request("remember this my project uses Python", "voice")
    assert "my project" in window.memories.body.toPlainText()
    assert not window.memories.store.search() and not window.ai_jobs
    assert window.voice.turn.state.value == "IDLE"
    window.close()


def test_memory_secret_is_rejected_with_a_friendly_status(qtbot, db, tmp_path, platform):
    window = MainWindow(db, tmp_path, platform)
    qtbot.addWidget(window)
    window.memories.draft("password: fixture-invalid")
    window.memories.save()
    assert "Do not save" in window.memories.status.text()
    assert not window.memories.store.search()
    assert not window.health.jobs and window.files.index_jobs == []
    window.close()


def test_health_refresh_is_explicit_and_background_with_unavailable_values(qtbot, db, tmp_path, platform, monkeypatch):
    calls = []

    def snapshot(directory, cancel):
        calls.append(1)
        return {"cpu_percent": None, "memory_percent": None, "total_memory_mb": None,
                "available_memory_mb": None, "uptime_seconds": None, "disk_free_gb": None,
                "disk_total_gb": None, "battery": "Unavailable", "network": "Unavailable",
                "temperature": "Unavailable", "top_processes": []}

    monkeypatch.setattr("nexis.ui.health_page.health_snapshot", snapshot)
    window = MainWindow(db, tmp_path, platform)
    qtbot.addWidget(window)
    window.navigate("PC Health")
    assert not calls
    window.health.refresh()
    qtbot.waitUntil(lambda: window.health.refresh_button.isEnabled(), timeout=3000)
    assert calls == [1] and "Unavailable" in window.health.report.toPlainText()
    assert not platform.calls
    window.close()
