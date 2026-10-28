import sys
from pathlib import Path

from PySide6.QtCore import QLockFile, QStandardPaths, QTimer, Qt
from PySide6.QtWidgets import QApplication, QMessageBox

from nexis import __version__, MIN_WINDOWS_BUILD
from nexis.branding import application_icon, set_app_user_model_id
from nexis.storage.database import Database, StorageError
from nexis.ui.branding import WelcomeWizard, splash_screen
from nexis.ui.main_window import MainWindow
from nexis.utils.logging import configure


def main():
    set_app_user_model_id()
    app = QApplication(sys.argv)
    if sys.platform == "win32" and sys.getwindowsversion().build < MIN_WINDOWS_BUILD:
        QMessageBox.critical(None, "Unsupported Windows version", "NEXIS requires Windows 10 build 19045 or newer, or Windows 11 (64-bit). This installation is not supported on the current Windows version.")
        return 1
    app.setWindowIcon(application_icon())
    app.setApplicationName("NEXIS Desktop")
    app.setOrganizationName("NEXIS")
    app.setApplicationVersion(__version__)
    if "--smoke-test" in sys.argv:
        from nexis.diagnostics import smoke

        index = sys.argv.index("--smoke-test")
        if len(sys.argv) <= index + 1:
            return 2
        return smoke(app, sys.argv[index + 1])
    directory = Path(QStandardPaths.writableLocation(QStandardPaths.AppLocalDataLocation))
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError:
        QMessageBox.critical(
            None,
            "NEXIS could not start",
            "Windows could not create the local data folder. Check free disk space and your account's folder permissions.",
        )
        return 1
    lock = QLockFile(str(directory / "nexis.lock"))
    if not lock.tryLock(100):
        QMessageBox.information(None, "NEXIS", "NEXIS is already running or its data is locked.")
        return 1
    configure(directory)
    splash = splash_screen()
    splash.show()
    splash.showMessage("Opening local settings…", Qt.AlignBottom | Qt.AlignHCenter, Qt.white)
    app.processEvents()
    try:
        db = Database(directory / "nexis.db")
        splash.showMessage("Preparing command center…", Qt.AlignBottom | Qt.AlignHCenter, Qt.white)
        app.processEvents()
        window = MainWindow(db, directory)
    except (StorageError, OSError) as exc:
        splash.close()
        QMessageBox.critical(None, "NEXIS could not start", str(exc))
        return 1
    if not db.setting("welcome_completed") or not db.setting("system_access_acknowledged") or not db.setting('preferred_name'):
        splash.close()
        wizard = WelcomeWizard(db)
        wizard.setStyleSheet(window.styleSheet())
        if not wizard.exec():
            window.close()
            db.close()
            lock.unlock()
            return 0
        window.refresh()
        window.settings_page.provider.reload_saved()
        window.settings_page.reload_profile()
        window.apply_theme()
        window.show_launch_mode()
    if db.setting("start_minimised") or "--minimised" in sys.argv:
        window.showMinimized()
    elif db.setting("start_maximized"):
        window.showMaximized()
    else:
        window.show()
    splash.finish(window)
    QTimer.singleShot(100, window.start_services)
    result = app.exec()
    db.close()
    lock.unlock()
    return result


if __name__ == "__main__":
    raise SystemExit(main())
