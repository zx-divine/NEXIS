"""Unsaved appearance previews; saving changes only appearance preferences."""
from PySide6.QtGui import QColor, QRegularExpressionValidator
from PySide6.QtCore import QRegularExpression
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QComboBox, QLineEdit, QColorDialog,
    QHBoxLayout, QLabel, QPushButton,
)
from nexis.core.themes import THEMES, CUSTOM_DEFAULT, theme_id, validate_custom
from nexis.ui.pages import button


class AppearancePanel(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window = window
        layout = QVBoxLayout(self)
        self.theme = QComboBox()
        self.theme.setAccessibleName("Appearance theme")
        for key, label in THEMES.items():
            self.theme.addItem(label, key)
        self.theme.setCurrentIndex(self.theme.findData(theme_id(window.db.setting("theme"))))
        layout.addWidget(self.theme)
        self.custom = QWidget()
        form = QFormLayout(self.custom)
        self.colors = {}
        for key, value in window.db.setting("custom_theme").items():
            row = QHBoxLayout()
            field = QLineEdit(value)
            field.setAccessibleName("Custom theme " + key + " hexadecimal color")
            field.setMaxLength(7)
            field.setValidator(QRegularExpressionValidator(QRegularExpression("#[0-9a-fA-F]{6}"), field))
            self.colors[key] = field
            row.addWidget(field)
            picker = QPushButton("Choose…")
            picker.setAccessibleName("Choose " + key + " color")
            picker.clicked.connect(lambda checked=False, name=key: self.pick(name))
            row.addWidget(picker)
            form.addRow(key.title(), row)
        layout.addWidget(self.custom)
        self.status = QLabel("Preview changes every window immediately. Save keeps your choice; Revert restores the saved appearance.")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        for label, callback in (("Preview theme", self.preview), ("Save appearance", self.save),
                                ("Revert preview", self.revert), ("Reset to Original Crimson Red", self.reset)):
            button(label, callback, layout)
        self.theme.currentIndexChanged.connect(self.preview)
        self.custom.setVisible(self.theme.currentData() == "custom")
        from nexis.ui.launch_page import ExperiencePreview

        self.experience = ExperiencePreview()
        layout.addWidget(self.experience)

    def pick(self, key):
        value = QColorDialog.getColor(QColor(self.colors[key].text()), self, "Choose " + key,
                                      QColorDialog.DontUseNativeDialog)
        if value.isValid():
            self.colors[key].setText(value.name().upper())
            self.preview()

    def values(self):
        return validate_custom({key: field.text() for key, field in self.colors.items()})

    def preview(self, *args):
        custom = self.theme.currentData() == "custom"
        self.custom.setVisible(custom)
        try:
            self.window.apply_theme(self.theme.currentData(), self.values() if custom else None)
            self.status.setText("Preview active — not saved. Text contrast is checked at 4.5:1; accent and button colors are adjusted for readability.")
            return True
        except ValueError as exc:
            self.status.setText(str(exc))
            return False

    def save(self):
        if not self.preview():
            return
        db = self.window.db
        # Both appearance values commit together; unrelated preferences and credentials stay intact.
        db.set_appearance(self.theme.currentData(), self.values() if self.theme.currentData() == "custom"
                          else db.setting("custom_theme"))
        self.status.setText("Appearance saved. It will be restored at the next start.")

    def revert(self):
        self.theme.blockSignals(True)
        self.theme.setCurrentIndex(self.theme.findData(theme_id(self.window.db.setting("theme"))))
        self.theme.blockSignals(False)
        for key, value in self.window.db.setting("custom_theme").items():
            self.colors[key].setText(value)
        self.preview()
        self.status.setText("Saved appearance restored.")

    def reset(self):
        # Deliberate appearance-only reset; Save is still required.
        for key, value in CUSTOM_DEFAULT.items():
            self.colors[key].setText(value)
        self.theme.setCurrentIndex(self.theme.findData("og"))
        self.preview()
        self.status.setText("Original Crimson Red preview. Save to keep this reset.")
