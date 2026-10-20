"""Local identity routing and current provider labels; no live inference claims."""

from nexis.ui.main_window import MainWindow


def test_local_identity_without_credentials_or_network(qtbot, db, tmp_path, platform, monkeypatch):
    def unexpected(*args):
        raise AssertionError("Local identity must not start AI or execute tools")

    monkeypatch.setattr("nexis.ui.main_window.start_chat", unexpected)
    window = MainWindow(db, tmp_path, platform)
    qtbot.addWidget(window)
    permissions = db.setting("access_permissions")
    permissions["network_actions"] = False
    db.set_setting("access_permissions", permissions)
    window.conversation_request("Who made you?", "chat")
    answer = window.chat.messages.item(window.chat.messages.count() - 1).text()
    assert "ASH" in answer and "could not be verified" in answer
    assert window.conversation_history[-1]["role"] == "assistant"
    assert not window.ai_jobs and not platform.calls
    assert not db.setting("access_permissions")["network_actions"]
    window.close()


def test_provider_save_switch_and_removal_refresh_labels(qtbot, db, tmp_path, platform):
    window = MainWindow(db, tmp_path, platform)
    qtbot.addWidget(window)
    manager = window.providers.manager
    profile = {"provider": "OmniRoute", "endpoint": "http://127.0.0.1:20128/v1",
               "key": "fixture-private-key", "model": "owner-first"}
    identifier = manager.save(profile)
    manager.select(identifier)
    window.providers.changed.emit()
    assert "owner-first" in window.chat.provider_status.text()
    manager.save({**profile, "model": "owner-edited"}, identifier)
    window.providers.profile_saved.emit()
    assert "owner-edited" in window.nav_hint.text()
    window.conversation_request("Which model powers you?", "chat")
    assert "owner-edited" in window.conversation_history[-1]["content"]
    manager.remove(identifier)
    window.providers.changed.emit()
    assert "No verified provider" in window.chat.provider_status.text()
    window.close()


def test_ordinary_chat_still_routes_to_operator(qtbot, db, tmp_path, platform, monkeypatch):
    routed = []
    monkeypatch.setattr("nexis.ui.main_window.start_chat", lambda window, text, origin: routed.append((text, origin)))
    window = MainWindow(db, tmp_path, platform)
    qtbot.addWidget(window)
    window.conversation_request("Explain Python classes", "chat")
    assert routed == [("Explain Python classes", "chat")]
    assert not platform.calls
    window.close()
