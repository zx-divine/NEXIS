from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QTextEdit,
    QVBoxLayout,
)


def confirm(parent, preview):
    dialog = QDialog(parent)
    dialog.setWindowTitle("Permission preview")
    dialog.setMinimumWidth(480)
    layout = QVBoxLayout(dialog)
    for text in (
        "Action: " + preview.action,
        "Target: " + preview.target,
        "Expected effect: " + preview.effect,
        "Risk: " + preview.risk.name,
        "Permissions: " + preview.permission,
    ):
        label = QLabel(text)
        label.setWordWrap(True)
        label.setTextFormat(__import__("PySide6.QtCore", fromlist=["Qt"]).Qt.PlainText)
        layout.addWidget(label)
    buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    buttons.button(QDialogButtonBox.Ok).setText("Confirm")
    buttons.button(QDialogButtonBox.Cancel).setDefault(True)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    return dialog.exec() == QDialog.Accepted


def edit(parent, title, fields, multiline=()):
    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    dialog.resize(560, 360)
    form = QFormLayout(dialog)
    controls = {}
    for key, value in fields.items():
        widget = QTextEdit() if key in multiline else QLineEdit()
        if key in multiline:
            widget.setAcceptRichText(False)
        widget.setPlainText(value) if key in multiline else widget.setText(value)
        controls[key] = widget
        form.addRow(key, widget)
    buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    form.addRow(buttons)
    if dialog.exec() != QDialog.Accepted:
        return None
    return {
        key: widget.toPlainText() if key in multiline else widget.text()
        for key, widget in controls.items()
    }
