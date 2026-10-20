"""Read-only PC Health; refresh is explicit and runs outside the GUI thread."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPlainTextEdit, QLabel

from nexis.platform.health import health_snapshot
from nexis.ui.pages import heading, button
from nexis.ui.setup_services import Task


class HealthPage(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window, self.jobs = window, []
        layout = QVBoxLayout(self)
        heading(layout, "PC HEALTH", "Read-only local snapshot. Nothing is changed, terminated, uploaded or probed on the internet. Refresh when needed; no background polling.")
        self.refresh_button = button("Refresh health snapshot", self.refresh, layout)
        self.status = QLabel("Press Refresh to inspect this PC. No administrator access is requested.")
        self.status.setTextFormat(Qt.PlainText)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.report = QPlainTextEdit()
        self.report.setReadOnly(True)
        self.report.setAccessibleName("Read-only PC health report")
        layout.addWidget(self.report, 1)

    def refresh(self):
        if any(job.isRunning() for job in self.jobs):
            return
        for old in self.jobs:
            old.deleteLater()
        self.jobs.clear()
        self.refresh_button.setEnabled(False)
        self.status.setText("Reading local Windows counters…")
        task = Task(lambda cancel, progress: health_snapshot(self.window.data_dir, cancel), self)
        task.result.connect(self.loaded)
        task.failed.connect(self.status.setText)
        task.finished.connect(lambda: self.refresh_button.setEnabled(True))
        self.jobs.append(task)
        task.start()

    def loaded(self, value):
        if not value:
            return

        def number(key, suffix=""):
            raw = value.get(key)
            return "Unavailable" if raw is None else f"{raw:.1f}{suffix}"

        lines = ["CPU use: " + number("cpu_percent", "% (short sample)"),
                 "RAM use: " + number("memory_percent", "%"),
                 "Physical memory: " + number("total_memory_mb", " MB"),
                 "Available physical memory: " + number("available_memory_mb", " MB"),
                 "NEXIS data volume free / total: " + number("disk_free_gb", " GB") + " / " + number("disk_total_gb", " GB"),
                 "Uptime: " + number("uptime_seconds", " seconds"),
                 "Battery: " + value["battery"], "Network: " + value["network"],
                 "Temperature: " + value["temperature"], "", "Top accessible processes by RAM (bounded sample, not CPU ranking):"]
        lines.extend(f"{row['name']} · PID {row['pid']} · {row['working_set_mb']:.1f} MB" for row in value["top_processes"])
        if not value["top_processes"]:
            lines.append("Unavailable or no accessible processes.")
        lines.extend(["", "High CPU can be temporary; repeat a sample before drawing conclusions. Low available RAM or disk space may slow applications. Protected processes and sensor data may be unavailable without additional permissions; NEXIS does not elevate to read them."])
        self.report.setPlainText("\n".join(lines))
        self.status.setText("Snapshot complete. This is an explanation, not an automatic optimization or hardware diagnosis.")
