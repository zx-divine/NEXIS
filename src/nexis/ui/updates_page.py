"""No installer is ever executed here. Downloads open only after explicit review."""

from datetime import datetime, timezone
from pathlib import Path
import webbrowser

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, QPlainTextEdit,
    QComboBox, QMessageBox, QFileDialog,
)

from nexis import __version__
from nexis.core.access import require_access
from nexis.core.updates import check_updates, official_url, verify_download
from nexis.ui.pages import heading, button
from nexis.ui.setup_services import Task, safe_ui


class UpdatesPage(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window, self.jobs, self.release = window, [], None
        layout = QVBoxLayout(self)
        heading(layout, "OFFICIAL UPDATES", "Installed version " + __version__ + ". Discovery only from github.com/zx-divine/nexis. No account, automatic installer execution, security bypass or user-data migration is performed here.")
        self.automatic = QCheckBox("Check official release metadata on startup, at most once daily (optional)")
        self.automatic.setChecked(window.db.setting("update_checks_enabled"))
        self.automatic.toggled.connect(lambda enabled: window.db.set_setting("update_checks_enabled", enabled))
        layout.addWidget(self.automatic)
        notice = QLabel("A check sends your app version and ordinary connection metadata/IP to GitHub, never credentials, chats, audio or files. Automatic checks are off by default and also need the network capability. A same-source digest is an integrity comparison, not independent publisher authentication. Keep Windows SmartScreen enabled.")
        notice.setWordWrap(True)
        layout.addWidget(notice)
        row = QHBoxLayout()
        button("Check official releases", self.check, row)
        button("Cancel request / verification", self.cancel, row)
        layout.addLayout(row)
        self.status = QLabel("No check has run. Existing local functionality does not require an internet connection.")
        self.status.setTextFormat(Qt.PlainText)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.notes = QPlainTextEdit()
        self.notes.setReadOnly(True)
        self.notes.setAccessibleName("Untrusted official release notes; no commands execute")
        layout.addWidget(self.notes, 1)
        self.assets = QComboBox()
        self.assets.setAccessibleName("Available official release assets")
        layout.addWidget(self.assets)
        row = QHBoxLayout()
        self.page_button = button("Open release page…", self.open_page, row)
        self.download_button = button("Open selected download…", self.download, row)
        self.verify_button = button("Verify downloaded file…", self.verify, row)
        layout.addLayout(row)
        self.update_controls()

    def update_controls(self):
        self.page_button.setEnabled(bool(self.release and self.release["page"]))
        available = self.assets.count() > 0
        self.download_button.setEnabled(available)
        self.verify_button.setEnabled(available)

    def cancel(self):
        for job in self.jobs:
            job.cancel.set()

    def task(self, function, callback):
        if any(job.isRunning() for job in self.jobs):
            self.status.setText("Cancel or finish the active update operation first.")
            return False
        for old in self.jobs:
            old.deleteLater()
        self.jobs.clear()
        task = Task(function, self)
        task.result.connect(lambda value: callback(value) if not task.cancel.is_set() else None)
        task.failed.connect(self.status.setText)
        self.jobs.append(task)
        task.start()
        return True

    @safe_ui
    def check(self):
        require_access(self.window.db, "network_actions")
        if self.task(lambda cancel, progress: check_updates(cancel), self.loaded):
            self.window.db.set_setting("update_last_check", datetime.now(timezone.utc).isoformat())
            self.status.setText("Checking only official GitHub release metadata…")

    def auto_check_if_due(self):
        if not self.automatic.isChecked() or self.window.closing:
            return
        try:
            last = datetime.fromisoformat(self.window.db.setting("update_last_check"))
            elapsed = (datetime.now(timezone.utc) - last).total_seconds()
            if 0 <= elapsed < 86400:
                return
        except (ValueError, TypeError):
            pass
        self.check()

    def loaded(self, release):
        self.release = release
        self.notes.setPlainText(release["notes"])
        self.assets.clear()
        for asset in release["assets"]:
            self.assets.addItem(f"{asset['name']} · {asset['bytes'] / 1048576:.1f} MB · " + ("metadata SHA-256 available" if asset["sha256"] else "no digest supplied"), asset)
        self.update_controls()
        self.status.setText("Update available: " + release["tag"] if release["available"] else "No newer supported public release is available.")

    @safe_ui
    def open_page(self):
        require_access(self.window.db, "network_actions")
        require_access(self.window.db, "browser_control")
        if not self.release or not self.release["page"]:
            return
        target = official_url(self.release["page"], self.release["tag"])
        if QMessageBox.question(self, "Open official release?", "Open this official page in your default browser?\n" + target, QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes:
            if not webbrowser.open(target, new=2):
                raise ValueError("The browser did not accept the release-page request.")

    @safe_ui
    def download(self):
        require_access(self.window.db, "network_actions")
        require_access(self.window.db, "browser_control")
        asset = self.assets.currentData()
        if not asset or not self.release:
            return
        target = official_url(asset["url"], self.release["tag"], True)
        if QMessageBox.question(self, "Open official download?", "Your browser will handle this download. NEXIS will never execute it. Verify the downloaded file and publisher before choosing whether to install.\n" + target, QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes:
            if not webbrowser.open(target, new=2):
                raise ValueError("The browser did not accept the download request.")

    @safe_ui
    def verify(self):
        asset = self.assets.currentData()
        if not asset or not asset["sha256"]:
            raise ValueError("No valid SHA-256 was supplied for this asset. Do not treat an unverified file as authenticated.")
        path, _ = QFileDialog.getOpenFileName(self, "Select the downloaded release file", "", "Release files (*.exe *.zip)")
        if not path:
            return
        expected = asset["sha256"]
        if self.task(lambda cancel, progress: verify_download(Path(path), expected, cancel),
            lambda result: self.status.setText(("SHA-256 MATCHES release metadata. This does not authenticate the publisher or execute the file." if result["matches"] else "SHA-256 MISMATCH. Do not install this file.") + "\nComputed: " + result["sha256"])):
            self.status.setText("Reading only the selected local file to compute SHA-256…")
