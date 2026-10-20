"""Explicitly approved local notes, isolated from providers and tool execution."""

from datetime import datetime, timezone
import json
import re
from uuid import uuid4

KINDS = {"preference": "Preference", "favorite_app": "Favorite application",
         "project": "Approved project context", "memory": "Approved memory",
         "summary": "Optional conversation summary"}
MAX_ITEMS = 1000
MAX_IMPORT_BYTES = 40 * 1024 * 1024  # Accommodates the largest supported UTF-8 export.
_SECRET = re.compile(
    r"(?i)(?:\b(?:password|passphrase|passcode|api[ _-]?key|access[ _-]?token|"
    r"recovery[ _-]?code|client[ _-]?secret)\s*(?:is|=|:)\s*\S+|"
    r"\b(?:sk-[A-Za-z0-9_-]{12,}|AIza[A-Za-z0-9_-]{30,}|gh[pousr]_[A-Za-z0-9]{24,}|"
    r"github_pat_[A-Za-z0-9_]{30,}|GOCSPX-[A-Za-z0-9_-]{16,})|"
    r"-----BEGIN .*PRIVATE KEY-----|credential redacted|API key redacted)"
)


def validate_entry(entry):
    if not isinstance(entry, dict) or set(entry) != {"kind", "title", "body"}:
        raise ValueError("Memory entries need a category, title and text only.")
    if not isinstance(entry["kind"], str) or entry["kind"] not in KINDS:
        raise ValueError("Choose a supported memory category.")
    result = {"kind": entry["kind"]}
    for key, limit in (("title", 120), ("body", 8000)):
        value = entry[key]
        if (not isinstance(value, str) or not 1 <= len(value.strip()) <= limit
                or any(ord(c) < 32 and c not in "\n\t" for c in value)):
            raise ValueError("Memory needs a title (120 characters) and text (8,000 characters).")
        if _SECRET.search(value):
            raise ValueError("Do not save passwords, keys, recovery codes or other secrets in memory.")
        result[key] = value.strip()
    return result


class LocalMemory:
    """No implicit writes, AI tool adapter or automatic network context injection."""

    def __init__(self, db):
        self.db = db

    def search(self, query=""):
        if not isinstance(query, str) or len(query) > 300:
            raise ValueError("Use a memory search of at most 300 characters.")
        rows = self.db.rows("SELECT * FROM local_memories ORDER BY updated_at DESC LIMIT ?", (MAX_ITEMS,))
        query = query.casefold()
        return [row for row in rows if query in (row["title"] + "\n" + row["body"]).casefold()]

    def save(self, entry, identifier=None):
        entry = validate_entry(entry)
        now = datetime.now(timezone.utc).isoformat()
        with self.db.lock, self.db.connection:
            existing = self.db.connection.execute("SELECT created_at FROM local_memories WHERE id=?", (identifier,)).fetchone() if identifier else None
            if identifier and not existing:
                raise ValueError("That memory no longer exists. Refresh the list.")
            if not existing and self.db.connection.execute("SELECT COUNT(*) FROM local_memories").fetchone()[0] >= MAX_ITEMS:
                raise ValueError("Memory limit reached. Delete or export older entries first.")
            identifier = identifier or uuid4().hex
            self.db.connection.execute("INSERT OR REPLACE INTO local_memories VALUES (?,?,?,?,?,?)",
                (identifier, entry["kind"], entry["title"], entry["body"], existing[0] if existing else now, now))
        return identifier

    def delete(self, identifier):
        self.db.execute("DELETE FROM local_memories WHERE id=?", (identifier,))

    def clear(self):
        self.db.execute("DELETE FROM local_memories")

    def export_text(self):
        return json.dumps({"version": 1, "memories": [validate_entry({k: row[k] for k in ("kind", "title", "body")}) for row in self.search()]}, ensure_ascii=False, indent=2)

    def import_text(self, text, cancel=None):
        if not isinstance(text, str) or len(text.encode("utf-8")) > MAX_IMPORT_BYTES:
            raise ValueError("Memory import is limited to 40 MB.")
        try:
            data = json.loads(text)
        except ValueError:
            raise ValueError("This is not a valid memory JSON file.") from None
        if (not isinstance(data, dict) or set(data) != {"version", "memories"}
                or type(data["version"]) is not int or data["version"] != 1
                or not isinstance(data["memories"], list) or len(data["memories"]) > MAX_ITEMS):
            raise ValueError("Import up to 1,000 entries from a supported memory export.")
        # Validate the complete import before touching the database.
        entries = [validate_entry(item) for item in data["memories"]]
        if cancel and cancel.is_set():
            raise ValueError("Memory import cancelled; previous notes preserved.")
        with self.db.lock, self.db.connection:
            known = {(row["kind"], row["title"], row["body"]) for row in self.search()}
            new = {tuple(entry[k] for k in ("kind", "title", "body")) for entry in entries} - known
            if len(known) + len(new) > MAX_ITEMS:
                raise ValueError("This import would exceed the local memory limit.")
            now = datetime.now(timezone.utc).isoformat()
            self.db.connection.executemany("INSERT INTO local_memories VALUES (?,?,?,?,?,?)",
                [(uuid4().hex, *entry, now, now) for entry in sorted(new)])
            if cancel and cancel.is_set():
                raise ValueError("Memory import cancelled; previous notes preserved.")
        return len(new)
