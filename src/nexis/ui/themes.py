"""One application palette shared by controls, dialogs and painted HUD surfaces."""
from pathlib import Path

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from nexis.core.themes import tokens

_DEFAULT = tokens()
_CURRENT = _DEFAULT
_COLORS = {role: QColor(value) for role, value in _DEFAULT.items()}


def current():
    return _CURRENT


def color(role, alpha=None):
    # Painter callers treat cached colors as immutable. Only alpha variants copy.
    if alpha is None:
        return _COLORS[role]
    value = QColor(_COLORS[role])
    value.setAlpha(alpha)
    return value


def apply(selected, custom=None):
    global _CURRENT, _COLORS
    app = QApplication.instance()
    values = tokens(selected, custom)
    if getattr(app, "nexis_theme", None) == values and app.styleSheet():
        return values
    app.nexis_theme = values
    _CURRENT = values
    _COLORS = {role: QColor(value) for role, value in values.items()}
    palette = QPalette()
    for role, key in ((QPalette.Window, "background"), (QPalette.Base, "panel"),
                      (QPalette.AlternateBase, "hover"), (QPalette.WindowText, "text"),
                      (QPalette.Text, "text"), (QPalette.Button, "panel"),
                      (QPalette.ButtonText, "text"), (QPalette.Highlight, "primary"),
                      (QPalette.HighlightedText, "on_primary"), (QPalette.Link, "primary"),
                      (QPalette.ToolTipBase, "panel"), (QPalette.ToolTipText, "text")):
        palette.setColor(role, QColor(values[key]))
    palette.setColor(QPalette.Disabled, QPalette.Text, QColor(values["muted"]))
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(values["muted"]))
    qss = Path(__file__).with_name("theme.qss").read_text(encoding="utf-8")
    for key, value in values.items():
        qss = qss.replace("@" + key + ";", value + ";")
        qss = qss.replace("@" + key + " ", value + " ")
    windows = [(widget, widget.updatesEnabled()) for widget in app.topLevelWidgets()]
    try:
        for widget, enabled in windows:
            if enabled:
                widget.setUpdatesEnabled(False)
        # Changing the application palette under an active Qt stylesheet causes
        # repeated recursive repolishing. Clear it while repaints are suspended.
        if app.styleSheet():
            app.setStyleSheet("")
        app.setPalette(palette)
        app.setStyleSheet(qss)
    finally:
        for widget, enabled in windows:
            if enabled:
                widget.setUpdatesEnabled(True)
    for widget in app.allWidgets():
        # Cached raster layers must change even while the reactor is reduced-motion/hidden.
        if hasattr(widget, "_cache_key"):
            widget._cache_key = None
            widget._core_cache.clear()
        widget.update()
    return values
