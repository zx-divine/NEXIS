"""Render real v1.1 widgets at the requested sizes with isolated data and real sensors."""

from pathlib import Path
import tempfile
import time
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase
from PySide6.QtTest import QTest
from nexis.storage.database import Database
from nexis.ui.main_window import MainWindow


def wait_for_command(window):
    deadline = time.perf_counter() + 5
    while not window.execute.isEnabled():
        app.processEvents()
        time.sleep(0.01)
        if time.perf_counter() > deadline:
            window.stop_command()
            window.worker.wait(3000)
            raise RuntimeError("The screenshot command did not complete.")
    app.processEvents()


app = QApplication([])
QFontDatabase.addApplicationFont("C:/Windows/Fonts/segoeui.ttf")
QFontDatabase.addApplicationFont("C:/Windows/Fonts/consola.ttf")
output = Path("docs/screenshots-v1.1")
output.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory() as directory:
    db = Database(Path(directory) / "preview.db")
    window = MainWindow(db, directory)
    window.show()
    for width, height in ((1366, 768), (1600, 900), (1920, 1080)):
        window.resize(width, height)
        window.navigate("Dashboard")
        QTest.qWait(1200)
        window.grab().save(str(output / f"hud-{width}x{height}.png"))
    window.resize(1366, 768)
    window.navigate("Chat")
    window.chat.input.setText("what can you do")
    window.chat.send()
    wait_for_command(window)
    window.grab().save(str(output / "chat.png"))
    window.navigate("Voice Chat")
    app.processEvents()
    window.grab().save(str(output / "voice.png"))
    window.focus_command()
    window.submit("help")
    QTest.qWait(300)
    window.grab().save(str(output / "manual.png"))
    window.navigate("Settings")
    app.processEvents()
    window.grab().save(str(output / "settings.png"))
    window.close()
    db.close()
print("Rendered seven actual Qt v1.1 screenshots at all three requested resolutions.")
