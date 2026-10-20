"""Optional local recognition. No model downloads, retained recordings or ambient capture."""

from array import array
from dataclasses import replace
import importlib.util
import math
from pathlib import Path
from queue import Empty, Full, Queue
from threading import Event, Lock
from time import monotonic

from PySide6.QtCore import QThread, Signal
from nexis.platform.speech import default_input
from nexis.core.models import valid_model
from nexis.core.audio import AudioConditioner, InputOptions, calibration_floor
from nexis.core.recognition import TranscriptDecoder

_model_lock = Lock()
_cached_model = None
_cached_path = ""
_capture_lock = Lock()


def speech_model(path, factory):
    global _cached_model, _cached_path
    with _model_lock:
        if _cached_path != path or _cached_model is None:
            _cached_model = None
            _cached_model = factory(path)
            _cached_path = path
        return _cached_model


def audio_level(data: bytes) -> float:
    samples = array("h")
    samples.frombytes(data[: len(data) // 2 * 2])
    if not samples:
        return 0.0
    return min(1.0, math.sqrt(sum(v * v for v in samples) / len(samples)) / 32768)


def setup_status(model_path: str) -> tuple[bool, str]:
    missing = [name for name in ("vosk", "sounddevice", "webrtcvad", "_webrtcvad") if importlib.util.find_spec(name) is None]
    if missing:
        return (
            False,
            "Offline voice components are unavailable in this installation. Repair or reinstall "
            "NEXIS using the complete installer. No models are downloaded without consent. Other features remain available.",
        )
    path = Path(model_path) if model_path else None
    if not path or not path.is_dir() or not valid_model(path):
        return (
            False,
            "Select One-click voice setup to download a verified offline model with your consent. "
            "No microphone is active.",
        )
    return (
        True,
        "Offline recognition ready. Press Push to talk; capture stops after 30 seconds or Stop.",
    )


def capture_rates(model_path, device_rate):
    """Choose model-compatible rates before opening a capture stream.

    Read only the selected model's bounded configuration. Do not modify model
    weights or enable upsampling that the model has not explicitly allowed.
    """
    minimum = 16000
    upsample = False
    try:
        with (Path(model_path) / "conf/mfcc.conf").open(encoding="utf-8") as source:
            config = source.read(65536)
        for line in config.splitlines():
            parts = line.strip().replace("=", " ", 1).split()
            if len(parts) != 2:
                continue
            if parts[0] == "--sample-frequency" and 8000 <= float(parts[1]) <= 192000:
                minimum = int(float(parts[1]))
            if parts[0] == "--allow-upsample":
                upsample = parts[1].lower() == "true"
    except (OSError, UnicodeError, ValueError):
        pass
    candidates = (device_rate, minimum, 16000, 48000, 44100)
    return tuple(dict.fromkeys(rate for rate in candidates if upsample or rate >= minimum))


class VoiceWorker(QThread):
    status = Signal(str)
    level = Signal(float)
    transcript = Signal(str)
    partial = Signal(str)
    failed = Signal(str)
    measured = Signal(object)
    input_metrics = Signal(object)
    calibrated = Signal(float)

    def __init__(self, model_path, input_preference="", options=None, calibrate=False):
        super().__init__()
        self.model_path = model_path
        self.input_preference = input_preference
        self.options = options or InputOptions()
        self.calibrate = calibrate
        self.cancel = Event()
        self.finish_capture = Event()

    def stop_recording(self):
        """Finish and transcribe. Cancellation instead discards pending speech."""
        self.finish_capture.set()

    def run(self):
        owns_capture = False
        try:
            if self.cancel.is_set():
                return
            owns_capture = _capture_lock.acquire(blocking=False)
            if not owns_capture:
                raise ValueError("Another microphone session is still stopping or active. Retry after it releases the input.")
            import sounddevice as sd
            if not self.calibrate:
                from vosk import KaldiRecognizer, Model, SetLogLevel

                SetLogLevel(-1)
                self.status.emit("Loading local speech model…")
                model = speech_model(self.model_path, Model)
            else:
                self.status.emit("Preparing quiet-room calibration; microphone not active yet")
            if self.cancel.is_set():
                return
            device, info = default_input(sd, self.input_preference)
            self.device_name = info.get("name", "Windows default microphone")
            options = self.options
            if options.calibration_device and options.calibration_device != self.device_name:
                options = replace(options, noise_floor=0.001, calibration_device="")
            rate = int(info["default_samplerate"])
            if not 8000 <= rate <= 192000:
                raise ValueError("Unsupported microphone sample rate.")
            candidates = capture_rates(self.model_path, rate)
            checker = getattr(sd, "check_input_settings", None)
            if checker:
                for candidate in candidates:
                    try:
                        checker(device=device, samplerate=candidate, channels=1, dtype="int16")
                        rate = candidate
                        break
                    except Exception:
                        continue
                else:
                    raise ValueError(
                        "Microphone does not support mono 16-bit capture at a compatible sample rate."
                    )
            elif rate not in candidates:
                raise ValueError("Microphone sample rate is incompatible with this speech model. Select another input or a wideband headset mode.")
            decoder = TranscriptDecoder(model, KaldiRecognizer, rate) if not self.calibrate else None
            conditioner = AudioConditioner(rate, options)
            noise_levels = []
            chunks = Queue(maxsize=20)
            overflow = Event()

            def capture(data, frames, timing, status):
                if self.cancel.is_set():
                    abort = getattr(sd, "CallbackAbort", None)
                    if abort:
                        raise abort
                    return
                if status:
                    overflow.set()
                try:
                    chunks.put_nowait(bytes(data))
                except Full:
                    overflow.set()

            samples = 0
            peak_level = 0.0
            clipping_frames = 0
            peak_gain = 1.0
            if self.cancel.is_set():
                return
            if self.finish_capture.is_set():
                self.status.emit("TRANSCRIBING — stopped before microphone activation")
                self.transcript.emit("")
                return
            with sd.RawInputStream(
                device=device,
                samplerate=rate,
                blocksize=max(800, rate // 10),
                dtype="int16",
                channels=1,
                callback=capture,
            ):
                self.status.emit("LISTENING — microphone active" + ("; stay quiet for two-second calibration" if self.calibrate else ""))
                started = monotonic()
                last_chunk = started
                while not self.cancel.is_set() and monotonic() - started < (2 if self.calibrate else 30):
                    if self.finish_capture.is_set():
                        break
                    if overflow.is_set():
                        raise ValueError(
                            "Audio capture overflowed. Stop other audio tasks and retry."
                        )
                    try:
                        data = chunks.get(timeout=0.1)
                    except Empty:
                        if monotonic() - last_chunk > 5:
                            raise ValueError(
                                "Microphone stopped supplying audio. Reconnect it and press Push to talk again."
                            )
                        continue
                    last_chunk = monotonic()
                    processed, metrics = conditioner.process(data)
                    level = metrics["rms"]
                    self.input_metrics.emit(metrics)
                    clipping_frames += int(metrics["clipping"])
                    peak_gain = max(peak_gain, metrics["gain"])
                    samples += len(data) // 2
                    peak_level = max(peak_level, level)
                    self.level.emit(level)
                    if self.calibrate:
                        noise_levels.append(level)
                        if samples >= 2 * rate:
                            break
                        continue
                    self.partial.emit(decoder.accept(processed))
                    if conditioner.endpoint and decoder.parts:
                        break
            if self.cancel.is_set():
                self.status.emit("CANCELLED — microphone released; pending transcript discarded.")
                return
            self.status.emit("TRANSCRIBING — microphone off")
            if self.calibrate:
                self.calibrated.emit(calibration_floor(noise_levels))
                return
            # Closing the stream freezes this bounded queue before final recognition.
            while not chunks.empty():
                data = chunks.get_nowait()
                samples += len(data) // 2
                peak_level = max(peak_level, audio_level(data))
                processed, metrics = conditioner.process(data)
                clipping_frames += int(metrics["clipping"])
                peak_gain = max(peak_gain, metrics["gain"])
                decoder.accept(processed)
            text = decoder.finish()
            raw_text = decoder.raw
            if not self.cancel.is_set():
                self.measured.emit(
                    {
                        "samples": samples,
                        "sample_rate": rate,
                        "audio_seconds": round(samples / rate, 3),
                        "peak_rms": round(peak_level, 6),
                        "device": info.get("name", "Windows default microphone"),
                        "pcm": "mono signed 16-bit",
                        "stream_closed": True,
                        # Only a short adapted greeting belongs in measurement metadata.
                        # Standalone QA persists metrics; ordinary private speech must not leak there.
                        "raw_transcript": raw_text if text != raw_text else "",
                        "greeting_adapted": text != raw_text,
                        "max_gain": round(peak_gain, 3),
                        "clipping_frames": clipping_frames,
                        "noise_floor": round(conditioner.noise, 6),
                    }
                )
                self.transcript.emit(text)
        except Exception as exc:
            import logging

            logging.getLogger("nexis").warning("Voice unavailable (%s)", type(exc).__name__)
            if not self.cancel.is_set():
                if isinstance(exc, ValueError) and any(word in str(exc) for word in ("sample rate", "microphone session", "Calibration", "calibration", "Room is too loud")):
                    message = str(exc)
                else:
                    message = (
                        "Offline recognition failed during microphone/model processing "
                        f"({type(exc).__name__}). Check Windows microphone access for desktop apps, "
                        "the selected input and the offline model. No recording was saved."
                    )
                self.failed.emit(message)
        finally:
            self.level.emit(0.0)
            if owns_capture:
                _capture_lock.release()
