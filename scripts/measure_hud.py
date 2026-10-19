"""Actual rendering/cpu benchmark; direct state changes here are test stimuli, not commands."""

import json
from pathlib import Path
import tempfile
import time

from PySide6.QtGui import QFontDatabase
from PySide6.QtTest import QTest
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication
from nexis.platform.system import process_working_set_mb
from nexis.storage.database import Database
from nexis.ui.main_window import MainWindow
from nexis.ui.reactor import ReactorState

app = QApplication([])
QFontDatabase.addApplicationFont("C:/Windows/Fonts/segoeui.ttf")
QFontDatabase.addApplicationFont("C:/Windows/Fonts/consola.ttf")
rows = []
with tempfile.TemporaryDirectory(prefix="nexis-benchmark-") as directory:
    started = time.perf_counter()
    db = Database(Path(directory) / "bench.db")
    window = MainWindow(db, directory)
    window.resize(1366, 768)
    window.show()
    app.processEvents()
    first_event_seconds = time.perf_counter() - started
    QTest.qWait(400)
    for mode in ("idle", "active", "reduced", "minimized"):
        window.showNormal()
        db.set_setting("reduced_motion", mode == "reduced")
        window.apply_theme()
        window.set_state(ReactorState.EXECUTING if mode == "active" else ReactorState.IDLE)
        if mode == "minimized":
            window.showMinimized()
        QTest.qWait(200)
        started, cpu = time.perf_counter(), time.process_time()
        paints, painting = window.reactor.paint_count, window.reactor.paint_seconds
        loop = QEventLoop()
        QTimer.singleShot(3000, loop.quit)
        loop.exec()
        elapsed = time.perf_counter() - started
        frames = window.reactor.paint_count - paints
        memory = process_working_set_mb()
        rows.append(
            {
                "mode": mode,
                "elapsed_seconds": round(elapsed, 3),
                "paint_events_per_second": round(frames / elapsed, 2),
                "mean_paint_ms": round(
                    (window.reactor.paint_seconds - painting) * 1000 / max(frames, 1), 3
                ),
                "process_cpu_percent_one_core": round(
                    100 * (time.process_time() - cpu) / elapsed, 2
                ),
                "working_set_mb": round(memory, 2) if memory is not None else None,
                "reactor_timer_active": window.reactor.timer.isActive(),
                "sensor_timer_active": window.sensor_timer.isActive(),
            }
        )
    window.close()
    db.close()
report = {
    "qt_platform": app.platformName(),
    "viewport": [1366, 768],
    "first_event_seconds_excluding_imports": round(first_event_seconds, 3),
    "modes": rows,
}
Path("docs/v11-performance.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2))
