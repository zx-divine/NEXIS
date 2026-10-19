import site
import sys
from pathlib import Path

site.addsitedir(".dev-deps")
sys.path.insert(0, "src")
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from nexis.ui.voice_diagnostics import VoiceDiagnostics, evidence_directory

app = QApplication([])
window = VoiceDiagnostics()
window.setStyleSheet(Path("src/nexis/ui/theme.qss").read_text())
window.show()


def check():
    assert window.worker is None
    assert window.devices.count() > 0
    assert window.grab().save(str(evidence_directory() / "diagnostics/standalone-ready.png"))
    window.close()


QTimer.singleShot(2200, check)
app.exec()
print("Standalone UI ready; zero microphone sessions started")
