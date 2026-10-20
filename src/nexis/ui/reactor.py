"""Original QPainter reactor. Static markings are cached; motion is elapsed-time based."""

import math
from enum import Enum
from time import perf_counter

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPixmap, QRadialGradient, QPolygonF
from PySide6.QtWidgets import QWidget

RED = QColor("#FF2338")
GOLD = QColor("#D4AF37")
MUTED = QColor("#B59B9A")


class ReactorState(str, Enum):
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    PROCESSING = "PROCESSING"
    SPEAKING = "SPEAKING"
    EXECUTING = "EXECUTING"
    SUCCESS = "SUCCESS"
    ERROR = "ERROR"


class ReactorWidget(QWidget):
    activated = Signal()
    state_changed = Signal(str)
    SPEEDS = {
        ReactorState.IDLE: 3,
        ReactorState.LISTENING: 7,
        ReactorState.PROCESSING: 24,
        ReactorState.SPEAKING: 11,
        ReactorState.EXECUTING: 18,
        ReactorState.SUCCESS: 5,
        ReactorState.ERROR: 2,
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.state = ReactorState.IDLE
        self.reduced_motion = False
        self.paused = False
        self.active_fps = 30
        self.audio_level = None
        self.phase = 0.0
        self.last_tick = perf_counter()
        self.paint_count = 0
        self.paint_seconds = 0.0
        self._cache = None
        self._cache_key = None
        self._core_cache = {}
        self._motion_cache = None
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.advance)
        self.setMinimumSize(220, 220)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAccessibleName("NEXIS reactor: open manual commands")
        self.setToolTip("Open manual commands · Enter or Space")
        self.setCursor(Qt.PointingHandCursor)

    def set_state(self, state):
        state = ReactorState(state)
        if state != self.state:
            self.state = state
            self.audio_level = None
            self.state_changed.emit(state.value)
        self.sync_timer()
        self.update()

    def set_audio_level(self, level):
        self.audio_level = None if level is None else max(0.0, min(1.0, float(level)))
        self.update()

    def set_reduced_motion(self, enabled):
        self.reduced_motion = bool(enabled)
        self.sync_timer()
        self.update()

    def set_paused(self, paused):
        self.paused = bool(paused)
        self.sync_timer()

    def set_fps(self, fps):
        self.active_fps = max(10, min(30, int(fps)))
        self.sync_timer()

    def sync_timer(self):
        if self.paused or self.reduced_motion or not self.isVisible():
            self.timer.stop()
        else:
            fps = 8 if self.state == ReactorState.IDLE else self.active_fps
            self.last_tick = perf_counter()
            self.timer.setTimerType(
                Qt.CoarseTimer if self.state == ReactorState.IDLE else Qt.PreciseTimer
            )
            self.timer.start(round(1000 / fps))

    def advance(self):
        now = perf_counter()
        self.phase = (self.phase + min(now - self.last_tick, 0.25) * self.SPEEDS[self.state]) % 360
        self.last_tick = now
        self.update()

    def showEvent(self, event):
        super().showEvent(event)
        self.sync_timer()

    def hideEvent(self, event):
        self.timer.stop()
        super().hideEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.activated.emit()
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self.activated.emit()
            event.accept()
        else:
            super().keyPressEvent(event)

    @staticmethod
    def ring(painter, radius, start, span, color, width=1):
        painter.setPen(QPen(color, width))
        painter.setBrush(Qt.NoBrush)
        painter.drawArc(
            QRectF(-radius, -radius, radius * 2, radius * 2), int(start * 16), int(span * 16)
        )

    def static_geometry(self, size):
        dpr = self.devicePixelRatioF()
        key = (size, dpr)
        if self._cache_key == key:
            return self._cache
        pixmap = QPixmap(round(size * dpr), round(size * dpr))
        pixmap.setDevicePixelRatio(dpr)
        pixmap.fill(Qt.transparent)
        p = QPainter(pixmap)
        p.setRenderHint(QPainter.Antialiasing)
        p.translate(size / 2, size / 2)
        p.scale(size / 600, size / 600)
        for radius in (286, 278, 251, 239, 205, 196, 154, 124):
            self.ring(p, radius, 0, 360, QColor("#570000"), 1)
        for i in range(120):
            a = math.radians(i * 3)
            outer = 273
            inner = 261 if i % 5 == 0 else 267
            p.setPen(QPen(QColor("#C8102E") if i % 5 == 0 else QColor("#570000"), 1))
            p.drawLine(
                QPointF(math.cos(a) * inner, math.sin(a) * inner),
                QPointF(math.cos(a) * outer, math.sin(a) * outer),
            )
        p.setFont(QFont("Consolas", 8))
        p.setPen(MUTED)
        for degrees, text in ((0, "090"), (90, "180"), (180, "270"), (270, "000")):
            a = math.radians(degrees)
            p.drawText(
                QRectF(math.cos(a) * 288 - 15, math.sin(a) * 288 - 8, 30, 16), Qt.AlignCenter, text
            )
        for i in range(8):
            p.save()
            p.rotate(i * 45 + 22.5)
            p.setPen(QPen(QColor("#8B0000"), 1))
            p.drawPolyline(
                QPolygonF(
                    [QPointF(185, -8), QPointF(220, -8), QPointF(236, -24), QPointF(268, -24)]
                )
            )
            p.drawRect(QRectF(217, -11, 6, 6))
            p.restore()
        p.end()
        self._cache, self._cache_key = pixmap, key
        return pixmap

    def core_texture(self, accent):
        key = accent.name()
        if key not in self._core_cache:
            texture = QPixmap(256, 256)
            texture.fill(Qt.transparent)
            painter = QPainter(texture)
            painter.setRenderHint(QPainter.Antialiasing)
            glow = QRadialGradient(128, 128, 128)
            glow.setColorAt(0, QColor("#FFF4E8"))
            glow.setColorAt(0.13, QColor("#FFD1C8"))
            glow.setColorAt(0.3, accent)
            glow.setColorAt(0.55, QColor(200, 16, 46, 160))
            glow.setColorAt(1, QColor(139, 0, 0, 0))
            painter.setPen(Qt.NoPen)
            painter.setBrush(glow)
            painter.drawEllipse(QPointF(128, 128), 128, 128)
            painter.end()
            self._core_cache[key] = texture
        return self._core_cache[key]

    def motion_geometry(self, size):
        """Cache vector paths, retaining resolution-independent original artwork."""
        if self._motion_cache is not None:
            return self._motion_cache

        def arcs(radius, starts, span):
            path = QPainterPath()
            rect = QRectF(-radius, -radius, radius * 2, radius * 2)
            for start in starts:
                path.arcMoveTo(rect, start)
                path.arcTo(rect, start, span)
            return path

        paths = [arcs(281, (i * 7.5 for i in range(48)), 4.7),
                 arcs(247, (i * 30 for i in range(12) if i % 3 == 0), 19),
                 arcs(247, (i * 30 for i in range(12) if i % 3), 19),
                 arcs(222, (i * 45 for i in range(8)), 17),
                 arcs(172, (i * 60 for i in range(6)), 20)]
        spokes = QPainterPath()
        for i in range(16):
            a = math.radians(i * 22.5)
            spokes.moveTo(132 * math.cos(a), 132 * math.sin(a))
            spokes.lineTo(158 * math.cos(a), 158 * math.sin(a))
        self._motion_cache = [*paths, spokes]
        return self._motion_cache

    def paintEvent(self, event):
        started = perf_counter()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        side = min(self.width(), self.height()) - 8
        if side < 1:
            return
        p.drawPixmap(
            round((self.width() - side) / 2),
            round((self.height() - side) / 2),
            self.static_geometry(side),
        )
        p.translate(self.width() / 2, self.height() / 2)
        p.scale(side / 600, side / 600)
        phase = self.phase
        pulse = 0.5 + 0.5 * math.sin(math.radians(phase * 8))
        if self.reduced_motion:
            pulse = 0.5
        accent = GOLD if self.state in (ReactorState.PROCESSING, ReactorState.SUCCESS) else RED
        gold_phase = math.floor(phase / 12) * 4
        layers = self.motion_geometry(side)
        for index, (rotation, color, width) in enumerate((
                (-phase, QColor("#8B0000"), 6), (phase * 1.5, RED, 2),
                (phase * 1.5, QColor("#8B0000"), 2), (-gold_phase, GOLD, 2),
                (phase, QColor("#8B0000"), 2))):
            p.save()
            p.rotate(rotation)
            p.setPen(QPen(color, width))
            p.setBrush(Qt.NoBrush)
            p.drawPath(layers[index])
            p.restore()
        for i in range(6):
            self.ring(p, 184, i * 60 + phase * 2.4, 38, accent, 5 + pulse * 2)
        self.ring(p, 255, -phase * 2, 22, GOLD if self.state == ReactorState.SUCCESS else RED, 3)
        p.save()
        p.rotate(phase * 0.3)
        p.setPen(QPen(QColor("#C8102E"), 1))
        p.setBrush(Qt.NoBrush)
        p.drawPath(layers[5])
        p.restore()
        p.setPen(QPen(accent, 1.5))
        p.setBrush(QColor("#120607"))
        p.drawEllipse(QPointF(0, 0), 125, 125)
        # Listening/speaking modulation uses only real levels; missing levels never become a synthetic waveform.
        energy = (
            (self.audio_level or 0)
            if self.state in (ReactorState.LISTENING, ReactorState.SPEAKING)
            else pulse * 0.12
        )
        if self.reduced_motion:
            energy = 0.0
        core_radius = 73 + energy * 28
        radius = core_radius * 1.7
        texture = self.core_texture(accent)
        p.drawPixmap(
            QRectF(-radius, -radius, radius * 2, radius * 2), texture, QRectF(texture.rect())
        )
        for i in range(5):
            self.ring(
                p,
                95 + i * 5,
                phase * (1 if i % 2 else -1),
                270,
                QColor(255, 35, 56, 50 + i * 25),
                1,
            )
        for i in range(5):
            a = math.radians(phase * (0.6 + i * 0.1) + i * 72)
            p.setBrush(GOLD if i == 0 else RED)
            p.drawEllipse(QPointF(math.cos(a) * (151 + i * 9), math.sin(a) * (151 + i * 9)), 2, 2)
        p.setPen(QColor("#F4E9E5"))
        p.setFont(QFont("Consolas", 10, QFont.Bold))
        p.drawText(QRectF(-110, 85, 220, 24), Qt.AlignCenter, self.state.value)
        p.setFont(QFont("Consolas", 7))
        p.setPen(MUTED)
        detail = "LOCAL COMMAND CORE"
        if self.state in (ReactorState.LISTENING, ReactorState.SPEAKING):
            detail = (
                "AUDIO LEVEL N/A" if self.audio_level is None else f"SIGNAL {self.audio_level:.0%}"
            )
        p.drawText(QRectF(-120, 109, 240, 20), Qt.AlignCenter, detail)
        if self.hasFocus():
            self.ring(p, 294, 0, 360, GOLD, 2)
        p.end()
        self.paint_count += 1
        self.paint_seconds += perf_counter() - started
