"""Visible, permission-gated lifecycle for the local wake worker."""

from time import monotonic

from PySide6.QtCore import QObject, QTimer

from nexis.core.access import require_access
from nexis.core.audio import input_options
from nexis.core.voice import setup_status
from nexis.core.wake_word import WakeWordWorker
from nexis.platform.desktop_state import notification_state


class WakeListening(QObject):
    def __init__(self, desktop):
        super().__init__(desktop)
        self.desktop, self.window = desktop, desktop.window
        self.worker, self.jobs = None, []
        self.active, self.blocked, self.suspended = False, False, True
        self.microphone_active = False
        self.cooldown = 0
        self.configuration = None
        self.timer = QTimer(self)
        self.timer.setInterval(250)
        self.timer.timeout.connect(self.refresh)

    def start(self):
        self.active = True
        self.timer.start()
        self.refresh()

    def pause(self):
        self.microphone_active = False
        self.suspended = True
        self.cooldown = monotonic() + .6
        if self.worker:
            self.worker.cancel.set()

    def stop(self):
        self.active = False
        self.timer.stop()
        self.pause()

    def retry(self):
        self.blocked = False
        self.pause()
        self.refresh()

    def permission(self):
        db = self.window.db
        return (not self.window.closing and not self.suspended
                and db.setting('floating_orb_enabled') and db.setting('wake_word_enabled')
                and not db.setting('microphone_muted')
                and db.setting('system_access_acknowledged')
                and db.setting('access_permissions').get('microphone_access', False)
                and self.configuration is not None
                and (db.setting('voice_model_path'), db.setting('audio_input')) == self.configuration[:2]
                and notification_state() == 5)

    def unavailable(self):
        w = self.window
        if not self.active or w.closing or not w.db.setting('floating_orb_enabled') or not w.db.setting('wake_word_enabled'):
            return 'Wake listening off — enable Always Active and Hey NEXIS to opt in.'
        if w.db.setting('microphone_muted'):
            return 'Hard muted — microphone off. Click Wake to resume your opted-in listening.'
        try:
            require_access(w.db, 'microphone_access')
        except ValueError:
            return 'Microphone permission is off. Review Settings > Permissions.'
        if notification_state() != 5:
            return 'Wake listening paused — Windows is locked, busy, fullscreen or unavailable.'
        if not w.isVisible() and not (self.desktop.tray and self.desktop.tray.isVisible()):
            return 'Wake listening paused — no visible window or tray indicator.'
        if (w.worker and w.worker.isRunning() or any(job.isRunning() for job in w.ai_jobs)
                or w.voice.worker and w.voice.worker.isRunning()
                or w.voice.turn.state.value in {'LISTENING', 'TRANSCRIBING', 'THINKING', 'SPEAKING'}
                or w.settings_page.voice_setup.microphone.worker and w.settings_page.voice_setup.microphone.worker.isRunning()
                or any(job.isRunning() for job in w.settings_page.voice_setup.jobs)
                or w.settings_page.voice_setup.speech and w.settings_page.voice_setup.speech.busy.is_set()):
            return 'Wake listening paused — another voice, speech or command task is active.'
        ready, message = setup_status(w.db.setting('voice_model_path'))
        return '' if ready else message

    def show_status(self, text):
        self.desktop.wake_status.setText(text)
        self.window.always_active_button.setToolTip(text)
        if self.desktop.tray:
            self.desktop.tray.setToolTip(('NEXIS — ' + text)[:127])

    def refresh(self):
        self.jobs = [job for job in self.jobs if job.isRunning() or job is self.worker]
        reason = self.unavailable()
        if reason:
            self.pause()
            self.show_status(reason)
            return
        if self.blocked or monotonic() < self.cooldown:
            return
        self.suspended = False
        configuration = (self.window.db.setting('voice_model_path'), self.window.db.setting('audio_input'),
                         input_options(self.window.db), self.window.db.setting('wake_word_confidence'))
        if self.worker is not None:
            if configuration != self.configuration:
                self.pause()
            return
        self.configuration = configuration
        worker = WakeWordWorker(self.window.db.setting('voice_model_path'), self.window.db.setting('audio_input'),
                                input_options(self.window.db), self.window.db.setting('wake_word_confidence') / 100,
                                self.permission)
        self.worker = worker
        self.jobs.append(worker)
        pending = []

        def active():
            return self.worker is worker and not worker.cancel.is_set() and not self.window.closing

        def status(text):
            if active():
                self.show_status(text)
                if text.startswith(('HEY NEXIS', 'LISTENING')):
                    self.microphone_active = True
                    self.window.set_state('LISTENING')
                elif text.startswith(('Wake microphone off', 'No command heard')):
                    self.microphone_active = False
                    self.window.set_state('PROCESSING' if pending else 'IDLE')

        def awakened():
            if active():
                self.desktop.restore()
                self.window.switch_mode('Voice Chat')
                self.window.voice.status.setText('Hey NEXIS detected locally — say your command, or Hard mute to stop.')
                self.window.voice.indicator.setText('LISTENING — WAKE MICROPHONE ACTIVE')

        def failed(message):
            if active():
                self.microphone_active = False
                self.blocked = True
                self.show_status(message + ' Use Retry wake listening after fixing the issue.')
                self.window.set_state('ERROR')

        def finished():
            self.microphone_active = False
            if not active():
                return
            self.cooldown = monotonic() + 1
            self.window.voice.indicator.setText('WAKE MICROPHONE OFF')
            if pending and self.permission() and not self.unavailable():
                text = pending[-1]
                if text.casefold().strip(' .!?') in {'stop listening', 'hard mute', 'go to sleep', 'sleep nexis', 'sleep nexus'}:
                    self.window.set_microphone_muted(True)
                else:
                    self.window.voice.transcript.setText(text)
                    # Use the existing speech safety policy, including manual radio review.
                    from nexis.core.intents import local_command
                    command = local_command(text)
                    if command and command.startswith('radio '):
                        self.window.voice.status.setText('Review this radio command, then click Retry / send transcript. Nothing was changed.')
                    else:
                        self.window.voice.submit_transcript(reviewed=False)
            elif not self.blocked:
                self.window.set_state('IDLE')

        worker.status.connect(status)
        worker.awakened.connect(awakened)
        worker.command.connect(lambda text: pending.append(text) if active() else None)
        worker.failed.connect(failed)
        worker.finished.connect(finished)
        def cleanup():
            if self.worker is worker:
                self.microphone_active = False
                self.worker = None
            if worker in self.jobs:
                self.jobs.remove(worker)
            if worker.cancel.is_set() and not self.window.closing and self.window.assistant_state.value == 'LISTENING' and self.window.voice.turn.state.value != 'LISTENING':
                self.window.set_state('IDLE')
            worker.deleteLater()

        worker.finished.connect(cleanup)
        worker.start()
