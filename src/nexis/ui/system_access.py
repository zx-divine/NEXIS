"""First-run disclosure and revocable category controls."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QVBoxLayout, QLabel, QCheckBox, QGroupBox
from nexis.core.access import CATEGORIES, DISCLOSURE
from nexis.ui.pages import button


class SystemAccessPanel(QGroupBox):
    revoked = Signal()

    def __init__(self, db, *, show_buttons=True):
        super().__init__("NEXIS — SYSTEM ACCESS & CONTROL")
        self.db = db
        layout = QVBoxLayout(self)
        notice = QLabel(DISCLOSURE)
        notice.setWordWrap(True)
        layout.addWidget(notice)
        self.acknowledged = QCheckBox(
            "I understand this disclosure and the fresh approval requirements."
        )
        self.acknowledged.setChecked(db.setting("system_access_acknowledged"))
        layout.addWidget(self.acknowledged)
        self.choices = {}
        saved = db.setting("access_permissions")
        for key, title in CATEGORIES.items():
            choice = QCheckBox(title)
            choice.setChecked(saved.get(key, False))
            if key == "terminal_commands":
                choice.setChecked(False)
                choice.setEnabled(False)
            layout.addWidget(choice)
            self.choices[key] = choice
        self.status = QLabel(
            "No category authorizes every future action. File access also requires approved folders. High/protected actions always need fresh review."
        )
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        if show_buttons:
            button("Save system access", self.save, layout)
            button("Revoke all capabilities now", self.revoke, layout)

    def save(self):
        if not self.acknowledged.isChecked():
            self.status.setText(
                "Acknowledge the disclosure to enable selected capabilities. Revoke all remains available."
            )
            return False
        self.db.set_setting("system_access_acknowledged", True)
        self.db.set_setting(
            "access_permissions", {key: item.isChecked() for key, item in self.choices.items()}
        )
        self.status.setText(
            "Access choices saved. Revocations apply to the next tool boundary; active capture and requests are cancelled when access changes."
        )
        self.revoked.emit()
        return True

    def revoke(self):
        for choice in self.choices.values():
            choice.setChecked(False)
        self.db.set_setting("access_permissions", {key: False for key in CATEGORIES})
        self.status.setText(
            "All capabilities revoked. Active capture and requests are being stopped."
        )
        self.revoked.emit()
