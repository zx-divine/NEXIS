"""Personalized mode selection and lightweight real-widget appearance previews."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget,
    QTabWidget, QLineEdit,
)

from nexis.core.profile import greeting
from nexis.ui.reactor import ReactorWidget


class ModuleNavigation(QListWidget):
    """Keyboard accessible tool list with the shell's existing navigation contract."""

    def currentText(self):
        item = self.currentItem()
        return item.text() if item else ""

    def setCurrentText(self, text):
        for index in range(self.count()):
            if self.item(index).text() == text:
                self.setCurrentRow(index)
                return


class WelcomePage(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window = window
        self.setObjectName("welcomePage")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 12, 24, 20)
        layout.setSpacing(12)
        self.greeting = QLabel()
        self.greeting.setTextFormat(Qt.PlainText)
        self.greeting.setObjectName("welcomeTitle")
        self.greeting.setWordWrap(True)
        self.greeting.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.greeting)
        prompt = QLabel("Which mode would you like to use?")
        prompt.setObjectName("welcomePrompt")
        prompt.setAlignment(Qt.AlignCenter)
        layout.addWidget(prompt)
        self.reactor = ReactorWidget()
        self.reactor.setMinimumSize(180, 180)
        self.reactor.setAccessibleName("NEXIS status reactor; choose a mode below")
        self.reactor.activated.connect(lambda: window.navigate("Voice Chat"))
        layout.addWidget(self.reactor, 1)
        choices = QHBoxLayout()
        choices.setSpacing(14)
        self.mode_buttons = {}
        for key, title, description, callback in (
            ("voice", "Voice Mode", "Talk with NEXIS", lambda: window.navigate("Voice Chat")),
            ("chat", "Chat Mode", "Type, plan and act", lambda: window.navigate("Chat")),
            ("manual", "Manual / Offline Mode", "Local tools and commands", window.focus_command),
        ):
            control = QPushButton(title + "\n" + description)
            control.setObjectName("modeCard")
            control.setAccessibleName(title)
            control.setMinimumHeight(72)
            control.clicked.connect(callback)
            self.mode_buttons[key] = control
            choices.addWidget(control, 1)
        layout.addLayout(choices)
        self.refresh()

    def refresh(self):
        self.greeting.setText(greeting(self.window.db.setting("preferred_name")))


class ExperiencePreview(QTabWidget):
    """Preview labels and sample content are explicit, never simulated live activity."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAccessibleName("Appearance preview: launch, orb, chat and voice")
        self.setMinimumHeight(220)
        self.reactors = []
        for title in ("Launch", "Orb", "Chat", "Voice"):
            page = QWidget()
            layout = QVBoxLayout(page)
            label = QLabel("APPEARANCE PREVIEW · " + title)
            label.setObjectName("hudLabel")
            layout.addWidget(label)
            if title in ("Orb", "Voice"):
                reactor = ReactorWidget()
                reactor.setMinimumSize(140, 140)
                reactor.set_reduced_motion(True)
                reactor.setAccessibleName(title + " preview, idle example")
                self.reactors.append(reactor)
                layout.addWidget(reactor, 1)
                if title == "Voice":
                    layout.addWidget(QLabel("Microphone off · Preview only"))
            elif title == "Launch":
                text = QLabel("Welcome to NEXIS.\nWhich mode would you like to use?")
                text.setAlignment(Qt.AlignCenter)
                layout.addWidget(text, 1)
                layout.addWidget(QPushButton("Voice   ·   Chat   ·   Manual"))
            else:
                text = QLabel("You: Help me plan my day.\n\nNEXIS: What would you like to work on?")
                text.setWordWrap(True)
                layout.addWidget(text, 1)
                field = QLineEdit()
                field.setPlaceholderText("Preview message field")
                field.setReadOnly(True)
                layout.addWidget(field)
            self.addTab(page, title)
