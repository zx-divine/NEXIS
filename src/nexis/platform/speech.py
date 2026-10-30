"""Windows SAPI synthesis in its own COM apartment; no idle audio polling."""

from queue import Queue, Empty, Full
from threading import Event
from time import monotonic
from uuid import uuid4

from PySide6.QtCore import QThread, Signal


def default_input(sd, preference=""):
    if isinstance(preference, int):
        device = sd.query_devices(preference, "input")
        if device["max_input_channels"] < 1:
            raise ValueError("The selected device is not a microphone.")
        return preference, device
    if preference:
        for index, device in enumerate(sd.query_devices()):
            if device["name"] == preference and device["max_input_channels"] > 0:
                return index, device
    return None, sd.query_devices(kind="input")


class SpeechService(QThread):
    status = Signal(str)
    voices = Signal(object)
    outputs = Signal(object)
    playback_started = Signal(str)
    playback_finished = Signal(str, str)

    def __init__(self, preference="", output_preference=""):
        super().__init__()
        self.preference = preference
        self.output_preference = output_preference
        self.cancel = Event()
        self.queue = Queue(maxsize=8)
        self.purge = Event()
        self.busy = Event()
        self.generation = 0

    def say(self, text):
        identifier = uuid4().hex
        try:
            self.queue.put_nowait(("say", (identifier, text[:24000], self.generation)))
        except Full:
            self.status.emit(
                "Speech queue is full. Stop speech and retry; this utterance was not queued."
            )
            self.playback_finished.emit(identifier, "ERROR")
            return None
        return identifier

    def stop_speaking(self):
        self.generation += 1
        self.purge.set()
        while not self.queue.empty():
            try:
                action, value = self.queue.get_nowait()
                if action == "say":
                    self.playback_finished.emit(value[0], "CANCELLED")
            except Empty:
                break

    def select(self, value):
        self.preference = value
        if not self.queue.full():
            self.queue.put(("select", value))

    def select_output(self, value):
        # COM tokens are resolved only in the owning speech thread, on the next utterance.
        self.output_preference = value

    def bind_output(self, speaker):
        enumerate_outputs = getattr(speaker, "GetAudioOutputs", None)
        if not enumerate_outputs:
            self.outputs.emit([])
            return
        try:
            tokens = enumerate_outputs()
            available = {tokens.Item(i).Id: tokens.Item(i) for i in range(tokens.Count)}
        except Exception:
            self.outputs.emit([])
            self.status.emit("Speaker enumeration is unavailable; trying the Windows default output.")
            return
        self.outputs.emit([(key, token.GetDescription()) for key, token in available.items()])
        if self.output_preference in available:
            speaker.AudioOutput = available[self.output_preference]
        elif self.output_preference:
            self.status.emit("Saved speaker is unavailable; using the current Windows default output. Your preference is retained for reconnection.")

    def run(self):
        initialized = False
        try:
            if self.cancel.is_set():
                return
            import pythoncom
            import win32com.client

            pythoncom.CoInitialize()
            initialized = True
            if self.cancel.is_set():
                return
            speaker = win32com.client.Dispatch("SAPI.SpVoice")
            if self.cancel.is_set():
                return
            self.bind_output(speaker)
            if self.cancel.is_set():
                return
            tokens = speaker.GetVoices()
            available = {tokens.Item(i).Id: tokens.Item(i) for i in range(tokens.Count)}
            if not available:
                raise ValueError("No Windows speech voice is installed.")
            if self.cancel.is_set():
                return
            self.voices.emit([(key, token.GetDescription()) for key, token in available.items()])
            if self.preference in available:
                speaker.Voice = available[self.preference]
            self.status.emit("Windows speech ready. Output follows your speaker preference; missing speakers fall back to Windows default.")
            while not self.cancel.is_set():
                pythoncom.PumpWaitingMessages()
                try:
                    action, value = self.queue.get(timeout=0.2)
                except Empty:
                    continue
                if action == "select" and value in available:
                    speaker.Voice = available[value]
                elif action == "stop":
                    speaker.Speak("", 3 | 16)  # async, purge, literal text
                elif action == "say":
                    identifier, text, generation = value
                    try:
                        self.busy.set()
                        if generation != self.generation or self.cancel.is_set():
                            self.busy.clear()
                            self.playback_finished.emit(identifier, "CANCELLED")
                            continue
                        if self.purge.is_set():
                            self.purge.clear()
                        speaker.Speak("", 3 | 16)
                        # A fresh default-output binding follows Windows speaker changes.
                        speaker = win32com.client.Dispatch("SAPI.SpVoice")
                        self.bind_output(speaker)
                        refreshed = speaker.GetVoices()
                        for index in range(refreshed.Count):
                            token = refreshed.Item(index)
                            if token.Id == self.preference:
                                speaker.Voice = token
                                break
                        if generation != self.generation or self.cancel.is_set():
                            self.busy.clear()
                            self.playback_finished.emit(identifier, "CANCELLED")
                            continue
                        speaker.Speak(text, 3 | 16)
                        playback_announced = False

                        def announce_playback():
                            nonlocal playback_announced
                            if playback_announced or generation != self.generation or self.cancel.is_set():
                                return
                            try:
                                # SAPI's speaking state, not merely a queued say()
                                # request. This is activity, never PCM amplitude.
                                speaking = int(speaker.Status.RunningState) == 2
                            except Exception:
                                speaking = False
                            if speaking:
                                playback_announced = True
                                self.playback_started.emit(identifier)

                        announce_playback()
                        deadline = monotonic() + 120
                        outcome = "PASS"
                        while not speaker.WaitUntilDone(50):
                            pythoncom.PumpWaitingMessages()
                            announce_playback()
                            if (
                                self.cancel.is_set()
                                or self.purge.is_set()
                                or generation != self.generation
                            ):
                                speaker.Speak("", 3 | 16)
                                outcome = "CANCELLED"
                                break
                            if monotonic() >= deadline:
                                speaker.Speak("", 3 | 16)
                                outcome = "TIMEOUT"
                                break
                        self.purge.clear()
                        if self.cancel.is_set() or generation != self.generation:
                            outcome = "CANCELLED"
                        self.busy.clear()
                        self.playback_finished.emit(identifier, outcome)
                    except Exception:
                        self.busy.clear()
                        self.playback_finished.emit(identifier, "ERROR")
                        self.status.emit(
                            "Speech playback could not start. Check the Windows default speaker; the next request will retry automatically."
                        )
            speaker.Speak("", 3 | 16)
        except Exception:
            self.status.emit(
                "Windows speech output is unavailable. Check installed Windows voices and your default speaker. Other NEXIS features remain available."
            )
        finally:
            self.busy.clear()
            while not self.queue.empty():
                try:
                    action, value = self.queue.get_nowait()
                    if action == "say":
                        self.playback_finished.emit(value[0], "ERROR")
                except Empty:
                    break
            if initialized:
                speaker = None
                tokens = None
                available = {}
                refreshed = None
                token = None
                pythoncom.CoUninitialize()
