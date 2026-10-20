"""Bounded offline PCM conditioning. Never opens devices or discards pre-speech audio."""
from array import array
from collections import deque
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class InputOptions:
    sensitivity: int = 100
    noise_floor: float = 0.001
    end_silence_ms: int = 1400
    normalize: bool = True
    calibration_device: str = ""

    def __post_init__(self):
        if type(self.sensitivity) is not int or not 50 <= self.sensitivity <= 200:
            raise ValueError("Microphone sensitivity must be 50–200 percent.")
        if not math.isfinite(self.noise_floor) or not 0.00001 <= self.noise_floor <= 0.25:
            raise ValueError("Invalid microphone calibration.")
        if type(self.end_silence_ms) is not int or not 700 <= self.end_silence_ms <= 3000:
            raise ValueError("End-of-speech pause must be 700–3000 ms.")


def level_percent(rms):
    """A dBFS meter makes normal quiet speech visible without falsifying raw levels."""
    return round(max(0, min(100, (20 * math.log10(max(float(rms), 1e-5)) + 70) / 70 * 100)))


class SpeechActivity:
    """WebRTC VAD on 20 ms mono frames; unmodified PCM still goes to the recognizer.

    Native capture rates unsupported by VAD are linearly sampled for VAD only.
    Recognition keeps its original negotiated rate and all initial syllables.
    """
    def __init__(self, rate, sensitivity=100):
        import webrtcvad

        self.rate = rate
        self.vad = webrtcvad.Vad(0 if sensitivity >= 140 else 2 if sensitivity <= 70 else 1)
        self.pending = array("h")
        self.offset = 0.0
        self.step = rate / 16000

    def update(self, samples):
        if self.rate in {8000, 16000, 32000, 48000}:
            resampled, vad_rate = samples, self.rate
        else:
            vad_rate = 16000
            self.pending.extend(samples)
            resampled = array("h")
            while self.offset + 1 < len(self.pending):
                index = int(self.offset)
                fraction = self.offset - index
                resampled.append(round(self.pending[index] * (1 - fraction) + self.pending[index + 1] * fraction))
                self.offset += self.step
            consumed = min(int(self.offset), len(self.pending))
            del self.pending[:consumed]
            self.offset -= consumed
        # Keep incomplete VAD frames across callbacks, not across recording sessions.
        if not hasattr(self, "frames"):
            self.frames = bytearray()
        self.frames.extend(resampled.tobytes())
        decisions = []
        frame_bytes = vad_rate // 50 * 2
        while len(self.frames) >= frame_bytes:
            decisions.append(self.vad.is_speech(bytes(self.frames[:frame_bytes]), vad_rate))
            del self.frames[:frame_bytes]
        return any(decisions)


class AudioConditioner:
    def __init__(self, rate, options=None, activity=None):
        self.options = options or InputOptions()
        self.activity = activity or SpeechActivity(rate, self.options.sensitivity)
        self.noise = self.options.noise_floor
        self.background = deque(maxlen=50)
        self.gain = 1.0
        self.speech_seconds = 0.0
        self.silence_seconds = 0.0
        self.rate = rate
        self.clipped_frames = 0

    def process(self, data):
        if len(data) % 2:
            raise ValueError("Microphone returned incomplete 16-bit PCM.")
        samples = array("h", data)
        if not samples:
            return data, {"rms": 0.0, "peak": 0.0, "speech": False, "gain": self.gain, "noise": self.noise, "clipping": False}
        raw_rms = math.sqrt(sum(v * v for v in samples) / len(samples)) / 32768
        peak = max(abs(v) for v in samples) / 32768
        clipping = peak >= 0.98
        self.clipped_frames += int(clipping)
        voiced = self.activity.update(samples)
        duration = len(samples) / self.rate
        # VAD is advisory for gain/endpoint, never a gate that throws away quiet speech.
        if not voiced:
            self.background.append(raw_rms)
            ordered = sorted(self.background)
            estimate = ordered[len(ordered) // 4]
            self.noise = max(0.00001, min(0.25, 0.9 * self.noise + 0.1 * estimate))
            self.silence_seconds += duration
        else:
            self.speech_seconds += duration
            self.silence_seconds = 0.0
        target = 1.0
        if self.options.normalize and voiced and raw_rms > max(0.0001, self.noise * 1.6):
            target = min(4.0, max(1.0, 0.035 / max(raw_rms, 1e-5) * self.options.sensitivity / 100))
        # Never boost noise-only frames. Limit every frame by its actual peak.
        self.gain = max(1.0, min(target, 0.88 / max(peak, 1e-5))) if target > 1 else 1.0
        if self.gain > 1:
            processed = array("h", (max(-32768, min(32767, round(v * self.gain))) for v in samples)).tobytes()
        else:
            processed = data
        return processed, {"rms": raw_rms, "peak": peak, "speech": voiced, "gain": self.gain,
                           "noise": self.noise, "clipping": clipping}

    @property
    def endpoint(self):
        return self.speech_seconds >= 0.12 and self.silence_seconds >= self.options.end_silence_ms / 1000


def calibration_floor(levels):
    """Explicit quiet-room calibration; reject invalid/device-disconnected samples."""
    valid = sorted(float(v) for v in levels if math.isfinite(v) and 0 <= v <= 1)
    if len(valid) < 5:
        raise ValueError("Calibration needs at least half a second of microphone audio.")
    floor = valid[len(valid) * 3 // 4]
    if floor > 0.08:
        raise ValueError("Room is too loud for calibration. Stay quiet, reduce background noise and retry.")
    return max(0.00001, floor)


def input_options(db):
    return InputOptions(
        sensitivity=db.setting("mic_sensitivity"), noise_floor=db.setting("mic_noise_floor"),
        end_silence_ms=db.setting("mic_end_silence_ms"), normalize=db.setting("mic_normalize"),
        calibration_device=db.setting("mic_calibration_device"),
    )


def greeting_recognizer(model, factory, rate):
    """A separate contextual decoder; never replace the unrestricted recognizer."""
    finder = getattr(model, "vosk_model_find_word", None)
    if not finder or any(finder(word) < 0 for word in ("hi", "hello", "hey", "nexis")):
        return None
    import json

    try:
        return factory(model, rate, json.dumps(["hi nexis", "hello nexis", "hey nexis", "[unk]"]))
    except Exception:
        # Static graphs or older engines may not support grammar changes.
        # Optional contextual decoding must not disable the unrestricted engine.
        return None


def contextual_greeting(raw, hinted):
    """Accept only exact assistant greetings supported by both decoders.

    Never turn 'hi mate' or arbitrary mentions of Nexus into the brand name.
    Original transcript remains in in-memory diagnostics for review.
    """
    plain, evidence = raw.strip().casefold().split(), hinted.strip().casefold().split()
    if len(plain) == 2 and plain[0] in {"hi", "hello", "hey"} and plain[1] in {"nexis", "nexus"}:
        if evidence == [plain[0], "nexis"]:
            return plain[0].capitalize() + " NEXIS"
    return raw
