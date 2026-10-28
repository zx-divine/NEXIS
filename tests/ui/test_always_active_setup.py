from threading import Event

from PySide6.QtCore import QObject, Signal

from nexis.storage.database import Database
from nexis.ui.branding import WelcomeWizard
from nexis.ui.main_window import MainWindow


def test_first_run_requires_name_and_explicit_api_setup_or_offline_choice(qtbot, tmp_path):
    db = Database(tmp_path / 'onboarding.db')
    wizard = WelcomeWizard(db)
    qtbot.addWidget(wizard)
    wizard.show()
    wizard.next()
    assert wizard.currentId() == 0
    wizard.preferred_name.setText('Ananya')
    wizard.access.acknowledged.setChecked(True)
    for _ in range(5):
        wizard.next()
    assert wizard.currentId() == 5
    wizard.next()
    assert wizard.currentId() == 5 and 'Save a provider' in wizard.api_status.text()
    wizard.accept()
    assert not db.setting('welcome_completed')
    wizard.api_setup_choice.setCurrentIndex(wizard.api_setup_choice.findData('later'))
    wizard.accept()
    assert db.setting('welcome_completed') and db.setting('preferred_name') == 'Ananya'
    assert db.setting('ai_setup_choice') == 'later'
    assert not db.setting('floating_orb_enabled') and not db.setting('wake_word_enabled')
    db.close()


def test_onboarding_wake_opt_in_needs_microphone_grant_and_persists(qtbot, db):
    wizard = WelcomeWizard(db)
    qtbot.addWidget(wizard)
    wizard.preferred_name.setText('ASH')
    wizard.api_setup_choice.setCurrentIndex(wizard.api_setup_choice.findData('later'))
    wizard.wake_word.setChecked(True)
    assert wizard.always_active.isChecked()
    wizard.access.choices['microphone_access'].setChecked(False)
    wizard.accept()
    assert not db.setting('welcome_completed')
    wizard.access.choices['microphone_access'].setChecked(True)
    wizard.accept()
    assert db.setting('floating_orb_enabled') and db.setting('wake_word_enabled')
    assert db.setting('minimize_to_tray')
    assert not wizard.microphone_worker and not wizard.jobs


class FakeWake(QObject):
    status = Signal(str)
    awakened = Signal()
    command = Signal(str)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, *args):
        super().__init__()
        self.cancel, self.running = Event(), False

    def start(self):
        self.running = True
        self.status.emit('HEY NEXIS — local microphone listening')

    def isRunning(self):
        return self.running

    def complete(self):
        self.running = False
        self.finished.emit()


def test_visible_always_active_wake_handoff_mute_and_permission_revocation(qtbot, db, tmp_path, platform, monkeypatch):
    monkeypatch.setattr('nexis.ui.desktop_page.notification_state', lambda: 5)
    monkeypatch.setattr('nexis.ui.wake_listening.notification_state', lambda: 5)
    monkeypatch.setattr('nexis.ui.wake_listening.setup_status', lambda path: (True, 'ready'))
    monkeypatch.setattr('nexis.ui.wake_listening.WakeWordWorker', FakeWake)
    window = MainWindow(db, tmp_path, platform)
    qtbot.addWidget(window)
    window.show()
    window.always_active_button.click()
    assert window.stack.currentIndex() == window.pages['Desktop Companion']
    page = window.desktop_experience
    page.enabled.setChecked(True)
    page.wake_enabled.setChecked(True)
    page.wake.start()
    page.wake.cooldown = 0
    page.wake.refresh()
    worker = page.wake.worker
    assert worker and worker.isRunning()
    assert 'local microphone listening' in page.wake_status.text()
    sent = []
    monkeypatch.setattr(window.voice, 'submit_transcript', lambda reviewed: sent.append((window.voice.transcript.text(), reviewed)))
    worker.awakened.emit()
    worker.command.emit('what is my name')
    worker.complete()
    assert sent == [('what is my name', False)]
    page.wake.cooldown = 0
    page.wake.refresh()
    worker = page.wake.worker
    window.set_microphone_muted(True)
    assert worker.cancel.is_set()
    worker.command.emit('open notepad')
    worker.complete()
    assert len(sent) == 1 and not platform.calls
    window.set_microphone_muted(False)
    db.set_setting('access_permissions', {**db.setting('access_permissions'), 'microphone_access': False})
    page.wake.refresh()
    assert page.wake.worker is None
    page.wake.stop()
    window.close()


def test_name_can_be_recalled_locally_without_an_api_or_tool(qtbot, db, tmp_path, platform):
    db.set_setting('preferred_name', 'ASH')
    window = MainWindow(db, tmp_path, platform)
    qtbot.addWidget(window)
    window.conversation_request('What is my name?', 'chat')
    assert "I'll call you ASH." in window.chat.messages.item(window.chat.messages.count() - 1).text()
    assert not window.ai_jobs and not platform.calls
    window.close()


def test_wake_pauses_on_windows_lock_and_discards_a_pending_command(qtbot, db, tmp_path, platform, monkeypatch):
    state = [5]
    monkeypatch.setattr('nexis.ui.desktop_page.notification_state', lambda: state[0])
    monkeypatch.setattr('nexis.ui.wake_listening.notification_state', lambda: state[0])
    monkeypatch.setattr('nexis.ui.wake_listening.setup_status', lambda path: (True, 'ready'))
    monkeypatch.setattr('nexis.ui.wake_listening.WakeWordWorker', FakeWake)
    window = MainWindow(db, tmp_path, platform)
    qtbot.addWidget(window)
    window.show()
    page = window.desktop_experience
    page.enabled.setChecked(True)
    page.wake_enabled.setChecked(True)
    window.navigate('Welcome')
    assert window.mute_button.isVisible()
    page.wake.start()
    page.wake.cooldown = 0
    page.wake.refresh()
    worker = page.wake.worker
    sent = []
    monkeypatch.setattr(window.voice, 'submit_transcript', lambda reviewed: sent.append(True))
    worker.command.emit('open notepad')
    state[0] = 1
    page.wake.refresh()
    assert worker.cancel.is_set() and 'paused' in page.wake_status.text()
    worker.complete()
    assert not sent and not platform.calls
    page.wake.stop()
    window.close()
