"""Render actual foundation widgets using isolated data; never certify audio/network."""

import argparse
import hashlib
import json
from pathlib import Path
import tempfile
from time import perf_counter, process_time

from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from PySide6.QtGui import QFont, QFontDatabase

from nexis.storage.database import Database
from nexis.ui.branding import WelcomeWizard
from nexis.ui.main_window import MainWindow
from nexis.core.themes import THEMES


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--interactive", action="store_true", help="Open an isolated native preview; no personal profile is read")
    parser.add_argument("--profile", action="store_true", help="Measure this host's UI CPU/RAM; does not certify reference hardware")
    parser.add_argument("--native-check", action="store_true", help="Verify this isolated window's actual Windows frame/minimize/maximize state")
    parser.add_argument("--preview-matrix", action="store_true", help="Render all four actual theme-preview tabs in all six themes")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    app = QApplication.instance() or QApplication([])
    # Offscreen Qt does not discover the normal Windows font collection.
    for font in ("segoeui.ttf", "segoeuib.ttf", "consola.ttf", "seguisym.ttf", "Nirmala.ttf"):
        path = Path("C:/Windows/Fonts") / font
        if path.is_file():
            QFontDatabase.addApplicationFont(str(path))
    app.setFont(QFont("Segoe UI", 10))
    app.setQuitOnLastWindowClosed(False)
    records = []
    measurements = []
    native = {"performed": False}

    def capture(widget, name):
        app.processEvents()
        QTest.qWait(60)
        target = args.output / (name + ".png")
        pixmap = widget.grab()
        if pixmap.isNull() or not pixmap.save(str(target)):
            raise RuntimeError("Real widget capture failed: " + name)
        records.append({"file": target.name, "width": pixmap.width(), "height": pixmap.height(),
                        "device_pixel_ratio": pixmap.devicePixelRatio(),
                        "sha256": hashlib.sha256(target.read_bytes()).hexdigest()})

    with tempfile.TemporaryDirectory(prefix="nexis-v1-preview-") as folder:
        db = Database(Path(folder) / "preview.db")
        db.set_setting("preferred_name", "Preview")
        db.set_setting("reduced_motion", True)
        started = perf_counter()
        window = MainWindow(db, folder)
        window.show()
        app.processEvents()
        construction = perf_counter() - started
        if args.native_check:
            if app.platformName() != "windows":
                raise RuntimeError("Native verification requires QT_QPA_PLATFORM=windows")
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.WinDLL("user32", use_last_error=True)
            user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
            user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
            user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
            user32.IsZoomed.argtypes = [wintypes.HWND]
            user32.IsIconic.argtypes = [wintypes.HWND]
            user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
            user32.SendMessageW.restype = ctypes.c_ssize_t
            handle = int(window.winId())
            title = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(handle, title, len(title))
            style = user32.GetWindowLongPtrW(handle, -16)
            native = {"performed": True, "title": title.value,
                      "normal_frame_and_controls": style & 0x00CF0000 == 0x00CF0000,
                      "windows_icon_handle_present": bool(user32.SendMessageW(handle, 0x007F, 2, 0))}
            window.showMaximized()
            QTest.qWait(100)
            native["maximized_by_windows"] = bool(user32.IsZoomed(handle))
            window.showMinimized()
            QTest.qWait(100)
            native["minimized_by_windows"] = bool(user32.IsIconic(handle))
            window.showNormal()
            QTest.qWait(100)
            native["restored_by_windows"] = not user32.IsIconic(handle) and not user32.IsZoomed(handle)
            if title.value != "NEXIS" or not all(value for key, value in native.items() if key not in {"title", "performed"}):
                raise RuntimeError("Native window acceptance check failed: " + json.dumps(native))
        if args.interactive:
            from PySide6.QtCore import QTimer

            app.setQuitOnLastWindowClosed(True)
            QTimer.singleShot(300000, window.close)
            app.exec()
            db.close()
            return
        for width, height in ((820, 600), (1366, 768)):
            window.resize(width, height)
            for page in ("Welcome", "Chat", "Voice Chat", "Dashboard", "Settings", "Saved Conversations", "Desktop Companion"):
                window.navigate(page)
                if page == "Settings":
                    window.settings_page.open_section("General")
                capture(window, f"{page.replace(' ', '-').lower()}-{width}x{height}")
        for theme in THEMES:
            window.apply_theme(theme)
            window.navigate("Welcome")
            capture(window, "theme-" + theme)
        window.apply_theme("og")
        if args.profile:
            from nexis.platform.system import process_working_set_mb

            window.navigate("Welcome")
            for mode in ("idle", "active", "reduced", "minimized"):
                window.showNormal()
                db.set_setting("reduced_motion", mode == "reduced")
                window.apply_theme()
                window.set_state("EXECUTING" if mode == "active" else "IDLE")
                if mode == "minimized":
                    window.showMinimized()
                app.processEvents()
                reactor = window.welcome.reactor
                started, cpu = perf_counter(), process_time()
                paints, painting = reactor.paint_count, reactor.paint_seconds
                QTest.qWait(3000)
                elapsed = perf_counter() - started
                count = reactor.paint_count - paints
                measurements.append({"mode": mode, "seconds": round(elapsed, 3),
                    "process_cpu_percent_one_core": round(100 * (process_time() - cpu) / elapsed, 2),
                    "working_set_mb": process_working_set_mb(), "paint_events": count,
                    "mean_paint_ms": round(1000 * (reactor.paint_seconds - painting) / max(count, 1), 3),
                    "reactor_timer_active": reactor.timer.isActive(), "sensor_timer_active": window.sensor_timer.isActive()})
            window.showNormal()
        wizard = WelcomeWizard(db)
        wizard.show()
        capture(wizard, "onboarding-identity")
        wizard.preferred_name.setText("Preview")
        wizard.access.acknowledged.setChecked(True)
        wizard.api_setup_choice.setCurrentIndex(wizard.api_setup_choice.findData('later'))
        for index in range(1, 9):
            wizard.next()
            if wizard.currentId() != index:
                raise RuntimeError("Could not reach onboarding page " + str(index))
            if index in (2, 3, 4, 5, 7, 8):
                capture(wizard, "onboarding-" + str(index))
        if args.preview_matrix:
            for theme in THEMES:
                wizard.appearance.theme.setCurrentIndex(wizard.appearance.theme.findData(theme))
                for index in range(4):
                    wizard.appearance.experience.setCurrentIndex(index)
                    capture(wizard.appearance.experience, f"preview-{theme}-{index}")
        wizard.reject()
        window.close()
        for _ in range(100):
            if not any(job and job.isRunning() for job in window.background_jobs()):
                break
            QTest.qWait(50)
        if any(job and job.isRunning() for job in window.background_jobs()):
            raise RuntimeError("Background work did not stop during render verification")
        db.close()
    result = {"kind": "real-Qt-widget-rendering", "hardware_or_live_service_certification": False,
              "construction_to_first_event_seconds_excluding_imports": round(construction, 3),
              "native_window_checks": native, "measurements_on_this_host": measurements, "screenshots": records}
    (args.output / "render-results.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"rendered": len(records), "output": str(args.output.resolve())}))


if __name__ == "__main__":
    main()
