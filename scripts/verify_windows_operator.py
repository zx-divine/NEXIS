"""Native window checks on this test process only. No owner window is changed."""

import json
import os
from pathlib import Path
import site
import sys

os.environ["QT_QPA_PLATFORM"] = "windows"
site.addsitedir(str(Path(__file__).resolve().parents[1] / ".dev-deps"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMainWindow
from nexis.platform.operator_windows import list_windows, change_window  # noqa: E402
from nexis.platform.discovery import known_folder  # noqa: E402
from nexis.ui.setup_services import Task  # noqa: E402

app = QApplication([])
app.setQuitOnLastWindowClosed(False)
window = QMainWindow()
window.setWindowTitle("NEXIS disposable operator verification window")
window.resize(640, 400)
window.show()
identifier = int(window.winId())
pid = os.getpid()
import win32gui  # noqa: E402
import win32process  # noqa: E402
import ctypes  # noqa: E402

result = {
    "scope": "Only this disposable test window/process",
    "owner_windows_modified": False,
    "qt_platform": app.platformName(),
    "stages": {},
}


def exercise(cancel, progress):
    rows = list_windows()
    result["debug"] = {
        "qt_handle": identifier,
        "python_pid": pid,
        "native_pid": ctypes.windll.kernel32.GetCurrentProcessId(),
        "is_window": bool(win32gui.IsWindow(identifier)),
        "is_visible": bool(win32gui.IsWindowVisible(identifier)),
        "window_pid": win32process.GetWindowThreadProcessId(identifier)[1]
        if win32gui.IsWindow(identifier)
        else None,
        "own_enumerated": [r for r in rows if r["title"].startswith("NEXIS disposable")],
    }

    result["stages"]["enumeration"] = (
        "PASS" if any(r["window_id"] == identifier and r["pid"] == pid for r in rows) else "FAIL"
    )
    for operation in ("focus", "minimize", "maximize", "close"):
        try:
            report = change_window(identifier, operation, cancel, pid)
            result["stages"][operation] = "PASS" if report["verified"] else "NOT VERIFIED"
        except Exception as exc:
            result["stages"][operation] = "NOT VERIFIED"
            result[operation + "_error_type"] = type(exc).__name__
            result[operation + "_error"] = (
                str(exc) if isinstance(exc, ValueError) else type(exc).__name__
            )
    return result


worker = Task(exercise)


def finish():
    base = known_folder("B4BFCC3A-DB2C-424C-B029-7FE99A87C641") / "NEXIS-Voice-Engine"
    (base / "diagnostics/windows-native-controls.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, indent=2))
    window.close()
    app.quit()


worker.finished.connect(finish)
QTimer.singleShot(500, worker.start)
QTimer.singleShot(15000, worker.cancel.set)
app.exec()
