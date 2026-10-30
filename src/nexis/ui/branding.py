"""The original artwork, scaled without cropping or recolouring."""

import logging
import sqlite3

from PySide6.QtCore import Qt, QTimer, QEvent
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
    QLineEdit,
    QDialog,
    QDialogButtonBox,
    QTabWidget,
    QWidget,
    QFormLayout,
    QComboBox,
    QProgressBar,
    QHBoxLayout,
)

from nexis.branding import application_icon, asset
from nexis.core.access import DISCLOSURE
from nexis.ui.system_access import SystemAccessPanel
from nexis.ui.providers_page import AIProvidersPage
from nexis.ui.setup_services import Task
from nexis.ui.pages import button
from nexis.platform.speech import SpeechService
from nexis.core.models import install_model, detect_model
from nexis.core.profile import LAUNCH_MODES, preferred_name
from nexis.core.voice import VoiceWorker, setup_status
from nexis.core.audio import input_options, level_percent


def brand_pixmap(size, ratio=1.0, *, symbol=False):
    name = "NEXIS_symbol.png" if symbol else "NEXIS_logo.png"
    image = QPixmap(str(asset(name))).scaled(
        round(size * ratio), round(size * ratio), Qt.KeepAspectRatio, Qt.SmoothTransformation
    )
    image.setDevicePixelRatio(ratio)
    return image


class BrandLogo(QLabel):
    def __init__(self, size=144, parent=None, *, symbol=False):
        super().__init__(parent)
        self._logo_size, self._symbol = size, symbol
        self.setAccessibleName("Official NEXIS N symbol" if symbol else "Official NEXIS logo")
        self.setAlignment(Qt.AlignCenter)
        self.refresh_pixmap()

    def refresh_pixmap(self):
        self.setPixmap(brand_pixmap(self._logo_size, self.devicePixelRatioF(), symbol=self._symbol))

    def event(self, event):
        if event.type() == QEvent.DevicePixelRatioChange and hasattr(self, "_logo_size"):
            self.refresh_pixmap()
        return super().event(event)


def splash_screen():
    screen = QGuiApplication.primaryScreen()
    image = brand_pixmap(360, screen.devicePixelRatio() if screen else 1.0)
    splash = QSplashScreen(image)
    splash.setWindowIcon(application_icon())
    splash.setAccessibleName("NEXIS startup splash")
    return splash


class WelcomeWizard(QWizard):
    """Online-first onboarding; tests are explicit, never automatic capture."""

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db, self.jobs, self.speech = db, [], None
        self.microphone_worker = None
        self._closing_setup = False
        self._completed_setup = False
        self._resume_page = 0
        self._resume_timer = QTimer(self)
        self._resume_timer.setSingleShot(True)
        self._resume_timer.timeout.connect(self.commit_completion)
        self._appearance_before = (db.setting("theme"), db.setting("custom_theme"))
        self.setWindowTitle("NEXIS")
        self.setWindowIcon(application_icon())
        self.setWizardStyle(QWizard.ModernStyle)
        screen = QGuiApplication.primaryScreen()
        available = screen.availableGeometry() if screen else None
        self.resize(
            min(900, available.width() - 70) if available else 900,
            min(680, available.height() - 70) if available else 680,
        )
        _, identity_layout = self.page_with(
            "Welcome to NEXIS",
            "Your Windows assistant for conversation and permitted desktop tasks. Choose what NEXIS calls you; the name is saved locally and included with configured AI conversations for personalization. Change it in Settings whenever you want.",
            logo=110,
        )
        identity_layout.addWidget(QLabel("What should NEXIS call you?"))
        self.preferred_name = QLineEdit(db.setting("preferred_name"))
        self.preferred_name.setMaxLength(80)
        self.preferred_name.setPlaceholderText("Your preferred name")
        self.preferred_name.setAccessibleName("What should NEXIS call you?")
        identity_layout.addWidget(self.preferred_name)
        self.identity_status = QLabel("")
        self.identity_status.setWordWrap(True)
        identity_layout.addWidget(self.identity_status)
        self.page_with("NEXIS — SYSTEM ACCESS & CONTROL", DISCLOSURE + "\n\nAdministrator access: installing software, changing protected system settings or accessing protected locations may need Windows UAC. NEXIS runs as your normal user. Privileged actions are currently handed off to Windows; the entire app is never permanently elevated.")
        permissions = AcknowledgmentPage()
        self.access_page = permissions
        permissions.setTitle("Choose system access")
        layout = QVBoxLayout(permissions)
        self.access = SystemAccessPanel(db, show_buttons=False)
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.addWidget(self.access)
        self.screen_enabled = QCheckBox("Enable screen assistance (capture only when I request it)")
        self.screen_enabled.setChecked(db.setting("screen_awareness_enabled"))
        body_layout.addWidget(self.screen_enabled)
        screen_notice = QLabel("Screen assistance can capture visible text and images, including private information. You review a preview and approve transmission to your configured vision model. Enable Screen capture above as well. Disable either choice in Settings whenever needed.")
        screen_notice.setWordWrap(True)
        body_layout.addWidget(screen_notice)
        self.scroll(layout, body)
        # A Qt mandatory field compares against its INITIAL value. An initially
        # checked persisted acknowledgment can therefore never complete the page.
        permissions.acknowledgment = self.access.acknowledged
        self.access.acknowledged.toggled.connect(permissions.completeChanged)
        self.access.acknowledged.toggled.connect(self.acknowledgment_feedback)
        self.acknowledgment_feedback()
        self.addPage(permissions)
        mic, mic_layout = self.page_with(
            "Microphone detection and speech model",
            'Test input locally by saying: "Hey NEXIS, can you hear me?" Press Test phrase to begin. Windows microphone privacy must allow desktop apps. This test does not activate a wake-word detector or send audio to an AI provider.',
        )
        self.microphone = QLabel(
            "Click Detect devices to query Windows without opening audio streams."
        )
        self.microphone.setWordWrap(True)
        mic_layout.addWidget(self.microphone)
        button("Detect microphone and speaker", self.detect_devices, mic_layout)
        self.model_button = button("Set up English speech model (41.2 MB)", self.download_model, mic_layout)
        self.refresh_model()
        self.mic_level = QProgressBar()
        self.mic_level.setRange(0, 100)
        self.mic_level.setAccessibleName("Live microphone input level during explicit setup test")
        mic_layout.addWidget(self.mic_level)
        self.mic_transcript = QLabel("Phrase test not performed.")
        self.mic_transcript.setTextFormat(Qt.PlainText)
        self.mic_transcript.setWordWrap(True)
        mic_layout.addWidget(self.mic_transcript)
        row = QHBoxLayout()
        self.phrase_button = button("Test phrase", self.test_microphone, row)
        self.stop_phrase = button("Stop and transcribe", self.finish_microphone, row)
        self.stop_phrase.setEnabled(False)
        button("Mute / cancel input", self.cancel_microphone, row)
        mic_layout.addLayout(row)
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
        provider.setTitle("Set up your AI API")
        self.provider_page_id = 5
        layout = QVBoxLayout(provider)
        self.api_setup_choice = QComboBox()
        self.api_setup_choice.setAccessibleName('First-run AI API setup choice')
        self.api_setup_choice.addItem('Set up AI now — save a provider, API key and model', 'configured')
        self.api_setup_choice.addItem('Use Manual / Offline for now — configure AI later in Settings', 'later')
        layout.addWidget(self.api_setup_choice)
        self.api_status = QLabel('Choose a provider, enter your own API key and model, then click Save & use as default. Ollama can use an existing local server without an API key. Test requests are optional and explicit.')
        self.api_status.setWordWrap(True)
        layout.addWidget(self.api_status)
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
        self.always_active = QCheckBox('Enable Always Active — floating orb and tray availability')
        self.always_active.setChecked(db.setting('floating_orb_enabled'))
        desktop_layout.addWidget(self.always_active)
        self.wake_word = QCheckBox('Also listen locally for “Hey NEXIS” (optional microphone access)')
        self.wake_word.setChecked(db.setting('wake_word_enabled'))
        self.wake_word.toggled.connect(lambda enabled: self.always_active.setChecked(True) if enabled else None)
        desktop_layout.addWidget(self.wake_word)
        wake_notice = QLabel('Wake listening processes standby audio locally in memory and discards it. After activation, the command may be sent to your configured provider. Enable Microphone access on the permissions page as well. Hard mute stops listening. Startup at Windows sign-in is a separate setting.')
        wake_notice.setWordWrap(True)
        desktop_layout.addWidget(wake_notice)
        _, finish_layout = self.page_with(
            "Choose your appearance",
            "Preview the launch screen, orb, chat and voice interface. The approved NEXIS logo stays unchanged. Tests you skipped remain unverified; you can return to Settings later.",
        )
        from nexis.ui.appearance import AppearancePanel

        appearance_body = QWidget()
        appearance_layout = QVBoxLayout(appearance_body)
        self.appearance = AppearancePanel(self)
        appearance_layout.addWidget(self.appearance)
        self.scroll(finish_layout, appearance_body)
        self.history = QCheckBox("Keep local command history (arguments are not logged)")
        self.history.setChecked(db.setting("history_enabled"))
        self.motion = QCheckBox("Reduce interface motion")
        self.motion.setChecked(db.setting("reduced_motion"))
        finish_layout.addWidget(self.history)
        finish_layout.addWidget(self.motion)
        self.setButtonText(QWizard.FinishButton, "Open NEXIS")
        self.setOption(QWizard.HaveCustomButton1, True)
        self.setButtonText(QWizard.CustomButton1, "⚙ Settings")
        self.button(QWizard.CustomButton1).setAccessibleName("Open setup settings")
        self.customButtonClicked.connect(self.open_setup_settings)
        self.currentIdChanged.connect(self.page_changed)
        self.restore_progress()

    def acknowledgment_feedback(self):
        message = (
            "Acknowledgment complete. All capability grants below are optional; Next continues setup."
            if self.access.acknowledged.isChecked() else
            "Required: check ‘I understand’ to enable Next. Capability grants below are optional."
        )
        # Keep the requirement visible even when capability choices need scrolling.
        self.access_page.setSubTitle(message)
        self.access.status.setText(message)

    def go_to_page(self, page_id):
        # Available on the supported Qt runtime; Back preserves unregistered inputs.
        self.setCurrentId(page_id)

    def restore_progress(self):
        draft = self.db.setting("onboarding_progress")
        if self.db.setting("welcome_completed") or not draft:
            return
        try:
            name = preferred_name(draft.get("name", ""))
            page = draft.get("page", 0)
            if type(page) is not int or not 0 <= page <= 8:
                return
            self.preferred_name.setText(name)
            self.access.acknowledged.setChecked(draft.get("acknowledged") is True)
            grants = draft.get("grants", {})
            for key, field in self.access.choices.items():
                field.setChecked(grants.get(key) is True and field.isEnabled())
            self.screen_enabled.setChecked(draft.get("screen") is True)
            self.api_setup_choice.setCurrentIndex(self.api_setup_choice.findData(
                "later" if draft.get("api") == "later" else "configured"))
            if page > 2 and not self.access.acknowledged.isChecked():
                page = 2
            if page > 5 and not self.validate_api_choice():
                page = 5
            self._resume_page = page
        except (ValueError, TypeError, AttributeError):
            logging.getLogger(__name__).warning("Invalid onboarding checkpoint; restarting review")

    def checkpoint(self, page_id):
        if self._closing_setup or self._completed_setup or page_id < 0:
            return
        # A draft is never an effective capability grant or a completion flag.
        self.db.set_setting("onboarding_progress", {
            "page": page_id, "name": self.preferred_name.text(),
            "acknowledged": self.access.acknowledged.isChecked(),
            "grants": {key: field.isChecked() for key, field in self.access.choices.items()},
            "screen": self.screen_enabled.isChecked(), "api": self.api_setup_choice.currentData(),
        })

    def showEvent(self, event):
        super().showEvent(event)
        if self._resume_page:
            page, self._resume_page = self._resume_page, 0
            # Recreate the validated navigation history, so Back still reaches
            # consent and settings after an interrupted first launch.
            for _ in range(page):
                before = self.currentId()
                self.next()
                if self.currentId() == before:
                    break

    def apply_theme(self, selected=None, custom=None):
        from nexis.ui.themes import apply

        apply(selected or self.db.setting("theme"), self.db.setting("custom_theme") if custom is None else custom)

    def open_setup_settings(self, *args):
        """Edit real setup preferences without losing the current wizard page."""
        if self.microphone_worker:
            self.microphone_worker.cancel.set()
        dialog = QDialog(self)
        dialog.setWindowTitle("NEXIS · Setup settings")
        dialog.resize(680, 560)
        layout = QVBoxLayout(dialog)
        tabs = QTabWidget()
        general = QWidget()
        form = QFormLayout(general)
        name = QLineEdit(self.preferred_name.text())
        name.setMaxLength(80)
        form.addRow("What should NEXIS call you?", name)
        mode = QComboBox()
        for key, title in LAUNCH_MODES.items():
            mode.addItem(title, key)
        mode.setCurrentIndex(mode.findData(self.db.setting("default_launch_mode")))
        form.addRow("Default launch mode", mode)
        screen = QCheckBox("Enable screen assistance with preview and transmission approval")
        screen.setChecked(self.screen_enabled.isChecked())
        form.addRow(screen)
        mute = QCheckBox("Hard mute microphone")
        mute.setChecked(self.db.setting("microphone_muted"))
        form.addRow(mute)
        notice = QLabel("Changes here apply to setup. Review capability grants on Choose system access. Full device, provider, privacy and advanced controls remain in the Settings hub after setup.")
        notice.setWordWrap(True)
        form.addRow(notice)
        tabs.addTab(general, "General")
        from nexis.ui.appearance import AppearancePanel

        appearance = AppearancePanel(self)
        self.scroll_tab(tabs, appearance, "Appearance")
        layout.addWidget(tabs)
        status = QLabel("")
        status.setWordWrap(True)
        layout.addWidget(status)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)

        def save():
            try:
                validated = preferred_name(name.text())
                if not appearance.preview():
                    raise ValueError(appearance.status.text())
                self.preferred_name.setText(validated)
                self.screen_enabled.setChecked(screen.isChecked())
                self.db.set_setting("default_launch_mode", mode.currentData())
                self.db.set_setting("microphone_muted", mute.isChecked())
                self.appearance.theme.setCurrentIndex(self.appearance.theme.findData(appearance.theme.currentData()))
                for key, field in appearance.colors.items():
                    self.appearance.colors[key].setText(field.text())
                self.appearance.preview()
                dialog.accept()
            except ValueError as exc:
                status.setText(str(exc))

        buttons.accepted.connect(save)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()
        self.appearance.preview()
        dialog.deleteLater()

    @staticmethod
    def scroll_tab(tabs, widget, title):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(widget)
        tabs.addTab(scroll, title)

    def page_changed(self, page_id):
        if page_id != 3 and self.microphone_worker:
            self.microphone_worker.cancel.set()
        if page_id != 4 and self.speech:
            self.speech.stop_speaking()
        try:
            self.checkpoint(page_id)
        except (OSError, sqlite3.Error, ValueError):
            self.show_setup_error("Setup progress could not be saved. Check disk space and folder access, then retry.")

    def validateCurrentPage(self):
        if self.currentId() == 0:
            try:
                preferred_name(self.preferred_name.text())
            except ValueError as exc:
                self.identity_status.setText(str(exc))
                return False
        if self.currentId() == 2 and not self.access.acknowledged.isChecked():
            self.acknowledgment_feedback()
            return False
        if self.currentId() == self.provider_page_id and not self.validate_api_choice():
            return False
        return super().validateCurrentPage()

    def validate_api_choice(self):
        if self.api_setup_choice.currentData() == 'later':
            return True
        try:
            profile = self.provider.manager.active()
            if not profile or not profile.get('model'):
                raise ValueError('Save a provider and model, then choose it as default; or explicitly select Manual / Offline for now above.')
        except ValueError as exc:
            self.api_status.setText(str(exc))
            return False
        return True

    def test_microphone(self):
        if self._closing_setup or self.microphone_worker and self.microphone_worker.isRunning():
            return
        try:
            if self.db.setting("microphone_muted"):
                raise ValueError("Hard mute is on. Enable microphone in setup settings or Voice settings before testing.")
            if not self.access.acknowledged.isChecked() or not self.access.choices["microphone_access"].isChecked():
                raise ValueError("Enable Microphone access on Choose system access before testing.")
            ready, message = setup_status(self.db.setting("voice_model_path"))
            if not ready:
                raise ValueError(message)
            if self.speech and self.speech.busy.is_set():
                raise ValueError("Stop speaker playback before testing microphone input.")
            worker = VoiceWorker(self.db.setting("voice_model_path"), self.db.setting("audio_input"), input_options(self.db))
            self.microphone_worker = worker
            self.jobs.append(worker)

            def active():
                return self.microphone_worker is worker and not worker.cancel.is_set() and not self._closing_setup

            worker.status.connect(lambda text: self.microphone.setText(text) if active() else None)
            worker.input_metrics.connect(lambda data: self.mic_level.setValue(level_percent(data["rms"])) if active() else None)
            worker.partial.connect(lambda text: self.mic_transcript.setText("Local preview: " + text) if active() else None)
            worker.transcript.connect(lambda text: self.phrase_result(text) if active() else None)
            worker.failed.connect(lambda text: self.microphone.setText(text) if active() else None)
            worker.finished.connect(self.microphone_finished)
            self.microphone.setText("Preparing microphone — recording requested by you.")
            self.mic_transcript.setText("Say: Hey NEXIS, can you hear me?")
            self.phrase_button.setEnabled(False)
            self.stop_phrase.setEnabled(True)
            worker.start()
        except ValueError as exc:
            self.microphone.setText(str(exc))

    def phrase_result(self, text):
        import re

        words = set(re.findall(r"\w+", text.casefold()))
        if {"can", "you", "hear", "me"}.issubset(words):
            message = "Example phrase recognized locally. Check the original words below."
        elif text.strip():
            message = "Speech detected; example phrase was not fully matched. Try again at normal volume."
        else:
            message = "No speech recognized. Check Windows privacy, selected input and microphone level."
        self.mic_transcript.setText(message + "\nTranscript: " + text)

    def finish_microphone(self):
        if self.microphone_worker:
            self.microphone_worker.stop_recording()

    def cancel_microphone(self):
        if self.microphone_worker:
            self.microphone_worker.cancel.set()
        self.db.set_setting("microphone_muted", True)
        self.mic_level.setValue(0)
        self.microphone.setText("Hard mute enabled. Microphone release requested; test transcript discarded.")

    def microphone_finished(self):
        self.mic_level.setValue(0)
        self.phrase_button.setEnabled(True)
        self.stop_phrase.setEnabled(False)

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
        if self._closing_setup or self._completed_setup:
            return
        try:
            preferred_name(self.preferred_name.text())
            if not self.appearance.preview():
                return
        except ValueError as exc:
            self.identity_status.setText(str(exc))
            self.go_to_page(0)
            return
        if not self.validate_api_choice():
            self.go_to_page(self.provider_page_id)
            return
        if self.wake_word.isChecked() and (not self.always_active.isChecked() or not self.access.choices['microphone_access'].isChecked()):
            self.api_status.setText('Hey NEXIS needs Always Active and an explicit Microphone access grant. Enable them or turn wake listening off.')
            self.go_to_page(self.provider_page_id)
            return
        if not self.access.acknowledged.isChecked():
            self.go_to_page(2)
            self.acknowledgment_feedback()
            return
        self._closing_setup = True
        self.button(QWizard.FinishButton).setEnabled(False)
        self.commit_completion()

    def show_setup_error(self, message):
        if self.currentPage():
            self.currentPage().setSubTitle(message)
        logging.getLogger(__name__).error(message)

    def commit_completion(self):
        self.stop_jobs()
        if self.active_jobs():
            self.currentPage().setSubTitle("Stopping setup tests safely…")
            self._resume_timer.start(100)
            return
        try:
            # The user can navigate while an optional test is stopping. Recheck
            # live requirements at the commit boundary, not just at Finish click.
            if not self.access.acknowledged.isChecked():
                raise ValueError("Select I understand on Choose system access before finishing.")
            if not self.validate_api_choice():
                raise ValueError("Save a provider and model, or select Manual / Offline for now.")
            if self.wake_word.isChecked() and (not self.always_active.isChecked()
                    or not self.access.choices["microphone_access"].isChecked()):
                raise ValueError("Wake listening needs an explicit microphone grant")
            selected = self.appearance.theme.currentData()
            values = {
                "system_access_acknowledged": True,
                "access_permissions": {key: field.isChecked() for key, field in self.access.choices.items()},
                "history_enabled": self.history.isChecked(), "reduced_motion": self.motion.isChecked(),
                "preferred_name": preferred_name(self.preferred_name.text()),
                "ai_setup_choice": self.api_setup_choice.currentData(),
                "floating_orb_enabled": self.always_active.isChecked(),
                "wake_word_enabled": self.wake_word.isChecked(),
                "screen_awareness_enabled": self.screen_enabled.isChecked(),
                "theme": selected,
                "custom_theme": self.appearance.values() if selected == "custom" else self.db.setting("custom_theme"),
                "onboarding_progress": {}, "welcome_completed": True,
            }
            if self.always_active.isChecked():
                values["minimize_to_tray"] = True
            self.db.set_settings(values)
        except (OSError, sqlite3.Error, ValueError) as exc:
            self._closing_setup = False
            self.button(QWizard.FinishButton).setEnabled(True)
            if isinstance(exc, ValueError):
                self.show_setup_error("Review setup requirements: " + str(exc))
            else:
                self.show_setup_error("Setup could not be saved. Check free space and local folder permissions, then click Open NEXIS to retry. Your profile was preserved.")
            return
        self._completed_setup = True
        super().accept()

    def reject(self):
        if self._completed_setup:
            return
        self._resume_timer.stop()
        if not self._closing_setup:
            try:
                self.checkpoint(self.currentId())
            except (OSError, sqlite3.Error, ValueError):
                pass
        self._closing_setup = True
        self.stop_jobs()
        if self.active_jobs():
            QTimer.singleShot(100, self.reject)
            return
        from nexis.ui.themes import apply

        apply(*self._appearance_before)
        super().reject()


class AcknowledgmentPage(QWizardPage):
    """Completion depends on consent itself, including consent already persisted."""

    def isComplete(self):
        return hasattr(self, "acknowledgment") and self.acknowledgment.isChecked()
