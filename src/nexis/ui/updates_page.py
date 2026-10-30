"""NEXIS update experience, using the existing Qt controls and theme."""

from datetime import datetime, timedelta, timezone
import json
import struct
import sys

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, QPlainTextEdit,
    QProgressBar, QDialog,
)

from nexis import __version__, PUBLIC_VERSION
from nexis.core.access import require_access
from nexis.core.update_service import UpdateService, UpdateError, CHECK_INTERVAL
from nexis.platform.update_install import WindowsInstaller, acknowledge_startup
from nexis.ui.pages import heading, button
from nexis.ui.setup_services import Task, safe_ui


def bytes_text(value):
    return f"{value / 1048576:.1f} MB" if value >= 1048576 else f"{value / 1024:.1f} KB"


class UpdatesPage(QWidget):
    changed = Signal()

    def __init__(self, window):
        super().__init__()
        self.window, self.jobs, self.release = window, [], None
        self.ready, self.preparing, self.pending_download = False, False, False
        self.notice = None
        self.notice_primary = None
        self.service, self.init_error = None, ""
        try:
            self.service = UpdateService(window.data_dir / "updates")
        except (ValueError, OSError):
            self.init_error = "The update cache is unavailable. Check folder access; NEXIS remains usable."
        layout = QVBoxLayout(self)
        heading(layout, "SOFTWARE UPDATES", "Signed updates from the official NEXIS release infrastructure. Your settings, providers, voice, permissions and saved conversations are preserved.")
        layout.addWidget(QLabel(f"Current Version: {PUBLIC_VERSION} · build {__version__}"))
        self.automatic = QCheckBox("Automatically check for updates")
        self.automatic.setChecked(window.db.setting("update_checks_enabled"))
        self.automatic.toggled.connect(self.set_automatic)
        layout.addWidget(self.automatic)
        self.auto_download = QCheckBox("Download updates automatically")
        self.auto_download.setChecked(window.db.setting("update_downloads_enabled"))
        self.auto_download.toggled.connect(self.set_downloads)
        layout.addWidget(self.auto_download)
        notice = QLabel("Checks run at launch and once daily while running. GitHub receives ordinary connection metadata and the app version. No provider keys, chats, audio or user files are sent. Downloads require signed TUF metadata and verified package hashes. Installation waits for Restart & Install.")
        notice.setWordWrap(True)
        layout.addWidget(notice)
        row = QHBoxLayout()
        self.check_button = button("Check for Updates", self.check, row)
        self.cancel_button = button("Cancel Download / Check", self.cancel, row)
        layout.addLayout(row)
        self.status = QLabel(self.init_error or "Ready to check. NEXIS works offline if an update request fails.")
        self.status.setTextFormat(Qt.PlainText)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.release_label = QLabel("")
        self.release_label.setTextFormat(Qt.PlainText)
        self.release_label.setWordWrap(True)
        layout.addWidget(self.release_label)
        self.notes = QPlainTextEdit()
        self.notes.setReadOnly(True)
        self.notes.setAccessibleName("Verified release notes")
        layout.addWidget(self.notes, 1)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setAccessibleName("Update download percentage")
        layout.addWidget(self.progress)
        self.transfer = QLabel("")
        layout.addWidget(self.transfer)
        row = QHBoxLayout()
        self.download_button = button("Download Update", self.download, row)
        self.later_button = button("Remind Me Later", self.remind_later, row)
        self.restart_button = button("Restart & Install", self.restart_install, row)
        layout.addLayout(row)
        notice = QLabel("Save unsaved chats before restarting. Active voice, AI, file and command work must finish first. You can keep using NEXIS and install later from this page.")
        notice.setWordWrap(True)
        layout.addWidget(notice)
        self.timer = QTimer(self)
        self.timer.setInterval(15 * 60 * 1000)
        self.timer.timeout.connect(self.auto_check_if_due)
        self.reminder_timer = QTimer(self)
        self.reminder_timer.setInterval(60 * 1000)
        self.reminder_timer.timeout.connect(self.show_notice_if_idle)
        self.update_controls()

    def busy(self):
        return any(job.isRunning() for job in self.jobs)

    def active_work(self):
        w = self.window
        speech = w.settings_page.voice_setup.speech
        ignored = [*self.jobs, *w.desktop_experience.wake.jobs, speech]
        return (w.closing or w.voice.capture_active or w.voice.speech_playing
                or w.desktop_experience.wake.microphone_active
                or bool(speech and speech.busy.is_set())
                or any(job and job not in ignored and job.isRunning() for job in w.background_jobs()))

    def update_controls(self):
        busy = self.busy() or self.preparing
        supported = sys.platform == "win32" and struct.calcsize("P") == 8
        self.check_button.setEnabled(not busy and supported and self.service is not None)
        self.download_button.setEnabled(bool(self.release) and not self.ready and not busy)
        self.restart_button.setVisible(self.ready)
        self.restart_button.setEnabled(self.ready and not busy)
        self.later_button.setEnabled(bool(self.release) and not self.preparing)
        self.cancel_button.setEnabled(busy)
        if not supported:
            self.status.setText("Automatic updates currently support Windows x64. No desktop binary will be installed on this platform.")
        self.changed.emit()

    def set_automatic(self, enabled):
        self.window.db.set_setting("update_checks_enabled", enabled)
        self.changed.emit()

    def set_downloads(self, enabled):
        self.window.db.set_setting("update_downloads_enabled", enabled)
        self.changed.emit()

    def cancel(self):
        for job in self.jobs:
            job.cancel.set()
        self.pending_download = False
        self.status.setText("Cancelling safely… You can retry after this request stops.")

    def task(self, function, callback):
        if self.busy():
            self.status.setText("An update operation is already running.")
            return False
        for old in self.jobs:
            old.deleteLater()
        self.jobs.clear()
        task = Task(function, self)
        task.result.connect(lambda value: callback(value) if not task.cancel.is_set() else None)
        task.failed.connect(self.failed)
        task.progress.connect(self.on_progress)
        self.jobs.append(task)
        task.finished.connect(lambda: self.finished(task))
        task.start()
        self.update_controls()
        return True

    def finished(self, task):
        if task.cancel.is_set():
            self.preparing = False
            self.status.setText("Update cancelled. NEXIS is unchanged. Retry to download a fresh verified copy.")
        self.update_controls()
        if self.pending_download and not self.window.closing:
            self.pending_download = False
            QTimer.singleShot(0, self.download)

    def failed(self, message):
        self.preparing = False
        self.pending_download = False
        self.status.setText(message + " Use Check for Updates or Download Update to retry.")
        self.update_controls()

    @safe_ui
    def check(self):
        require_access(self.window.db, "network_actions")
        if not self.service:
            raise UpdateError(self.init_error)
        if self.task(lambda cancel, progress: self.service.check(cancel), self.loaded):
            self.window.db.set_setting("update_last_check", datetime.now(timezone.utc).isoformat())
            self.status.setText("Checking signed release metadata…")
            self.changed.emit()

    def auto_check_if_due(self):
        if (not self.automatic.isChecked() or self.window.closing or self.busy()
                or self.ready or sys.platform != "win32" or struct.calcsize("P") != 8):
            return
        try:
            last = datetime.fromisoformat(self.window.db.setting("update_last_check"))
            elapsed = (datetime.now(timezone.utc) - last).total_seconds()
            if 0 <= elapsed < CHECK_INTERVAL:
                return
        except (ValueError, TypeError):
            pass
        self.check()

    def start(self):
        """After onboarding and normal startup; constructor never uses network."""
        self.timer.start()
        self.reminder_timer.start()
        if self.service:
            try:
                acknowledge_startup(self.service)
                state = self.service.read_state()
                phase = state.get("phase", "")
                if phase == "ready":
                    self.task(lambda cancel, progress: self.service.verified_staged()[0], self.restored)
                elif phase in {"install_failed", "restart_failed", "installing", "waiting", "prepared"}:
                    self.status.setText(state.get("error") or "An earlier update did not complete. Your profile and recovery copy are retained. Check again to retry, or follow UPDATE-GUIDE.md.")
                elif phase == "complete":
                    self.status.setText("NEXIS updated successfully. Your saved profile is preserved.")
            except (ValueError, OSError):
                self.status.setText("The previous update could not be restored. Check for updates to retry. Existing data is preserved.")
        self.auto_check_if_due()

    def loaded(self, release):
        if self.notice:
            self.notice.close()
        self.release, self.ready = release, False
        self.progress.setValue(0)
        self.transfer.clear()
        if release:
            self.release_label.setText(f"NEXIS Update Available\nCurrent: {PUBLIC_VERSION} (build {__version__})\nNew: {release.public_version} (build {release.build_version})\nDownload: {bytes_text(release.size)}")
            self.notes.setPlainText(release.notes)
            self.status.setText("NEXIS Update Available")
            self.pending_download = self.auto_download.isChecked()
            self.show_notice_if_idle()
        else:
            self.release_label.clear()
            self.notes.setPlainText("No newer compatible signed release is available.")
            self.status.setText("NEXIS is up to date. Older releases are ignored.")
        self.update_controls()

    @safe_ui
    def download(self):
        require_access(self.window.db, "network_actions")
        if not self.release or self.ready or not self.service:
            return
        if self.task(lambda cancel, progress: self.service.download(self.release, cancel,
                     lambda data: progress(json.dumps(data))), self.restored):
            self.status.setText("Downloading update… The package is verified before it becomes ready.")

    def on_progress(self, value):
        try:
            data = json.loads(value)
        except (ValueError, TypeError):
            self.status.setText(value)
            return
        self.progress.setValue(min(100, int(data["transferred"] * 100 / data["total"])))
        self.transfer.setText(f"{bytes_text(data['transferred'])} / {bytes_text(data['total'])} · {bytes_text(data['speed'])}/s")
        self.changed.emit()

    def restored(self, release):
        self.release, self.ready = release, True
        if self.notice_primary:
            self.notice_primary.setText("Restart & Install")
        self.release_label.setText(f"New version: {release.public_version} · build {release.build_version}\nDownload: {bytes_text(release.size)}")
        self.notes.setPlainText(release.notes)
        self.progress.setValue(100)
        self.status.setText("Update verified and ready. Restart & Install when your work is saved.")
        self.update_controls()
        self.show_notice_if_idle()

    def remind_later(self):
        self.window.db.set_setting("update_remind_after", (datetime.now(timezone.utc) + timedelta(days=1)).isoformat())
        if self.notice:
            self.notice.close()
        self.status.setText("Reminder postponed for a day. You can install anytime from Software Updates.")
        self.changed.emit()

    def show_notice_if_idle(self):
        if not self.release or self.active_work() or (self.notice and self.notice.isVisible()):
            return
        try:
            until = datetime.fromisoformat(self.window.db.setting("update_remind_after"))
            if until > datetime.now(timezone.utc):
                return
        except (ValueError, TypeError):
            pass
        if self.notice:
            self.notice.deleteLater()
        self.notice = QDialog(self.window)
        self.notice.setWindowTitle("NEXIS Update Available")
        self.notice.setAttribute(Qt.WA_ShowWithoutActivating)
        self.notice.setMinimumWidth(460)
        layout = QVBoxLayout(self.notice)
        label = QLabel(f"NEXIS Update Available\nCurrent: {PUBLIC_VERSION} (build {__version__})\nNew: {self.release.public_version} (build {self.release.build_version})\nDownload: {bytes_text(self.release.size)}")
        label.setTextFormat(Qt.PlainText)
        layout.addWidget(label)
        notes = QPlainTextEdit(self.release.notes)
        notes.setReadOnly(True)
        layout.addWidget(notes)
        row = QHBoxLayout()
        button("View Release Notes", lambda: (self.window.navigate("Updates"), self.notice.close()), row)
        self.notice_primary = button("Restart & Install" if self.ready else "Download Update", self.notice_action, row)
        button("Remind Me Later", self.remind_later, row)
        layout.addLayout(row)
        self.notice.show()

    def notice_action(self):
        if self.notice:
            self.notice.close()
        self.window.navigate("Updates")
        self.restart_install() if self.ready else self.download()

    @safe_ui
    def restart_install(self):
        if not self.ready or not self.service or self.busy():
            return
        if self.active_work():
            raise UpdateError("Finish active voice, AI, file and command work before restarting. The verified update will wait.")
        self.preparing = True
        installer = WindowsInstaller(self.service, self.window.data_dir)

        def prepared(token):
            self.preparing = False
            if self.active_work():
                self.service.record(phase="ready")
                self.status.setText("New work started while preparing. Finish it, then choose Restart & Install again.")
                self.update_controls()
                return
            try:
                installer.launch_helper(token)
            except (ValueError, OSError):
                self.service.record(phase="ready")
                self.failed("The restart helper could not start. The current app and profile are unchanged.")
                return
            self.window.close()

        if not self.task(lambda cancel, progress: installer.prepare(self.window.db, cancel, progress), prepared):
            self.preparing = False

    def shutdown(self):
        self.timer.stop()
        self.reminder_timer.stop()
        self.cancel()
        if self.notice:
            self.notice.close()

    def forget_staged_view(self):
        self.release, self.ready, self.pending_download = None, False, False
        self.notes.clear()
        self.release_label.clear()
        self.transfer.clear()
        self.progress.setValue(0)
        if self.notice:
            self.notice.close()
        self.status.setText("Local data and update recovery snapshots erased after your confirmation.")
        self.update_controls()


class SoftwareUpdatesPanel(QWidget):
    """Settings → General shares the same updater and persisted preferences."""

    def __init__(self, page):
        super().__init__()
        self.page = page
        layout = QVBoxLayout(self)
        heading(layout, "Software Updates", f"Current Version: {PUBLIC_VERSION} · build {__version__}")
        self.automatic = QCheckBox("Automatically check for updates")
        self.downloads = QCheckBox("Download updates automatically")
        layout.addWidget(self.automatic)
        layout.addWidget(self.downloads)
        self.automatic.toggled.connect(page.automatic.setChecked)
        self.downloads.toggled.connect(page.auto_download.setChecked)
        row = QHBoxLayout()
        self.check_button = button("Check for Updates", page.check, row)
        button("View Release Notes", lambda: page.window.navigate("Updates"), row)
        self.restart_button = button("Restart & Install", page.restart_install, row)
        layout.addLayout(row)
        self.status = QLabel()
        self.status.setTextFormat(Qt.PlainText)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        page.changed.connect(self.refresh)
        self.refresh()

    def refresh(self):
        for target, source in ((self.automatic, self.page.automatic), (self.downloads, self.page.auto_download)):
            target.blockSignals(True)
            target.setChecked(source.isChecked())
            target.blockSignals(False)
        self.check_button.setEnabled(self.page.check_button.isEnabled())
        self.restart_button.setVisible(self.page.ready)
        self.restart_button.setEnabled(self.page.restart_button.isEnabled())
        self.status.setText(self.page.status.text())
