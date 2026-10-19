# ruff: noqa: E402
"""Measure Qt window startup and idle working set in an isolated temporary data folder."""

import ctypes
from ctypes import wintypes
import json
from pathlib import Path
import tempfile
import time

STARTED = time.perf_counter()
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase
from PySide6.QtCore import QTimer
from nexis.storage.database import Database
from nexis.ui.main_window import MainWindow

app = QApplication([])
QFontDatabase.addApplicationFont("C:/Windows/Fonts/segoeui.ttf")
with tempfile.TemporaryDirectory() as directory:
    db = Database(Path(directory) / "measure.db")
    window = MainWindow(db, directory)
    window.show()
    app.processEvents()
    startup = time.perf_counter() - STARTED

    idle_started = time.perf_counter()
    cpu_started = time.process_time()

    def finish():
        class Counters(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
                (name, ctypes.c_size_t)
                for name in (
                    "PeakWorkingSetSize",
                    "WorkingSetSize",
                    "QuotaPeakPagedPoolUsage",
                    "QuotaPagedPoolUsage",
                    "QuotaPeakNonPagedPoolUsage",
                    "QuotaNonPagedPoolUsage",
                    "PagefileUsage",
                    "PeakPagefileUsage",
                )
            ]

        info = Counters()
        info.cb = ctypes.sizeof(info)
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
        if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(info), info.cb):
            raise ctypes.WinError(ctypes.get_last_error())
        print(
            json.dumps(
                {
                    "startup_seconds": round(startup, 3),
                    "idle_working_set_mb": round(info.WorkingSetSize / 1048576, 2),
                    "idle_cpu_percent": round(
                        100
                        * (time.process_time() - cpu_started)
                        / (time.perf_counter() - idle_started),
                        2,
                    ),
                    "window_construction_ms": round(window.construction_ms, 1),
                }
            )
        )
        window.close()
        app.quit()

    QTimer.singleShot(3000, finish)
    app.exec()
    db.close()
