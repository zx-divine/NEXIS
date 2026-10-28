"""Opt-in local phrase spotting. Ambient audio/text never leaves this worker.

Uses the installed Vosk vocabulary, not a claimed custom neural wake model. Only
speech after a confirmed wake phrase may become a command; no audio is saved.
"""

import json
from queue import Empty, Full, Queue
from threading import Event
from time import monotonic

from PySide6.QtCore import QThread, Signal

from nexis.core.audio import AudioConditioner, InputOptions
from nexis.core.recognition import TranscriptDecoder
from nexis.core.voice import _capture_lock, capture_rates, speech_model
from nexis.platform.speech import default_input


def wake_detected(result, threshold=.85):
    """Require the whole two-word phrase and confidence for both words."""
    words = result.get('result', [])
    return (result.get('text', '').strip().casefold() == 'hey nexis'
            and len(words) == 2 and [word.get('word') for word in words] == ['hey', 'nexis']
            and all(isinstance(word.get('conf'), (int, float)) and threshold <= word['conf'] <= 1 for word in words)
            and .15 <= words[-1].get('end', 0) - words[0].get('start', 0) <= 3)


class WakeWordWorker(QThread):
    status = Signal(str)
    awakened = Signal()
    command = Signal(str)
    failed = Signal(str)

    def __init__(self, model_path, input_preference='', options=None, threshold=.85, allowed=lambda: False):
        super().__init__()
        self.model_path, self.input_preference = model_path, input_preference
        self.options, self.threshold = options or InputOptions(), threshold
        self.allowed = allowed
        self.cancel = Event()

    def run(self):
        owns_capture = False
        try:
            if self.cancel.is_set() or not self.allowed():
                return
            owns_capture = _capture_lock.acquire(blocking=False)
            if not owns_capture:
                raise ValueError('Another microphone session is active. Finish it, then retry wake listening.')
            import sounddevice as sd
            from vosk import KaldiRecognizer, Model, SetLogLevel

            SetLogLevel(-1)
            self.status.emit('Loading local wake recognition — microphone off')
            model = speech_model(self.model_path, Model)
            if any(model.vosk_model_find_word(word) < 0 for word in ('hey', 'nexis')):
                raise ValueError('This speech model lacks the Hey NEXIS vocabulary. Select the bundled English model.')
            device, info = default_input(sd, self.input_preference)
            rate = int(info['default_samplerate'])
            if not 8000 <= rate <= 192000:
                raise ValueError('Unsupported microphone sample rate.')
            for candidate in capture_rates(self.model_path, rate):
                try:
                    sd.check_input_settings(device=device, samplerate=candidate, channels=1, dtype='int16')
                    rate = candidate
                    break
                except Exception:
                    continue
            else:
                raise ValueError('Microphone does not support compatible mono 16-bit capture.')
            keyword = KaldiRecognizer(model, rate, json.dumps(['hey nexis', '[unk]']))
            keyword.SetWords(True)
            conditioner = AudioConditioner(rate, self.options)
            chunks, overflow = Queue(maxsize=40), Event()

            def capture(data, frames, timing, status):
                if self.cancel.is_set():
                    raise sd.CallbackAbort
                if status:
                    overflow.set()
                try:
                    chunks.put_nowait(bytes(data))
                except Full:
                    overflow.set()

            if self.cancel.is_set() or not self.allowed():
                return
            pending = ''
            with sd.RawInputStream(device=device, samplerate=rate, blocksize=rate // 10,
                                   dtype='int16', channels=1, callback=capture):
                self.status.emit('HEY NEXIS — local microphone listening')
                last_chunk, awake_at, decoder = monotonic(), None, None
                while not self.cancel.is_set() and self.allowed():
                    if overflow.is_set():
                        raise ValueError('Wake input overflowed. Reduce audio load, then retry listening.')
                    try:
                        data = chunks.get(timeout=.1)
                    except Empty:
                        if monotonic() - last_chunk > 5:
                            raise ValueError('Microphone stopped supplying audio. Reconnect it, then retry listening.')
                        continue
                    last_chunk = monotonic()
                    processed, _ = conditioner.process(data)
                    if awake_at is None:
                        if keyword.AcceptWaveform(processed) and wake_detected(json.loads(keyword.Result()), self.threshold):
                            # Start a separate unrestricted command decoder only after
                            # activation. Standby content is never replayed into it.
                            decoder = TranscriptDecoder(model, KaldiRecognizer, rate, contextual=False)
                            keyword = None
                            awake_at = monotonic()
                            self.awakened.emit()
                            self.status.emit('LISTENING — Hey NEXIS detected; say your command')
                            conditioner = AudioConditioner(rate, self.options)
                    else:
                        decoder.accept(processed)
                        if conditioner.endpoint and decoder.parts or monotonic() - awake_at >= 20:
                            pending = decoder.finish().strip()[:1000]
                            break
            # Signals cannot dispatch a command until the physical stream is closed.
            if not self.cancel.is_set() and self.allowed():
                self.status.emit('Wake microphone off — processing command' if pending else 'No command heard — returning to standby')
                if pending:
                    self.command.emit(pending)
        except Exception as exc:
            if not self.cancel.is_set():
                message = str(exc) if isinstance(exc, ValueError) else (
                    'Wake listening failed (' + type(exc).__name__ + '). Check Windows microphone access, device and model, then retry. No audio was saved.')
                self.failed.emit(message)
        finally:
            if owns_capture:
                _capture_lock.release()
