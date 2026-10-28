from PySide6.QtCore import Property, QPropertyAnimation, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QFont, QPainter, QPainterPath, QPen
from nexis.ui.themes import color

from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget


class DeckButton(QPushButton):
    def __init__(self, title, subtitle):
        super().__init__(title)
        self.title, self.subtitle = title, subtitle
        self.progress = 0.0
        self.reduced_motion = False
        self.setCheckable(True)
        self.setMinimumHeight(56)
        self.setAccessibleName(title)
        self.setToolTip(title + " — " + subtitle)
        self.animation = QPropertyAnimation(self, b"hoverProgress", self)
        self.animation.setDuration(140)

    def get_progress(self):
        return self.progress

    def set_progress(self, value):
        self.progress = value
        self.update()

    hoverProgress = Property(float, get_progress, set_progress)

    def hover(self, end):
        self.animation.stop()
        if self.reduced_motion:
            self.set_progress(end)
        else:
            self.animation.setStartValue(self.progress)
            self.animation.setEndValue(end)
            self.animation.start()

    def enterEvent(self, event):
        self.hover(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.hover(0.0)
        super().leaveEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width() - 1, self.height() - 1
        shape = QPainterPath(QPointF(0, 12))
        for x, y in ((12, 0), (w - 28, 0), (w, 18), (w, h - 10), (w - 10, h), (0, h)):
            shape.lineTo(x, y)
        shape.closeSubpath()
        p.fillPath(shape, color("hover" if self.progress > .5 else "panel"))
        selected = self.isChecked() or self.hasFocus()
        p.setPen(QPen(color("accent" if selected else "primary"), 1.5 if selected else 1))
        p.drawPath(shape)
        p.setPen(QPen(color("primary"), 3))
        p.drawLine(14, 1, 52 + int(self.progress * 45), 1)
        p.setPen(color("accent" if selected else "text"))
        p.setFont(QFont("Consolas", 11, QFont.Bold))
        p.drawText(QRectF(12, 8, w - 24, 23), Qt.AlignCenter, self.title)
        p.setFont(QFont("Consolas", 7))
        p.setPen(color("muted"))
        p.drawText(QRectF(12, 32, w - 24, 16), Qt.AlignCenter, self.subtitle)


class CommandDeck(QWidget):
    chat_requested = Signal()
    voice_requested = Signal()
    manual_requested = Signal()

    def __init__(self):
        super().__init__()
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(14)
        self.chat = DeckButton("CHAT", "TEXT UPLINK  /  CTRL+2")
        self.voice = DeckButton("VOICE CHAT", "VOICE → SELECTED AI  /  CTRL+3")
        self.manual = DeckButton("MANUAL COMMANDS", "TRUSTED COMMAND DECK  /  CTRL+K")
        for control in (self.chat, self.voice, self.manual):
            row.addWidget(control, 1)
        self.chat.clicked.connect(self.chat_requested)
        self.voice.clicked.connect(self.voice_requested)
        self.manual.clicked.connect(self.manual_requested)

    def set_reduced_motion(self, reduced):
        for control in (self.chat, self.voice, self.manual):
            control.reduced_motion = reduced
            if reduced:
                control.animation.stop()
