"""The original artwork, scaled without cropping or recolouring."""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap, QGuiApplication
from PySide6.QtWidgets import (
    QLabel,
    QSplashScreen,
    QWizard,
    QWizardPage,
    QVBoxLayout,
    QCheckBox,
    QScrollArea,
    QMessageBox,
)

from nexis.branding import application_icon, asset
from nexis.core.access import DISCLOSURE
from nexis.ui.system_access import SystemAccessPanel
from nexis.ui.providers_page import AIProvidersPage
from nexis.ui.setup_services import Task
from nexis.ui.pages import button
from nexis.platform.speech import SpeechService
from nexis.core.models import install_model, detect_model


class BrandLogo(QLabel):
    def __init__(self, size=144, parent=None):
        super().__init__(parent)
        self.setAccessibleName("Official NEXIS logo")
        self.setAlignment(Qt.AlignCenter)
        self.setPixmap(
            QPixmap(str(asset("NEXIS_logo.png"))).scaled(
                size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
        )


def splash_screen():
    image = QPixmap(str(asset("NEXIS_logo.png"))).scaled(
        360, 360, Qt.KeepAspectRatio, Qt.SmoothTransformation
    )
    splash = QSplashScreen(image)
    splash.setWindowIcon(application_icon())
    splash.setAccessibleName("NEXIS startup splash")
    return splash


class WelcomeWizard(QWizard):
    """Online-first onboarding; tests are explicit, never automatic capture."""

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db, self.jobs, self.speech = db, [], None
        self.setWindowTitle("Welcome to NEXIS Desktop")
        self.setWindowIcon(application_icon())
        self.setWizardStyle(QWizard.ModernStyle)
        screen = QGuiApplication.primaryScreen()
        available = screen.availableGeometry() if screen else None
        self.resize(
            min(900, available.width() - 70) if available else 900,
            min(680, available.height() - 70) if available else 680,
        )
        self.page_with(
            "Welcome to NEXIS",
            "Your online-first Windows AI operator. Connect your selected provider, review system access, and use Talk for Vosk transcription and Windows speech. NEXIS never changes providers automatically.",
            logo=160,
        )
        self.page_with("NEXIS — SYSTEM ACCESS & CONTROL", DISCLOSURE)
        permissions = QWizardPage()
        permissions.setTitle("Choose system access")
        layout = QVBoxLayout(permissions)
        self.access = SystemAccessPanel(db, show_buttons=False)
        self.scroll(layout, self.access)
        permissions.registerField("accessAcknowledged*", self.access.acknowledged)
        self.addPage(permissions)
        mic, mic_layout = self.page_with(
            "Microphone detection and speech model",
            "No recording starts during setup. Windows desktop microphone privacy must permit access. Press Talk only when you want to record.",
        )
        self.microphone = QLabel(
            "Click Detect devices to query Windows without opening audio streams."
        )
        self.microphone.setWordWrap(True)
        mic_layout.addWidget(self.microphone)
        button("Detect microphone and speaker", self.detect_devices, mic_layout)
        self.model_button = button("Set up English speech model (41.2 MB)", self.download_model, mic_layout)
        self.refresh_model()
        speaker, speaker_layout = self.page_with(
            "Speaker verification",
            "Click Test Windows speech, then confirm only if you heard the complete sentence. Synthesis completion alone does not prove audibility.",
        )
        self.speaker_status = QLabel("Speaker test has not been performed.")
        self.speaker_status.setWordWrap(True)
        speaker_layout.addWidget(self.speaker_status)
        button("Test Windows speech", self.test_speaker, speaker_layout)
        self.heard = QCheckBox("I heard the full speaker test sentence")
        speaker_layout.addWidget(self.heard)
        provider = QWizardPage()
        provider.setTitle("Configure your AI provider")
        layout = QVBoxLayout(provider)
        self.provider = AIProvidersPage(db.path.parent)
        self.scroll(layout, self.provider)
        self.addPage(provider)
        _, connection_layout = self.page_with(
            "Provider connection test",
            "Use Test connection / inference on the previous page to test the exact saved configuration. Refresh models checks model-list access separately. No ping or unrelated website can block provider requests. You can finish setup and repair a provider later; your requests will remain available for Retry.",
        )
        button("Back to provider testing", self.back, connection_layout)
        _, desktop_layout = self.page_with(
            "Desktop automation test",
            "This read-only check lists available catalog entries. It does not launch programs, modify files, change Windows settings or start recording.",
        )
        self.desktop_status = QLabel("Test not performed.")
        desktop_layout.addWidget(self.desktop_status)
        button("Check application catalog", self.check_catalog, desktop_layout)
        _, finish_layout = self.page_with(
            "Setup completion",
            "Review access in Settings and configure providers on AI Providers at any time. Real microphone transcription, audible playback and live automation still need your own test. NEXIS does not mark unperformed tests as passed.",
            logo=96,
        )
        self.history = QCheckBox("Keep local command history (arguments are not logged)")
        self.history.setChecked(db.setting("history_enabled"))
        self.motion = QCheckBox("Reduce interface motion")
        self.motion.setChecked(db.setting("reduced_motion"))
        finish_layout.addWidget(self.history)
        finish_layout.addWidget(self.motion)
        self.setButtonText(QWizard.FinishButton, "Open NEXIS")

    @staticmethod
    def scroll(layout, widget):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(widget)
        layout.addWidget(scroll)

    def page_with(self, title, text, logo=0):
        page = QWizardPage()
        page.setTitle(title)
        layout = QVBoxLayout(page)
        if logo:
            layout.addWidget(BrandLogo(logo))
        description = QLabel(text)
        description.setWordWrap(True)
        layout.addWidget(description)
        self.addPage(page)
        return page, layout

    def detect_devices(self):
        def detect(cancel, progress):
            import sounddevice as sd

            return (
                "Microphone: "
                + sd.query_devices(kind="input")["name"]
                + "\nSpeaker: "
                + sd.query_devices(kind="output")["name"]
                + "\nNo audio stream opened."
            )

        task = Task(detect, self)
        task.result.connect(self.microphone.setText)
        task.failed.connect(self.microphone.setText)
        self.jobs.append(task)
        task.start()

    def refresh_model(self):
        path = detect_model(self.db.setting("voice_model_path"), self.db.path.parent)
        if path:
            self.db.set_setting("voice_model_path", path)
            self.model_button.setText("English offline model included — ready")
            self.model_button.setEnabled(False)
            self.microphone.setText("Offline recognition model is ready. Device detection is optional; recording stays off.")
        return path

    def download_model(self):
        if self.refresh_model():
            return
        if any(task.isRunning() for task in self.jobs):
            return
        if (
            QMessageBox.question(
                self,
                "Download speech model?",
                "Download English (US), 41.2 MB, Apache-2.0, from alphacephei.com? NEXIS verifies its pinned SHA-256 and installs it in managed application data. No recording starts.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            != QMessageBox.Yes
        ):
            return
        task = Task(
            lambda cancel, progress: install_model(
                self.db.path.parent, cancel, progress, consent=True
            ),
            self,
        )
        task.progress.connect(self.microphone.setText)
        task.result.connect(self.model_installed)
        task.failed.connect(self.microphone.setText)
        self.jobs.append(task)
        task.start()

    def model_installed(self, path):
        self.db.set_setting("voice_model_path", path)
        self.microphone.setText("Verified model installed. Recording remains off.")
        self.refresh_model()

    def test_speaker(self):
        if not self.speech or not self.speech.isRunning():
            self.speech = SpeechService(self.db.setting("tts_voice"))
            self.speech.status.connect(self.speaker_status.setText)
            self.speech.playback_finished.connect(
                lambda identifier, outcome: self.speaker_status.setText(
                    "Synthesis "
                    + outcome
                    + ". Confirm audibility yourself; NEXIS cannot hear your speaker."
                )
            )
            self.speech.start()
        self.speech.say("Hello. I am NEXIS. My voice engine is working.")

    def check_catalog(self):
        from nexis.core.catalog import Catalog

        self.desktop_status.setText(
            str(len(Catalog(self.db).rows()))
            + " catalog entries available. Discovery refresh is on Applications; no app launched in this test."
        )

    def active_jobs(self):
        return [
            job for job in [*self.jobs, *self.provider.jobs, self.speech] if job and job.isRunning()
        ]

    def stop_jobs(self):
        for job in self.active_jobs():
            job.cancel.set()

    def accept(self):
        self.stop_jobs()
        if self.active_jobs():
            QTimer.singleShot(100, self.accept)
            return
        if not self.access.save():
            self.setCurrentId(2) if hasattr(self, "setCurrentId") else self.restart()
            return
        self.db.set_setting("history_enabled", self.history.isChecked())
        self.db.set_setting("reduced_motion", self.motion.isChecked())
        self.db.set_setting("welcome_completed", True)
        super().accept()

    def reject(self):
        self.stop_jobs()
        if self.active_jobs():
            QTimer.singleShot(100, self.reject)
            return
        super().reject()
