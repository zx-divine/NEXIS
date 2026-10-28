"""Explicit local chat snapshots; no automatic saves or provider-context injection."""

from datetime import datetime, timezone
import json
from uuid import uuid4

from nexis.core.permissions import Permissions
from nexis.core.profile import preferred_name
from nexis.core.results import Preview, Risk
from nexis.storage.memory import _SECRET

MAX_CONVERSATIONS = 100


def validate_messages(messages):
    if not isinstance(messages, list) or not 1 <= len(messages) <= 200:
        raise ValueError("Save a conversation with 1–200 completed messages.")
    cleaned, total = [], 0
    for item in messages:
        if (not isinstance(item, dict) or set(item) != {"role", "content"}
                or not isinstance(item["role"], str) or item["role"] not in {"user", "assistant"}
                or not isinstance(item["content"], str) or not 1 <= len(item["content"]) <= 24000
                or any(ord(c) < 32 and c not in "\n\r\t" for c in item["content"])):
            raise ValueError("Conversation messages contain unsupported data.")
        if _SECRET.search(item["content"]):
            raise ValueError("This chat appears to contain credentials or secret material and was not saved. Keep secrets out of saved chats.")
        total += len(item["content"])
        if total > 64000:
            raise ValueError("A saved conversation is limited to 64,000 characters. Save a shorter conversation.")
        cleaned.append({"role": item["role"], "content": item["content"]})
    return cleaned


class Conversations:
    def __init__(self, db):
        self.db = db

    def search(self, query=""):
        if not isinstance(query, str) or len(query) > 300:
            raise ValueError("Search chats using at most 300 characters.")
        return self.db.rows("SELECT id,title,updated_at FROM conversations WHERE instr(lower(title || char(10) || messages),lower(?)) > 0 ORDER BY updated_at DESC LIMIT ?", (query, MAX_CONVERSATIONS))

    def get(self, identifier):
        rows = self.db.rows("SELECT * FROM conversations WHERE id=?", (identifier,))
        if not rows:
            raise ValueError("That saved chat is no longer available. Refresh the list.")
        row = rows[0]
        try:
            row["messages"] = validate_messages(json.loads(row["messages"]))
        except (ValueError, TypeError):
            raise ValueError("Saved chat data failed validation. The original was preserved.") from None
        return row

    def save(self, title, messages, identifier=None):
        title = preferred_name(title)
        if _SECRET.search(title):
            raise ValueError("Keep credentials out of chat titles.")
        messages = validate_messages(messages)
        now = datetime.now(timezone.utc).isoformat()
        with self.db.lock, self.db.connection:
            found = self.db.connection.execute("SELECT 1 FROM conversations WHERE id=?", (identifier,)).fetchone() if identifier else None
            if identifier and not found:
                raise ValueError("This saved chat was deleted. Save it as a new chat.")
            if not found and self.db.connection.execute("SELECT COUNT(*) FROM conversations").fetchone()[0] >= MAX_CONVERSATIONS:
                raise ValueError("Saved-chat limit reached (100). Export or delete older chats first.")
            identifier = identifier or uuid4().hex
            self.db.connection.execute("INSERT OR REPLACE INTO conversations VALUES (?,?,?,?)", (identifier, title, json.dumps(messages, ensure_ascii=False), now))
        return identifier

    def delete(self, identifier, permissions=None):
        row = self.get(identifier)
        preview = Preview("Delete saved conversation", row["title"], "Permanently remove this locally saved chat. External exports and backups remain. This cannot be undone.", Risk.HIGH)
        if not (permissions or Permissions()).authorise(preview):
            raise ValueError("Cancelled: permission was not granted.")
        self.db.execute("PRAGMA secure_delete=ON")
        self.db.execute("DELETE FROM conversations WHERE id=?", (identifier,))
