"""Explicit search/open/delete for saved chats. Viewing never sends provider requests."""

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QListWidget, QPlainTextEdit

from nexis.core.permissions import Permissions
from nexis.ui import dialogs
from nexis.ui.pages import button, heading


class SavedConversationsPage(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window, self.store, self.entries = window, window.chat.archive, []
        layout = QVBoxLayout(self)
        heading(layout, "Saved conversations", "Chats stay in memory until you choose Save conversation. Saved text is private plaintext under your Windows account. Export it from Settings → Memory and Privacy.")
        self.query = QLineEdit()
        self.query.setPlaceholderText("Search titles and messages")
        self.query.setAccessibleName("Search saved conversations")
        layout.addWidget(self.query)
        self.results = QListWidget()
        self.results.setAccessibleName("Saved conversations")
        layout.addWidget(self.results, 1)
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        layout.addWidget(self.preview, 2)
        row = QHBoxLayout()
        button("Open conversation", self.open_selected, row)
        button("Delete saved chat…", self.delete_selected, row)
        button("Export personal data…", lambda: window.settings_page.export(), row)
        layout.addLayout(row)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(180)
        self.query.textChanged.connect(lambda: self.timer.start())
        self.timer.timeout.connect(self.refresh)
        self.results.currentRowChanged.connect(self.show_selected)
        self.refresh()

    def refresh(self):
        if self.window.closing:
            return
        self.entries = self.store.search(self.query.text())
        self.results.clear()
        self.preview.clear()
        for row in self.entries:
            self.results.addItem(row["title"] + "  ·  " + row["updated_at"][:10])

    def hideEvent(self, event):
        self.timer.stop()
        super().hideEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh()

    def selected(self):
        index = self.results.currentRow()
        if not 0 <= index < len(self.entries):
            raise ValueError("Choose a saved conversation first.")
        return self.store.get(self.entries[index]["id"])

    def show_selected(self, index):
        if 0 <= index < len(self.entries):
            try:
                self.preview.setPlainText("\n\n".join(m["role"].upper() + ": " + m["content"] for m in self.selected()["messages"]))
            except ValueError as exc:
                self.preview.setPlainText(str(exc))

    def open_selected(self):
        if any(job.isRunning() for job in self.window.ai_jobs) or self.window.worker and self.window.worker.isRunning():
            raise ValueError("Finish or cancel active work before opening another chat.")
        row = self.selected()
        chat = self.window.chat
        chat.clear_conversation()
        chat.saved_id = row["id"]
        for message in row["messages"]:
            chat.add_message("YOU" if message["role"] == "user" else "NEXIS", message["content"])
        self.window.conversation_history = [dict(message) for message in row["messages"][-24:]]
        chat.pending_prompt = next((m["content"] for m in reversed(row["messages"]) if m["role"] == "user"), "")
        self.window.navigate("Chat")

    def delete_selected(self):
        row = self.selected()
        self.store.delete(row["id"], Permissions(lambda preview: dialogs.confirm(self, preview)))
        if self.window.chat.saved_id == row["id"]:
            self.window.chat.saved_id = None
        self.refresh()
