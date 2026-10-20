from threading import Event
from time import monotonic

from PySide6.QtCore import QThread, Signal

from nexis.actions.files import search
from nexis.core.permissions import Permissions
from nexis.core.router import Engine
from nexis.core.results import Result


class CommandWorker(QThread):
    finished_result = Signal(object)
    permission = Signal(object)
    phase = Signal(str)
    step = Signal(int, object)

    def __init__(self, db, text, platform=None):
        super().__init__()
        self.db, self.text, self.platform = db, text, platform
        self.cancel = Event()
        self.pause = Event()
        self.answer = Event()
        self.allowed = False
        self.deadline = None

    def confirm(self, preview):
        self.answer.clear()
        self.allowed = False
        self.permission.emit(preview)
        deadline = self.deadline or monotonic() + 180
        while not self.answer.wait(0.1):
            if self.cancel.is_set() or monotonic() >= deadline:
                self.cancel.set()
                return False
        return self.allowed and not self.cancel.is_set() and monotonic() < deadline

    def respond(self, allowed):
        self.allowed = allowed
        self.answer.set()

    def run(self):
        try:
            engine = Engine(self.db, self.platform, Permissions(self.confirm))
            effective_cancel = self.cancel
            if self.text.strip().casefold().startswith("run "):
                from nexis.core.tools import DeadlineCancel
                effective_cancel = DeadlineCancel(self.cancel, 120)
                self.deadline = effective_cancel.deadline
            result = engine.execute(self.text, effective_cancel, self.step.emit, self.phase.emit, self.pause)
        except Exception as exc:
            import logging

            logging.getLogger("nexis").error("Worker failed (%s)", type(exc).__name__)
            result = Result(False, "Unexpected failure. See local diagnostics.")
        self.finished_result.emit(result)


class SearchWorker(QThread):
    completed = Signal(object)
    progress = Signal(int)
    failed = Signal(str)

    def __init__(self, roots, query, extension, filters=None, access_check=lambda: None):
        super().__init__()
        self.roots, self.query, self.extension = roots, query, extension
        self.cancel = Event()
        self.filters, self.access_check = filters, access_check

    def run(self):
        try:
            self.completed.emit(
                search(self.roots, self.query, self.extension, self.cancel, self.progress.emit,
                       filters=self.filters, access_check=self.access_check)
            )
        except (ValueError, OSError) as exc:
            self.failed.emit(str(exc))
