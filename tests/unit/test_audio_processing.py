"""Deterministic PCM tests; no microphone or speaker is opened."""
from array import array
import math

import pytest

from nexis.core.audio import AudioConditioner, InputOptions, SpeechActivity, calibration_floor, contextual_greeting, level_percent


class Activity:
    def __init__(self, speech):
        self.speech = speech

    def update(self, samples):
        return self.speech


def tone(amplitude=200, rate=16000):
    return array("h", (round(amplitude * math.sin(2 * math.pi * 220 * i / rate)) for i in range(rate // 10))).tobytes()


def test_quiet_speech_has_bounded_gain_preserves_samples_and_headroom():
    data = tone()
    output, metrics = AudioConditioner(16000, activity=Activity(True)).process(data)
    assert len(output) == len(data)
    assert 1 < metrics["gain"] <= 4
    assert max(abs(x) for x in array("h", output)) < 32768 * 0.89
    assert not metrics["clipping"]


def test_noise_only_and_disabled_normalization_are_not_amplified():
    data = tone()
    output, metrics = AudioConditioner(16000, activity=Activity(False)).process(data)
    assert output == data and metrics["gain"] == 1
    output, metrics = AudioConditioner(16000, InputOptions(normalize=False), Activity(True)).process(data)
    assert output == data and metrics["gain"] == 1


def test_clipping_is_reported_without_wrapping_or_fake_repair():
    data = array("h", [32767, -32768] * 800).tobytes()
    output, metrics = AudioConditioner(16000, activity=Activity(True)).process(data)
    assert output == data and metrics["clipping"] and metrics["gain"] == 1


def test_conversational_pause_uses_hangover_and_keeps_initial_samples():
    activity = Activity(True)
    processor = AudioConditioner(16000, activity=activity)
    data = tone()
    assert len(processor.process(data)[0]) == len(data)
    processor.process(data)
    activity.speech = False
    for _ in range(6):
        processor.process(bytes(3200))
    assert not processor.endpoint
    for _ in range(9):
        processor.process(bytes(3200))
    assert processor.endpoint


@pytest.mark.parametrize("rate", [8000, 16000, 32000, 44100, 48000, 192000])
def test_real_vad_accepts_negotiated_rates_and_bounds_pending_frames(rate):
    vad = SpeechActivity(rate)
    for _ in range(12):
        assert vad.update(array("h", bytes(rate // 10 * 2))) is False
    assert len(vad.pending) <= 2
    assert len(vad.frames) < (rate // 50 * 2 if rate in {8000, 16000, 32000, 48000} else 640)


def test_calibration_validates_noise_and_never_guesses_from_missing_audio():
    assert calibration_floor([0.002] * 20) == 0.002
    with pytest.raises(ValueError, match="too loud"):
        calibration_floor([0.2] * 20)
    with pytest.raises(ValueError, match="half a second"):
        calibration_floor([float("nan"), 0.01])
    assert level_percent(0.005) > 30 and level_percent(0) == 0


@pytest.mark.parametrize("values", [{"sensitivity": 201}, {"noise_floor": float("nan")}, {"end_silence_ms": 400}])
def test_invalid_options_are_rejected(values):
    with pytest.raises(ValueError):
        InputOptions(**values)


@pytest.mark.parametrize("raw,hint,expected", [
    ("hi nexus", "hi nexis", "Hi NEXIS"),
    ("hi nexis", "hi nexis", "Hi NEXIS"),
    ("hello nexus", "hello nexis", "Hello NEXIS"),
    ("hi mate", "hi nexis", "hi mate"),
    ("tell me about nexus", "hi nexis", "tell me about nexus"),
    ("hi nexus", "[unk]", "hi nexus"),
    ("nexus", "hi nexis", "nexus"),
    ("नमस्ते", "hi nexis", "नमस्ते"),
])
def test_brand_adaptation_is_contextual_and_does_not_replace_unrelated_words(raw, hint, expected):
    assert contextual_greeting(raw, hint) == expected


def test_partial_pcm_is_rejected_and_malformed_settings_recover(db):
    with pytest.raises(ValueError):
        AudioConditioner(16000, activity=Activity(True)).process(b"x")
    db.execute("INSERT OR REPLACE INTO settings VALUES (?,?)", ("mic_noise_floor", "NaN"))
    db.execute("INSERT OR REPLACE INTO settings VALUES (?,?)", ("mic_sensitivity", "9000"))
    assert db.setting("mic_noise_floor") == 0.001
    assert db.setting("mic_sensitivity") == 100
