"""User-owned local notes. No document or model output can invoke a save."""

from pathlib import Path

from PySide6.QtCore import Qt, QSaveFile, QIODevice
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPlainTextEdit, QLabel,
    QComboBox, QListWidget, QListWidgetItem, QFileDialog, QMessageBox,
)

from nexis.storage.memory import LocalMemory, KINDS, MAX_IMPORT_BYTES
from nexis.ui.pages import heading, button
from nexis.ui.setup_services import Task, safe_ui


class MemoryPage(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window, self.store = window, LocalMemory(window.db)
        self.current_id = None
        self.jobs = []
        layout = QVBoxLayout(self)
        heading(layout, "LOCAL MEMORY", "Saved only after your approval. Never store passwords, keys, sensitive documents or screenshots. Detection is best effort. Notes stay local and are never automatically added to AI requests.")
        self.query = QLineEdit()
        self.query.setPlaceholderText("Search your memories")
        self.query.textChanged.connect(self.refresh)
        layout.addWidget(self.query)
        self.list = QListWidget()
        self.list.setMaximumHeight(160)
        self.list.currentItemChanged.connect(self.load)
        layout.addWidget(self.list)
        row = QHBoxLayout()
        self.kind = QComboBox()
        for key, name in KINDS.items():
            self.kind.addItem(name, key)
        row.addWidget(self.kind)
        self.title = QLineEdit()
        self.title.setMaxLength(120)
        self.title.setPlaceholderText("Memory title")
        self.title.setAccessibleName("Memory title")
        row.addWidget(self.title, 1)
        layout.addLayout(row)
        self.body = QPlainTextEdit()
        self.body.setPlaceholderText("Text to remember — review it, then Save approved memory")
        self.body.setAccessibleName("Approved local memory text")
        layout.addWidget(self.body, 1)
        row = QHBoxLayout()
        button("New", self.new, row)
        button("Save approved memory", self.save, row)
        button("Delete selected…", self.delete, row)
        button("Delete all…", self.clear, row)
        layout.addLayout(row)
        row = QHBoxLayout()
        button("Export local memories…", self.export, row)
        button("Import reviewed memories…", self.import_file, row)
        button("Cancel import", self.cancel_import, row)
        layout.addLayout(row)
        self.status = QLabel("Nothing is saved from chat or files automatically.")
        self.status.setTextFormat(Qt.PlainText)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.refresh()

    def refresh(self, *args):
        self.list.blockSignals(True)
        self.list.clear()
        for row in self.store.search(self.query.text()[:300]):
            item = QListWidgetItem(KINDS.get(row["kind"], "Memory") + " / " + row["title"])
            item.setData(Qt.UserRole, row)
            self.list.addItem(item)
        self.list.blockSignals(False)

    def load(self, item, previous=None):
        if not item:
            return
        row = item.data(Qt.UserRole)
        self.current_id = row["id"]
        self.kind.setCurrentIndex(self.kind.findData(row["kind"]))
        self.title.setText(row["title"])
        self.body.setPlainText(row["body"])

    def new(self):
        self.current_id = None
        self.title.clear()
        self.body.clear()
        self.list.setCurrentRow(-1)

    def draft(self, text):
        self.new()
        self.kind.setCurrentIndex(self.kind.findData("memory"))
        self.title.setText(text.splitlines()[0][:120])
        self.body.setPlainText(text[:8000])
        self.status.setText("DRAFT ONLY. Review the text and click Save approved memory to persist it.")

    @safe_ui
    def save(self):
        if self.current_id and QMessageBox.question(self, "Update memory?", "Replace this saved memory with the reviewed text?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        self.current_id = self.store.save({"kind": self.kind.currentData(), "title": self.title.text(), "body": self.body.toPlainText()}, self.current_id)
        self.refresh()
        self.status.setText("Memory saved locally. It was not sent to any provider.")

    def delete(self):
        if self.import_busy():
            return
        if self.current_id and QMessageBox.question(self, "Delete memory?", "Permanently delete this local note?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes:
            self.store.delete(self.current_id)
            self.new()
            self.refresh()
            self.status.setText("Memory deleted.")

    def clear(self):
        if self.import_busy():
            return
        if QMessageBox.question(self, "Delete all memories?", "Permanently delete all local memories? Export a private backup first if needed.", QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes:
            self.store.clear()
            self.new()
            self.refresh()
            self.status.setText("All memories deleted. Ordinary SQLite deletion is not forensic secure erasure; private backups may retain copies.")

    @safe_ui
    def export(self):
        text = self.store.export_text().encode("utf-8")
        path, _ = QFileDialog.getSaveFileName(self, "Private local memory export", "nexis-memories.json", "JSON (*.json)")
        if not path:
            return
        if Path(path).is_symlink():
            raise ValueError("Choose a regular local file, not a link.")
        output = QSaveFile(path)
        if not output.open(QIODevice.WriteOnly) or output.write(text) != len(text) or not output.commit():
            output.cancelWriting()
            raise ValueError("The private export could not be saved. Previous file contents were preserved.")
        self.status.setText("Private plaintext export saved. Keep it secure; no upload was performed.")

    @safe_ui
    def import_file(self):
        if any(job.isRunning() for job in self.jobs):
            return
        path, _ = QFileDialog.getOpenFileName(self, "Import reviewed non-secret memories", "", "JSON (*.json)")
        if not path:
            return
        if QMessageBox.question(self, "Approve memory import?", "Only import notes you reviewed and trust. This adds local data without executing it or sending it to AI. Import this file?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return

        def operation(cancel, progress):
            source = Path(path)
            if source.is_symlink() or not source.is_file() or source.stat().st_size > MAX_IMPORT_BYTES:
                raise ValueError("Choose a regular memory JSON file under 40 MB.")
            with source.open("rb") as stream:
                data = stream.read(MAX_IMPORT_BYTES + 1)
            if cancel.is_set():
                return 0
            if len(data) > MAX_IMPORT_BYTES:
                raise ValueError("Memory import is limited to 40 MB.")
            return self.store.import_text(data.decode("utf-8"), cancel)

        for old in self.jobs:
            old.deleteLater()
        self.jobs.clear()
        task = Task(operation, self)
        task.result.connect(self.imported)
        task.failed.connect(self.status.setText)
        self.jobs.append(task)
        self.status.setText("Validating the complete local import…")
        task.start()

    def imported(self, count):
        self.refresh()
        self.status.setText(f"Imported {count} new approved memories; duplicates skipped. No AI request was sent.")

    def import_busy(self):
        busy = any(job.isRunning() for job in self.jobs)
        if busy:
            self.status.setText("Cancel or finish the active import before deleting memories.")
        return busy

    def cancel_import(self):
        for job in self.jobs:
            job.cancel.set()
        self.status.setText("Import cancellation requested. A transaction already completed before cancellation is retained.")
