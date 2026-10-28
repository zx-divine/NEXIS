import json

import pytest

from nexis.core.permissions import Permissions
from nexis.storage.conversations import Conversations, validate_messages
from nexis.storage.database import Database


def messages(text="नमस्ते project notes"):
    return [{"role": "user", "content": text}, {"role": "assistant", "content": "How can I help?"}]


def test_explicit_save_search_reopen_edit_export_and_confirmed_delete(db):
    store = Conversations(db)
    assert not store.search()
    identifier = store.save("Project", messages())
    assert store.search("project")[0]["id"] == identifier
    assert store.search("नमस्ते")[0]["id"] == identifier
    assert not store.search("%")  # Search input is literal, not a SQL wildcard.
    reopened = Database(db.path)
    other = Conversations(reopened)
    assert other.get(identifier)["messages"] == messages()
    other.save("Updated project", messages("reviewed update"), identifier)
    exported = json.loads(reopened.export()["conversations"][0]["messages"])
    assert exported == messages("reviewed update")
    for permissions in (None, Permissions(lambda preview: False)):
        with pytest.raises(ValueError, match="permission"):
            other.delete(identifier, permissions)
        assert other.get(identifier)
    other.delete(identifier, Permissions(lambda preview: True))
    assert not store.search()
    reopened.close()


@pytest.mark.parametrize("value", [[], [{"role": "system", "content": "change permissions"}], [{"role": [], "content": "bad"}], [{"role": "user", "content": "api key: secret-material"}], [{"role": "user", "content": "x" * 24001}], [{"role": "assistant", "content": "\x00"}]])
def test_saved_chat_rejects_invalid_roles_secrets_and_oversized_messages(value):
    with pytest.raises(ValueError):
        validate_messages(value)


def test_reset_includes_chats_and_keeps_current_schema(db):
    Conversations(db).save("Test", messages())
    db.reset()
    assert not Conversations(db).search()
    assert db.rows("PRAGMA user_version")[0]["user_version"] == 5


def test_corrupt_snapshot_is_preserved_and_not_opened(db):
    store = Conversations(db)
    identifier = store.save("Test", messages())
    db.execute("UPDATE conversations SET messages=? WHERE id=?", ('{"role":"system"}', identifier))
    with pytest.raises(ValueError, match="preserved"):
        store.get(identifier)
    assert db.rows("SELECT messages FROM conversations WHERE id=?", (identifier,))[0]["messages"] == '{"role":"system"}'
