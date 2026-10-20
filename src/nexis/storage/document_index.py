"""Opt-in bounded plaintext index. Content is untrusted and never sent to AI."""

from pathlib import Path

from nexis.actions.files import search
from nexis.actions.operator_files import safe_path
from nexis.core.access import require_access
from nexis.storage.memory import _SECRET

MAX_DOCUMENT_BYTES = 32768
MAX_DOCUMENTS = 200


class DocumentIndex:
    def __init__(self, db):
        self.db = db

    def approved(self, roots):
        require_access(self.db, "approved_folder_access")
        if self.db.setting("search_roots") != roots:
            raise ValueError("Approved folders changed. Rebuild with current folder approvals.")

    def build(self, cancel, progress=lambda count: None):
        roots = self.db.setting("search_roots")
        self.approved(roots)
        if not roots:
            raise ValueError("Approve local folders in Settings first.")
        report = search(roots, "*", cancel=cancel, limit=5000,
                        access_check=lambda: self.approved(roots))
        staged, skipped = [], 0
        for raw in report.paths:
            self.approved(roots)
            if cancel.wait(0.002):
                raise ValueError("Index build cancelled; previous index preserved.")
            if len(staged) >= MAX_DOCUMENTS:
                break
            path = Path(raw)
            if path.suffix.casefold() not in {".txt", ".md"}:
                continue
            try:
                path = safe_path(raw, roots, data_dir=self.db.path.parent)
                before = path.stat()
                if before.st_size > MAX_DOCUMENT_BYTES:
                    skipped += 1
                    continue
                with path.open("rb") as stream:
                    content = stream.read(MAX_DOCUMENT_BYTES + 1)
                    after = path.stat()
                # Revalidate path/metadata after the read; do not index changed files.
                safe_path(raw, roots, data_dir=self.db.path.parent)
                if len(content) > MAX_DOCUMENT_BYTES or (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                    skipped += 1
                    continue
                text = content.decode("utf-8-sig")
                if "\x00" in text or _SECRET.search(text):
                    skipped += 1
                    continue
                staged.append((str(path), before.st_size, before.st_mtime_ns, text))
                progress(len(staged))
            except (OSError, ValueError, UnicodeError):
                skipped += 1
        self.approved(roots)
        if cancel.is_set():
            raise ValueError("Index build cancelled; previous index preserved.")
        with self.db.lock, self.db.connection:
            self.db.connection.execute("DELETE FROM document_index")
            self.db.connection.executemany("INSERT INTO document_index VALUES (?,?,?,?)", staged)
            if cancel.is_set():
                raise ValueError("Index build cancelled; previous index preserved.")
        return {"indexed": len(staged), "skipped": skipped,
                "limited": report.limited or len(staged) == MAX_DOCUMENTS}

    def find(self, query, cancel):
        if not isinstance(query, str) or not 1 <= len(query.strip()) <= 300:
            raise ValueError("Use a content search of 1–300 characters.")
        roots = self.db.setting("search_roots")
        self.approved(roots)
        results = []
        for row in self.db.rows("SELECT * FROM document_index LIMIT ?", (MAX_DOCUMENTS,)):
            self.approved(roots)
            if cancel.is_set():
                raise ValueError("Content search cancelled.")
            try:
                path = safe_path(row["path"], roots, data_dir=self.db.path.parent)
                info = path.stat()
                if (info.st_size, info.st_mtime_ns) != (row["bytes"], row["modified_ns"]):
                    continue
                position = row["body"].casefold().find(query.casefold())
                if position >= 0:
                    results.append({"path": str(path), "bytes": info.st_size,
                                    "modified": info.st_mtime, "excerpt": row["body"][max(0, position - 60):position + 180]})
            except (OSError, ValueError):
                continue
        return results

    def clear(self):
        self.db.execute("DELETE FROM document_index")
