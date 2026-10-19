"""Native decoder/PCM compatibility only; never captures speech or proves accuracy."""
import json
from pathlib import Path
import site
import sys

ROOT = Path(__file__).resolve().parents[1]
site.addsitedir(str(ROOT / ".dev-deps"))
sys.path[:0] = [str(ROOT / ".provider-deps"), str(ROOT / ".dev-deps"), str(ROOT / "src")]
from nexis.core.voice import capture_rates  # noqa: E402
from vosk import Model, KaldiRecognizer, SetLogLevel  # noqa: E402
SetLogLevel(-1)
model = Model(str(ROOT / "assets/models/vosk-model-small-en-us-0.15"))
checks = {}
for rate in (8000, 16000, 44100, 48000):
    try:
        recognizer = KaldiRecognizer(model, rate)
        recognizer.AcceptWaveform(bytes(rate // 5 * 2))
        result = json.loads(recognizer.FinalResult())
        checks[str(rate)] = {"pcm_decoder": "PASS", "text_empty_expected": result.get("text", "") == ""}
    except Exception as error:
        checks[str(rate)] = {"pcm_decoder": "FAIL", "error_type": type(error).__name__}
selected = capture_rates(ROOT / "assets/models/vosk-model-small-en-us-0.15", 8000)[0]
check = KaldiRecognizer(model, selected)
check.AcceptWaveform(bytes(selected // 5 * 2))
report = {"rates": checks, "narrowband_default_selected_rate": selected, "selected_rate_decodes": True, "microphone_opened": False, "input": "synthetic silence",
          "real_speech_recognition": "NOT VERIFIED"}
(ROOT / "docs/installer-overhaul/decoder-rates.json").write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))

passed = all(checks[str(rate)]["pcm_decoder"] == "PASS" for rate in (16000, 44100, 48000))
raise SystemExit(0 if passed and selected == 16000 else 1)
