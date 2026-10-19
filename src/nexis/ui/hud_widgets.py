import math
from collections import deque
from time import perf_counter

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget


class HUDPanel(QFrame):
    def __init__(self, title, code, parent=None):
        super().__init__(parent)
        self.setObjectName("hudPanel")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(13, 12, 13, 13)
        self.body.setSpacing(7)
        label = QLabel(title.upper() + "  /  " + code)
        label.setObjectName("hudLabel")
        label.setWordWrap(True)
        self.body.addWidget(label)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width() - 1, self.height() - 1
        path = QPainterPath(QPointF(0, 9))
        for x, y in ((9, 0), (w - 25, 0), (w, 18), (w, h - 9), (w - 9, h), (20, h), (0, h - 15)):
            path.lineTo(x, y)
        path.closeSubpath()
        p.fillPath(path, QColor("#0D0506"))
        p.setPen(QPen(QColor("#570000"), 1))
        p.drawPath(path)
        p.setPen(QPen(QColor("#C8102E"), 2))
        p.drawLine(10, 1, 60, 1)
        p.drawLine(w - 1, h - 45, w - 1, h - 12)
        p.setPen(QPen(QColor("#D4AF37"), 1))
        p.drawLine(16, h - 1, 39, h - 1)
        p.end()


class SegmentedMeter(QWidget):
    def __init__(self, label, parent=None):
        super().__init__(parent)
        self.label, self.value = label, None
        self.setMinimumHeight(38)
        self.setAccessibleName(label)

    def set_value(self, value):
        self.value = value
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setFont(QFont("Consolas", 9))
        p.setPen(QColor("#B59B9A"))
        value = "N/A" if self.value is None else f"{self.value:05.1f}%"
        p.drawText(QRectF(0, 0, self.width(), 19), Qt.AlignLeft, self.label)
        p.setPen(QColor("#F4E9E5"))
        p.drawText(QRectF(0, 0, self.width(), 19), Qt.AlignRight, value)
        count = 24
        width = (self.width() - 3 * (count - 1)) / count
        for i in range(count):
            lit = self.value is not None and i < math.ceil(self.value / 100 * count)
            p.fillRect(
                QRectF(i * (width + 3), 25, width, 7), QColor("#FF2338" if lit else "#341014")
            )


class SystemGraph(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.cpu, self.memory = deque(maxlen=60), deque(maxlen=60)
        self.setMinimumHeight(85)
        self.setAccessibleName("Real CPU and memory history, sixty samples")

    def add_sample(self, cpu, memory):
        self.cpu.append(cpu)
        self.memory.append(memory)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        width, height = self.width() - 2, self.height() - 20
        p.setPen(QPen(QColor("#341014"), 1))
        for i in range(5):
            p.drawLine(0, int(i * height / 4), width, int(i * height / 4))
        for i in range(11):
            p.drawLine(int(i * width / 10), 0, int(i * width / 10), height)
        for values, color in ((self.cpu, "#FF2338"), (self.memory, "#D4AF37")):
            path = QPainterPath()
            joined = False
            for index, value in enumerate(values):
                if value is None:
                    joined = False
                    continue
                point = QPointF(
                    width - (len(values) - 1 - index) * width / 59, height * (1 - value / 100)
                )
                path.lineTo(point) if joined else path.moveTo(point)
                joined = True
            p.setPen(QPen(QColor(color), 1.4))
            p.drawPath(path)
        p.setPen(QColor("#B59B9A"))
        p.setFont(QFont("Consolas", 8))
        p.drawText(0, self.height() - 2, "CPU / RED     MEMORY / GOLD     1 Hz")


class RadarWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(130)
        self.events = deque(maxlen=8)
        self.started = perf_counter()
        self.reduced_motion = False
        self.paused = False
        self.timer = QTimer(self)
        self.timer.setInterval(125)
        self.timer.timeout.connect(self.update)
        self.setAccessibleName("Decorative system activity visualization, not object detection")

    def add_event(self):
        self.events.append(perf_counter())
        self.update()

    def sync_timer(self):
        if self.isVisible() and not self.reduced_motion and not self.paused:
            self.timer.start()
        else:
            self.timer.stop()

    def showEvent(self, event):
        super().showEvent(event)
        self.sync_timer()

    def hideEvent(self, event):
        self.timer.stop()
        super().hideEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        radius = min(self.width(), self.height()) / 2 - 10
        p.translate(self.width() / 2, self.height() / 2)
        p.setPen(QPen(QColor("#8B0000"), 1))
        for scale in (0.25, 0.5, 0.75, 1):
            p.drawEllipse(QPointF(), radius * scale, radius * scale)
        p.drawLine(QPointF(-radius, 0), QPointF(radius, 0))
        p.drawLine(QPointF(0, -radius), QPointF(0, radius))
        angle = 0 if self.reduced_motion else (perf_counter() - self.started) * 0.35
        p.setPen(QPen(QColor("#C8102E"), 2))
        p.drawLine(QPointF(), QPointF(math.cos(angle) * radius, math.sin(angle) * radius))
        # Dots encode actual command events only, with arbitrary visual placement.
        p.setBrush(QColor("#D4AF37"))
        p.setPen(Qt.NoPen)
        for i, when in enumerate(self.events):
            if perf_counter() - when < 20:
                a = i * 2.4
                r = radius * (0.3 + (i % 4) * 0.15)
                p.drawEllipse(QPointF(math.cos(a) * r, math.sin(a) * r), 2.5, 2.5)
