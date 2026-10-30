"""NEXIS Living Particle Core. CPU QPainter projection, no inference/audio I/O."""

import math
from enum import Enum
from time import perf_counter

from PySide6.QtCore import QEvent, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPixmap, QRadialGradient
from PySide6.QtWidgets import QWidget

from nexis.ui.themes import color


class ReactorState(str, Enum):
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    PROCESSING = "PROCESSING"  # Existing controller's THINKING state.
    SPEAKING = "SPEAKING"
    EXECUTING = "EXECUTING"
    SUCCESS = "SUCCESS"  # Retained for existing command completion feedback.
    ERROR = "ERROR"
    WAITING_PERMISSION = "WAITING_PERMISSION"
    MUTED = "MUTED"
    OFFLINE = "OFFLINE"


def fibonacci_sphere(count=340):
    if not 200 <= count <= 400:
        raise ValueError("Particle count must be between 200 and 400.")
    golden_angle = math.pi * (3.0 - math.sqrt(5.0))
    points = []
    for index in range(count):
        y = 1.0 - 2.0 * index / (count - 1)
        radius = math.sqrt(max(0.0, 1.0 - y * y))
        theta = golden_angle * index
        points.append((math.cos(theta) * radius, y, math.sin(theta) * radius))
    return tuple(points)


class ReactorWidget(QWidget):
    activated = Signal()
    state_changed = Signal(str)
    # speed (degrees/s), radius, brightness, wave displacement, atmosphere
    PROFILES = {
        ReactorState.IDLE: (4., 1., .83, .006, .55),
        ReactorState.LISTENING: (7., 1.045, 1., .017, .68),
        ReactorState.PROCESSING: (17., 1.015, 1., .023, .75),
        ReactorState.SPEAKING: (9., 1.02, 1., .012, .72),
        ReactorState.EXECUTING: (13., 1.015, .98, .018, .72),
        ReactorState.SUCCESS: (5., 1., .96, .008, .65),
        ReactorState.ERROR: (3., 1., .92, .006, .62),
        ReactorState.WAITING_PERMISSION: (3., 1., .96, .009, .65),
        ReactorState.MUTED: (.6, .98, .48, .002, .25),
        ReactorState.OFFLINE: (1., .98, .57, .003, .3),
    }
    SPEEDS = {state: profile[0] for state, profile in PROFILES.items()}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.state = ReactorState.IDLE
        self.particles = fibonacci_sphere()
        self.reduced_motion, self.paused = False, False
        self.active_fps = 30
        self.audio_level = None
        self.smoothed_amplitude = 0.
        self._level_time = 0.
        self.phase = 0.
        self.elapsed = 0.
        self.last_tick = perf_counter()
        self.state_started = self.last_tick
        self._profile = list(self.PROFILES[self.state])
        self._rgb = list(color("primary").getRgb()[:3])
        self.paint_count, self.paint_seconds = 0, 0.
        self._cache, self._cache_key = None, None
        self._core_cache = {}  # Existing appearance invalidation contract.
        self._brush_key, self._brushes = None, None
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.advance)
        self.setMinimumSize(220, 220)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAccessibleName("NEXIS particle core: open manual commands")
        self.setToolTip("Open manual commands · Enter or Space")

    def state_color(self):
        role = {ReactorState.WAITING_PERMISSION: "warning", ReactorState.ERROR: "error",
                ReactorState.SUCCESS: "success", ReactorState.MUTED: "muted",
                ReactorState.OFFLINE: "muted"}.get(self.state, "primary")
        return color(role)

    def set_state(self, state):
        state = {"THINKING": "PROCESSING", "PERMISSION_REQUIRED": "WAITING_PERMISSION"}.get(state, state)
        state = ReactorState(state)
        if state != self.state:
            self.state = state
            self.state_started = perf_counter()
            self.audio_level = None
            self._level_time = 0.
            if state in {ReactorState.MUTED, ReactorState.OFFLINE}:
                self.smoothed_amplitude = 0.
            self.state_changed.emit(state.value)
        if self.reduced_motion or not self.isVisible():
            self._profile = list(self.PROFILES[state])
            self._rgb = list(self.state_color().getRgb()[:3])
        self.setAccessibleDescription(self.caption())
        self.sync_timer()
        self.update()

    def set_audio_level(self, level):
        # Only authorized, current capture/playback callbacks may supply levels.
        # No polling, capture, retained buffers or generated speech waveform here.
        if self.state not in {ReactorState.LISTENING, ReactorState.SPEAKING}:
            self.audio_level = None
            return
        try:
            value = float(level) if level is not None else None
        except (ValueError, TypeError):
            value = None
        self.audio_level = max(0., min(1., value)) if value is not None and math.isfinite(value) else None
        self._level_time = perf_counter()

    def set_particle_count(self, count):
        self.particles = fibonacci_sphere(count)
        self.update()

    def set_reduced_motion(self, enabled):
        self.reduced_motion = bool(enabled)
        if enabled:
            self._profile = list(self.PROFILES[self.state])
            self._rgb = list(self.state_color().getRgb()[:3])
            self.smoothed_amplitude = 0.
        self.sync_timer()
        self.update()

    def set_paused(self, paused):
        self.paused = bool(paused)
        self.sync_timer()

    def set_fps(self, fps):
        self.active_fps = max(10, min(30, int(fps)))
        self.sync_timer()

    def sync_timer(self):
        if self.paused or self.reduced_motion or not self.isVisible() or self.window().isMinimized():
            self.timer.stop()
            return
        fps = min(self.active_fps, 8 if self.state in {
            ReactorState.IDLE, ReactorState.MUTED, ReactorState.OFFLINE} else 30)
        interval = round(1000 / fps)
        if not self.timer.isActive() or self.timer.interval() != interval:
            self.last_tick = perf_counter()
            self.timer.setTimerType(Qt.CoarseTimer if fps <= 8 else Qt.PreciseTimer)
            self.timer.start(interval)

    def advance_motion(self, dt, now):
        """Elapsed-time integration, also used by deterministic geometry tests."""
        dt = max(0., min(dt, .25))
        blend = 1. - math.exp(-5. * dt)
        for index, target in enumerate(self.PROFILES[self.state]):
            self._profile[index] += (target - self._profile[index]) * blend
        target_rgb = self.state_color().getRgb()[:3]
        for index, target in enumerate(target_rgb):
            self._rgb[index] += (target - self._rgb[index]) * blend
        target = (self.audio_level or 0.) if now - self._level_time <= .3 else 0.
        if self.state not in {ReactorState.LISTENING, ReactorState.SPEAKING}:
            target = 0.
        rate = 16. if target > self.smoothed_amplitude else 4.5
        self.smoothed_amplitude += (target - self.smoothed_amplitude) * (1. - math.exp(-rate * dt))
        self.phase = (self.phase + dt * self._profile[0]) % 360.
        self.elapsed += dt

    def advance(self):
        if self.paused or self.reduced_motion or not self.isVisible() or self.window().isMinimized():
            self.timer.stop()
            return
        now = perf_counter()
        self.advance_motion(now - self.last_tick, now)
        self.last_tick = now
        self.update()

    def showEvent(self, event):
        super().showEvent(event)
        self.sync_timer()

    def hideEvent(self, event):
        self.timer.stop()
        self.audio_level = None
        self.smoothed_amplitude = 0.
        super().hideEvent(event)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.WindowStateChange:
            self.sync_timer()

    def closeEvent(self, event):
        self.timer.stop()
        super().closeEvent(event)

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

    def static_geometry(self, size):
        """One restrained atmospheric texture; the visible structure is all dots."""
        dpr = self.devicePixelRatioF()
        key = (size, dpr, color("primary").name(), color("background").name())
        if key == self._cache_key:
            return self._cache
        pixmap = QPixmap(round(size * dpr), round(size * dpr))
        pixmap.setDevicePixelRatio(dpr)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        light = color("background").lightnessF() > .65
        glow = QRadialGradient(size / 2, size / 2, size * .42)
        glow.setColorAt(0., color("primary", 10 if light else 26))
        glow.setColorAt(.5, color("primary", 6 if light else 12))
        glow.setColorAt(1., color("primary", 0))
        painter.setPen(Qt.NoPen)
        painter.setBrush(glow)
        painter.drawEllipse(QPointF(size / 2, size / 2), size * .42, size * .42)
        painter.end()
        self._cache, self._cache_key = pixmap, key
        return pixmap

    def projected_particles(self):
        angle = math.radians(self.phase)
        ca, sa = math.cos(angle), math.sin(angle)
        tilt = .28
        ct, st = math.cos(tilt), math.sin(tilt)
        t = 0. if self.reduced_motion else self.elapsed
        amplitude = 0. if self.reduced_motion else self.smoothed_amplitude
        breathing = 0. if self.reduced_motion else .009 * math.sin(t * .85)
        wave = 0. if self.reduced_motion else self._profile[3]
        result = []
        for index, (x, y, z) in enumerate(self.particles):
            # Rotate the cached unit sphere as a single formation.
            rx, rz = x * ca + z * sa, z * ca - x * sa
            ry, rz = y * ct - rz * st, y * st + rz * ct
            displacement = wave * math.sin(y * 4.5 + t * 2.1 + x * 1.8)
            displacement += amplitude * .075 * (.6 + .4 * math.sin(y * 6. + t * 4.))
            radius = self._profile[1] + breathing + displacement
            depth = rz * radius
            perspective = 4.8 / (4.8 - depth)
            result.append((depth, rx * radius * perspective, ry * radius * perspective,
                           .78 + .5 * (rz + 1.) / 2., (rz + 1.) / 2., index))
        result.sort(key=lambda point: point[0])
        return result

    def sprites(self, scale):
        rgb = tuple(round(v) for v in self._rgb)
        accent = color("accent")
        light = color("background").lightnessF() > .65
        brightness = round(self._profile[2] * 20) / 20
        dpr = self.devicePixelRatioF()
        key = (rgb, accent.name(), light, brightness, scale, dpr)
        if key != self._brush_key:
            groups = []
            for base in (QColor(*rgb), accent):
                brushes = []
                for depth in range(24):
                    opacity = (.32 + .68 * depth / 23) * brightness
                    dot = QColor(base)
                    dot.setAlpha(round(255 * min(1., opacity)))
                    halo = QColor(base)
                    halo.setAlpha(round(255 * opacity * (.08 if light else .13)))
                    size = (.78 + .5 * depth / 23) * scale
                    extent = math.ceil(size * 4.2 + 2.)
                    sprite = QPixmap(math.ceil(extent * dpr), math.ceil(extent * dpr))
                    sprite.setDevicePixelRatio(dpr)
                    sprite.fill(Qt.transparent)
                    painter = QPainter(sprite)
                    painter.setRenderHint(QPainter.Antialiasing)
                    painter.setPen(Qt.NoPen)
                    center = QPointF(extent / 2., extent / 2.)
                    painter.setBrush(halo)
                    painter.drawEllipse(center, size * 2.1, size * 2.1)
                    painter.setBrush(dot)
                    painter.drawEllipse(center, size, size)
                    painter.end()
                    brushes.append((sprite, extent / 2.))
                groups.append(brushes)
            self._brushes, self._brush_key = groups, key
        return self._brushes

    def caption(self):
        return {ReactorState.PROCESSING: "THINKING", ReactorState.WAITING_PERMISSION: "PERMISSION REQUIRED"}.get(self.state, self.state.value)

    def paintEvent(self, event):
        started = perf_counter()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        side = min(self.width(), self.height()) - 12
        if side <= 0:
            p.end()
            return
        if self.reduced_motion:
            self._rgb = list(self.state_color().getRgb()[:3])
        cx, cy = self.width() / 2., self.height() / 2. - side * .035
        p.setOpacity(self._profile[4])
        p.drawPixmap(round(cx - side / 2), round(cy - side / 2), self.static_geometry(side))
        p.setOpacity(1.)
        p.setPen(Qt.NoPen)
        radius = side * .35
        dot_scale = max(.75, min(1.65, side / 360.))
        palettes = self.sprites(dot_scale)
        # Tiny antialiased dot/halo sprites are reused at 24 depth levels.
        # No per-frame ellipse rasterization, brushes or radial gradients.
        for depth, x, y, dot_size, brightness, index in self.projected_particles():
            highlight = index % (19 if self.state == ReactorState.EXECUTING else 37) == 0
            bucket = min(23, max(0, round(brightness * 23)))
            sprite, offset = palettes[int(highlight)][bucket]
            p.drawPixmap(QPointF(cx + x * radius - offset, cy - y * radius - offset), sprite)
        p.setPen(Qt.NoPen)
        # A single slow attention/warning pulse, never a flashing full surface.
        if not self.reduced_motion and self.state in {ReactorState.WAITING_PERMISSION, ReactorState.ERROR}:
            age = perf_counter() - self.state_started
            pulse = (.5 + .5 * math.sin(age * 1.5)) if self.state == ReactorState.WAITING_PERMISSION else max(0., 1. - age / 1.2)
            p.setBrush(self.state_color())
            p.setOpacity(.35 + pulse * .4)
            p.drawEllipse(QPointF(cx, cy + side * .425), 2., 2.)
            p.setOpacity(1.)
        p.setPen(color("text"))
        p.setFont(QFont("Consolas", max(8, min(11, round(side / 40))), QFont.Bold))
        p.drawText(QRectF(0, cy + side * .45, self.width(), 22), Qt.AlignCenter, self.caption())
        if self.hasFocus():
            p.setPen(QPen(color("accent"), 1., Qt.DotLine))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(QRectF(cx - 92, cy + side * .45, 184, 22), 4, 4)
        p.end()
        self.paint_count += 1
        self.paint_seconds += perf_counter() - started
