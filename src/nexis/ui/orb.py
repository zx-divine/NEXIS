"""Optional visible desktop companion. Displaying it never opens a microphone."""

from PySide6.QtCore import Qt, QPoint, QEvent
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QApplication

from nexis.branding import application_icon
from nexis.ui.branding import BrandLogo
from nexis.ui.pages import button
from nexis.ui.reactor import ReactorWidget


def clamp_position(point, size, screens):
    if not screens:
        return QPoint(0, 0)
    screen = next((item for item in screens if item.availableGeometry().contains(point)), screens[0])
    area = screen.availableGeometry()
    return QPoint(max(area.left(), min(point.x(), area.right() - size.width() + 1)),
                  max(area.top(), min(point.y(), area.bottom() - size.height() + 1)))


class FloatingOrb(QWidget):
    def __init__(self, window, hide_callback):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.window = window
        self.drag_origin, self.drag_position, self.dragging = None, None, False
        self.setWindowTitle("NEXIS companion")
        self.setWindowIcon(application_icon())
        self.setObjectName("floatingOrb")
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        self.caption = QLabel("NEXIS / IDLE")
        self.caption.setAlignment(Qt.AlignCenter)
        branding = QHBoxLayout()
        branding.addWidget(BrandLogo(24, symbol=True))
        branding.addWidget(self.caption, 1)
        layout.addLayout(branding)
        self.reactor = ReactorWidget()
        self.reactor.setMinimumSize(150, 150)
        self.reactor.setAccessibleName("NEXIS floating reactor: drag to move, click to open main window")
        self.reactor.setToolTip("Drag to move · Click/Enter to open NEXIS · Talk explicitly starts the visible Voice Chat")
        self.reactor.activated.connect(self.expand)
        self.reactor.installEventFilter(self)
        layout.addWidget(self.reactor, 1)
        row = QHBoxLayout()
        button("Talk", self.talk, row)
        button("Open", self.expand, row)
        button("Hide", hide_callback, row)
        layout.addLayout(row)
        self.resize(220, 280)
        self.apply_preferences()
        self.reposition()

    def apply_preferences(self):
        self.setWindowFlag(Qt.WindowStaysOnTopHint, self.window.db.setting("orb_always_on_top"))
        self.reactor.set_reduced_motion(self.window.db.setting("reduced_motion"))
        self.reactor.set_fps(self.window.db.setting("animation_fps"))

    def reposition(self):
        saved = self.window.db.setting("orb_position")
        screens = QApplication.screens()
        if saved:
            point = QPoint(*saved)
        elif screens:
            area = screens[0].availableGeometry()
            point = QPoint(area.right() - self.width() - 24, area.bottom() - self.height() - 24)
        else:
            point = QPoint(0, 0)
        self.move(clamp_position(point, self.size(), screens))

    def eventFilter(self, watched, event):
        if watched is self.reactor:
            if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                self.drag_origin, self.drag_position = event.globalPosition().toPoint(), self.pos()
                self.dragging = False
            elif event.type() == QEvent.MouseMove and self.drag_origin is not None and event.buttons() & Qt.LeftButton:
                delta = event.globalPosition().toPoint() - self.drag_origin
                self.dragging = self.dragging or delta.manhattanLength() > 6
                if self.dragging:
                    self.move(clamp_position(self.drag_position + delta, self.size(), QApplication.screens()))
                    return True
            elif event.type() == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton and self.drag_origin is not None:
                moved = self.dragging
                self.drag_origin, self.dragging = None, False
                if moved:
                    self.window.db.set_setting("orb_position", [self.x(), self.y()])
                    return True  # A drag is not a reactor activation or Talk action.
        return super().eventFilter(watched, event)

    def expand(self):
        if not self.window.closing:
            self.window.showNormal()
            self.window.raise_()
            self.window.activateWindow()

    def talk(self):
        if self.window.closing:
            return
        self.expand()
        self.window.navigate("Voice Chat")
        self.window.voice.start()  # Only this explicit Talk gesture, with normal gates.

    def set_state(self, state):
        self.reactor.set_state(state)
        self.caption.setText("NEXIS / HARD MUTED" if self.window.db.setting("microphone_muted") else "NEXIS / " + state)
