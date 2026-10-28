from pathlib import Path
from datetime import datetime, timezone, timedelta
from PySide6.QtCore import Qt

from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from nexis.actions.files import scoped, SearchFilters
from nexis.core.access import require_access
from nexis.core.results import Preview, Risk
from nexis.ui import dialogs
from nexis.ui.workers import SearchWorker


def button(text, callback, layout):
    control = QPushButton(text)
    control.setToolTip(text)

    def invoke():
        try:
            callback()
        except Exception as exc:
            import logging

            logging.getLogger("nexis").warning("UI action failed (%s)", type(exc).__name__)
            QMessageBox.warning(
                control.window(),
                "Action could not complete",
                str(exc)
                if isinstance(exc, ValueError)
                else "Check local storage and target permissions. See Diagnostics.",
            )

    control.clicked.connect(invoke)
    if layout is not None:
        layout.addWidget(control)
    return control


def heading(layout, title, subtitle):
    label = QLabel(title)
    label.setObjectName("pageTitle")
    layout.addWidget(label)
    hint = QLabel(subtitle)
    hint.setWordWrap(True)
    layout.addWidget(hint)


class ResourcePage(QWidget):
    def __init__(self, window, table):
        super().__init__()
        self.window, self.table_name = window, table
        layout = QVBoxLayout(self)
        heading(
            layout,
            {
                "shortcuts": "Applications & websites",
                "snippets": "Your snippets",
                "workflows": "Workflows",
            }[table],
            {
                "shortcuts": "Approved launch targets. Custom executables require confirmation at each launch.",
                "snippets": "Local text, organised by category. Do not save passwords or access tokens.",
                "workflows": "A sequence of approved actions. Stops at the first failed or cancelled step.",
            }[table],
        )
        self.filter = QLineEdit()
        self.filter.setPlaceholderText("Search by name or category")
        self.filter.textChanged.connect(self.refresh)
        layout.addWidget(self.filter)
        if table == "shortcuts":
            row = QHBoxLayout()
            for name in ("notepad", "calculator", "explorer", "paint"):
                button(name.title(), lambda n=name: window.submit("open " + n), row)
            layout.addLayout(row)
        self.list = QTableWidget(0, 2)
        self.list.setHorizontalHeaderLabels(["Name", "Category / type / steps"])
        self.list.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.list.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.list)
        row = QHBoxLayout()
        button("Add", self.add, row)
        button("Edit", self.edit, row)
        button("Delete", self.delete, row)
        button({"shortcuts": "Open", "snippets": "Copy", "workflows": "Run"}[table], self.run, row)
        if table == "workflows":
            button("Preview", self.preview, row)
        layout.addLayout(row)
        self.refresh()

    def refresh(self):
        import json

        query = self.filter.text().casefold()
        rows = self.window.db.rows("SELECT * FROM " + self.table_name + " ORDER BY name")
        self.rows = [
            r
            for r in rows
            if query in r["name"].casefold() or query in r.get("category", "").casefold()
        ]
        self.list.setRowCount(len(self.rows))
        for i, row in enumerate(self.rows):
            detail = row.get("category", row.get("kind", ""))
            if self.table_name == "workflows":
                try:
                    detail = str(len(json.loads(row["steps"]))) + " steps"
                except (ValueError, TypeError):
                    detail = "Invalid workflow — edit to repair"
            self.list.setItem(i, 0, QTableWidgetItem(row["name"]))
            self.list.setItem(i, 1, QTableWidgetItem(detail))
        self.list.resizeColumnToContents(0)

    def selected(self):
        i = self.list.currentRow()
        if i < 0:
            raise ValueError("Select an item first.")
        return self.rows[i]

    def add(self):
        self.editor(None)

    def edit(self):
        self.editor(self.selected())

    def editor(self, row):
        import json

        row = row or {}
        if self.table_name == "snippets":
            fields = {
                "Name": row.get("name", ""),
                "Category": row.get("category", "General"),
                "Text": row.get("text", ""),
            }
            data = dialogs.edit(self, "Snippet", fields, ("Text",))
            if data:
                if not self.approve_replacement(data, row):
                    return
                self.window.repo.save_snippet(data["Name"], data["Category"], data["Text"])
        elif self.table_name == "shortcuts":
            fields = {
                "Name": row.get("name", ""),
                "Type (application or website)": row.get("kind", "website"),
                "Target (absolute .exe path or HTTPS URL)": row.get("target", ""),
            }
            data = dialogs.edit(self, "Shortcut", fields)
            if data:
                if not self.approve_replacement(data, row):
                    return
                target = data["Target (absolute .exe path or HTTPS URL)"]
                kind = data["Type (application or website)"].strip().lower()
                if kind == "application" and not dialogs.confirm(
                    self,
                    Preview(
                        "Trust executable",
                        target,
                        "Allow this executable to run with your account permissions. "
                        "Only add applications you trust; executable identity is not verified.",
                        Risk.HIGH,
                    ),
                ):
                    return
                self.window.repo.save_shortcut(data["Name"], kind, target)
        else:
            try:
                steps = "\n".join(json.loads(row.get("steps", "[]")))
            except (ValueError, TypeError):
                steps = ""
            data = dialogs.edit(
                self,
                "Workflow",
                {"Name": row.get("name", ""), "Steps (one command per line)": steps},
                ("Steps (one command per line)",),
            )
            if data:
                if not self.approve_replacement(data, row):
                    return
                commands = [
                    s.strip()
                    for s in data["Steps (one command per line)"].splitlines()
                    if s.strip()
                ]
                # Validate targets with the same core preparation path used at execution.
                from nexis.core.router import Engine
                from nexis.core.parser import parse

                for command in commands:
                    Engine(self.window.db).prepare(parse(command))
                self.window.repo.save_workflow(data["Name"], commands)
        if data:
            new_name = data["Name"].strip().lower()
            if row and row["name"] != new_name:
                self.window.repo.delete(self.table_name, row["name"])
            self.refresh()

    def approve_replacement(self, data, original):
        title = data["Name"].strip().lower()
        if title == original.get("name"):
            return True
        existing = self.window.db.rows(
            "SELECT name FROM " + self.table_name + " WHERE name=?", (title,)
        )
        return not existing or dialogs.confirm(
            self,
            Preview("Replace saved item", title, "Overwrite this existing saved item.", Risk.HIGH),
        )

    def delete(self):
        row = self.selected()
        if dialogs.confirm(
            self,
            Preview(
                "Delete saved item", row["name"], "Permanently remove this saved item.", Risk.HIGH
            ),
        ):
            self.window.repo.delete(self.table_name, row["name"])
            self.refresh()

    def run(self):
        action = {"shortcuts": "open", "snippets": "copy", "workflows": "run"}[self.table_name]
        self.window.submit(action + " " + self.selected()["name"])

    def preview(self):
        from nexis.core.parser import parse
        from nexis.core.router import Engine

        preview, _ = Engine(self.window.db).prepare(parse("run " + self.selected()["name"]))
        QMessageBox.information(self, "Workflow preview", preview.target)


class FilesPage(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window, self.worker = window, None
        self.index_jobs = []
        from nexis.storage.document_index import DocumentIndex
        self.index_store = DocumentIndex(window.db)
        layout = QVBoxLayout(self)
        heading(
            layout,
            "Find your files",
            "Filename search within approved folders only. Results are limited to 1,000 files.",
        )
        row = QHBoxLayout()
        self.query = QLineEdit()
        self.query.setPlaceholderText("Partial filename, e.g. report")
        self.query.returnPressed.connect(self.start)
        self.extension = QLineEdit()
        self.extension.setPlaceholderText("Extension, e.g. .pdf")
        self.extension.setMaximumWidth(190)
        row.addWidget(self.query)
        row.addWidget(self.extension)
        self.start_button = button("Search", self.start, row)
        button("Cancel search", self.cancel, row)
        layout.addLayout(row)
        filters = QHBoxLayout()
        self.min_size = QLineEdit()
        self.min_size.setPlaceholderText("Minimum bytes (optional)")
        self.max_size = QLineEdit()
        self.max_size.setPlaceholderText("Maximum bytes (optional)")
        self.after = QLineEdit()
        self.after.setPlaceholderText("Modified from YYYY-MM-DD (UTC)")
        self.before = QLineEdit()
        self.before.setPlaceholderText("Through YYYY-MM-DD (UTC)")
        for field in (self.min_size, self.max_size, self.after, self.before):
            field.setAccessibleName(field.placeholderText())
            filters.addWidget(field)
        layout.addLayout(filters)
        self.status = QLabel("Approve folders in Settings to begin.")
        layout.addWidget(self.status)
        self.results = QListWidget()
        self.results.setWordWrap(True)
        layout.addWidget(self.results)
        self.metadata = QLabel("Select a result for safe size/date metadata. Use * as the filename to filter all names.")
        self.metadata.setTextFormat(Qt.PlainText)
        self.metadata.setWordWrap(True)
        self.results.currentTextChanged.connect(self.preview_metadata)
        layout.addWidget(self.metadata)
        self.result_metadata = {}
        button("Open selected file location", self.open_location, layout)
        row = QHBoxLayout()
        self.content_query = QLineEdit()
        self.content_query.setPlaceholderText("Optional local text-index search")
        self.content_query.setAccessibleName("Search previously indexed local document text")
        row.addWidget(self.content_query)
        button("Search indexed text", self.find_content, row)
        button("Build / refresh text index…", self.build_index, row)
        button("Delete text index…", self.clear_index, row)
        layout.addLayout(row)
        hint = QLabel("Opt-in index: UTF-8 .txt/.md only, 32 KB per file, 200 documents; bounded 5,000-candidate scan. Contents stay local in plaintext. No PDF/Office parsing, uploads or execution. Changed/unapproved files are excluded from results.")
        hint.setWordWrap(True)
        layout.addWidget(hint)

    def start(self):
        if self.worker and self.worker.isRunning():
            return
        require_access(self.window.db, "approved_folder_access")
        roots = self.window.db.setting("search_roots")
        if not roots:
            self.status.setText("Add approved folders in Settings first.")
            return
        def date_value(field, ending=False):
            if not field.text().strip():
                return None
            try:
                value = datetime.strptime(field.text().strip(), "%Y-%m-%d").replace(tzinfo=timezone.utc)
                return (value + timedelta(days=1, microseconds=-1) if ending else value).timestamp()
            except ValueError:
                raise ValueError("Use dates in YYYY-MM-DD format (UTC).") from None

        try:
            minimum = int(self.min_size.text()) if self.min_size.text().strip() else 0
            maximum = int(self.max_size.text()) if self.max_size.text().strip() else None
        except ValueError:
            raise ValueError("File sizes must be whole numbers of bytes.") from None
        filters = SearchFilters(minimum, maximum, date_value(self.after), date_value(self.before, True))
        self.results.clear()
        self.start_button.setEnabled(False)
        self.status.setText("Searching…")
        def access_check():
            require_access(self.window.db, "approved_folder_access")
            if self.window.db.setting("search_roots") != roots:
                raise ValueError("Approved folders changed. Search stopped; start again with current approvals.")

        self.worker = SearchWorker(roots, self.query.text(), self.extension.text(), filters, access_check)
        self.worker.progress.connect(
            lambda count: self.status.setText(f"Searching… {count} files inspected")
        )
        self.worker.completed.connect(self.completed)
        self.worker.failed.connect(self.status.setText)
        self.worker.finished.connect(lambda: self.start_button.setEnabled(True))
        self.worker.start()

    def completed(self, report):
        self.result_metadata = report.metadata
        self.results.addItems(report.paths)
        status = "Cancelled" if report.cancelled else "Complete"
        self.status.setText(
            f"{status}: {len(report.paths)} matches, {report.visited} files checked, "
            f"{report.inaccessible} inaccessible. "
            + ("Result limit reached; narrow your search." if report.limited else "")
        )

    def preview_metadata(self, path):
        value = self.result_metadata.get(path)
        if value:
            modified = datetime.fromtimestamp(value["modified"], timezone.utc).isoformat()
            self.metadata.setText(f"{value['bytes']:,} bytes · Modified {modified}\n{path}"
                                  + ("\nUntrusted indexed excerpt: " + value["excerpt"] if "excerpt" in value else ""))

    def index_task(self, operation, callback):
        from nexis.ui.setup_services import Task
        if any(job.isRunning() for job in self.index_jobs):
            self.status.setText("Wait for the current index operation, or cancel it.")
            return
        for old in self.index_jobs:
            old.deleteLater()
        self.index_jobs.clear()
        task = Task(operation, self)
        task.result.connect(callback)
        task.failed.connect(self.status.setText)
        self.index_jobs.append(task)
        self.status.setText("Processing the local text index…")
        task.start()

    def build_index(self):
        require_access(self.window.db, "approved_folder_access")
        if QMessageBox.question(self, "Approve local text indexing?", "This copies supported document text from approved folders into your local plaintext database. Do not include sensitive folders; secret detection is best effort. Nothing is sent to AI. Build a bounded index and replace the previous cache?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes:
            self.index_task(lambda cancel, progress: self.index_store.build(cancel),
                lambda report: self.status.setText(f"Indexed {report['indexed']} documents; {report['skipped']} skipped. " + ("Bounds reached; narrow approved folders for better coverage." if report["limited"] else "Local index ready.")))

    def find_content(self):
        require_access(self.window.db, "approved_folder_access")
        query = self.content_query.text()

        def loaded(rows):
            self.results.clear()
            self.result_metadata = {row["path"]: row for row in rows}
            self.results.addItems([row["path"] for row in rows])
            self.status.setText(f"{len(rows)} current, approved indexed matches. No file was opened or uploaded.")

        self.index_task(lambda cancel, progress: self.index_store.find(query, cancel), loaded)

    def clear_index(self):
        for job in self.index_jobs:
            if job.isRunning():
                self.status.setText("Cancel and finish the index operation before deleting the cache.")
                return
        if QMessageBox.question(self, "Delete local text index?", "Delete cached document text? Original files are preserved. This is ordinary SQLite deletion, not forensic secure erasure.", QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes:
            self.index_store.clear()
            self.results.clear()
            self.result_metadata.clear()
            self.metadata.clear()
            self.status.setText("Text index deleted. Private backups may retain previous copies.")

    def cancel(self):
        if self.worker:
            self.worker.cancel.set()
        for job in self.index_jobs:
            job.cancel.set()

    def open_location(self):
        require_access(self.window.db, "approved_folder_access")
        item = self.results.currentItem()
        if not item:
            raise ValueError("Select a file first.")
        parent = scoped(Path(item.text()).parent, self.window.db.setting("search_roots"))
        self.window.submit("folder " + str(parent))


class HistoryPage(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window = window
        layout = QVBoxLayout(self)
        heading(
            layout,
            "Command history",
            "Only action names and status are saved. Arguments and snippet contents are excluded.",
        )
        self.query = QLineEdit()
        self.query.setPlaceholderText("Filter actions, timestamps or status")
        self.query.textChanged.connect(self.refresh)
        layout.addWidget(self.query)
        self.list = QTableWidget(0, 4)
        self.list.setHorizontalHeaderLabels(["Timestamp (UTC)", "Action", "Status", "Summary"])
        self.list.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.list.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.list)
        button("Clear history…", lambda: window.submit("clear history"), layout)
        self.refresh()

    def refresh(self):
        query = self.query.text().casefold()
        rows = self.window.db.rows(
            "SELECT timestamp,command,status,summary FROM history ORDER BY id DESC"
        )
        rows = [r for r in rows if query in " ".join(r.values()).casefold()]
        self.list.setRowCount(len(rows))
        for i, row in enumerate(rows):
            for j, value in enumerate(row.values()):
                self.list.setItem(i, j, QTableWidgetItem(value))
        self.list.resizeColumnsToContents()
