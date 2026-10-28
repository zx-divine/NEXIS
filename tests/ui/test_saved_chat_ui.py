"""Saved-chat UI behavior uses the same execution-layer storage policy."""

import pytest

from nexis.ui.main_window import MainWindow


def test_save_is_explicit_and_open_preserves_context_without_network(qtbot, db, tmp_path, platform, monkeypatch):
    window = MainWindow(db, tmp_path, platform)
    qtbot.addWidget(window)
    chat = window.chat
    chat.clear_conversation()
    chat.add_message("YOU", "Plan the project")
    chat.add_message("NEXIS", "Start with a checklist")
    assert not chat.archive.search()
    monkeypatch.setattr("nexis.ui.conversation.QInputDialog.getText", lambda *args, **kwargs: ("Project plan", True))
    chat.save_conversation()
    identifier = chat.saved_id
    chat.input.setText("Private unfinished draft")
    chat.clear_conversation()
    assert not chat.input.text()
    assert chat.archive.search()[0]["id"] == identifier  # New chat does not delete a saved chat.
    saved = window.saved_conversations
    saved.results.setCurrentRow(0)
    saved.open_selected()
    assert window.stack.currentIndex() == window.pages["Chat"]
    assert window.conversation_history == [{"role": "user", "content": "Plan the project"}, {"role": "assistant", "content": "Start with a checklist"}]
    assert not window.ai_jobs and not window.voice.worker and not platform.calls
    monkeypatch.setattr("nexis.ui.saved_conversations.dialogs.confirm", lambda *args: False)
    with pytest.raises(ValueError, match="permission"):
        saved.delete_selected()
    assert chat.archive.get(identifier)
    monkeypatch.setattr("nexis.ui.saved_conversations.dialogs.confirm", lambda *args: True)
    saved.delete_selected()
    assert not chat.archive.search() and chat.saved_id is None
    window.close()
