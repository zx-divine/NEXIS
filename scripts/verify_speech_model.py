"""Explicitly consented real-model verification; never opens an audio device."""

import json
from pathlib import Path
import site
import sys
from threading import Event

root = Path(__file__).resolve().parents[1]
site.addsitedir(str(root / ".dev-deps"))
sys.path.insert(0, str(root / "src"))
from nexis.core.models import MODEL, install_model  # noqa: E402

if "--consent" not in sys.argv:
    raise SystemExit("Explicit user consent is required for the 41.2 MB verification download.")
destination = root / ".verification-v13-model-real"
destination.mkdir(parents=True, exist_ok=True)
last = ""


def progress(message):
    global last
    if message != last:
        print(message, flush=True)
        last = message


path = install_model(destination, Event(), progress, consent=True)
from vosk import Model, KaldiRecognizer, SetLogLevel  # noqa: E402

SetLogLevel(-1)
model = Model(path)
recognizer = KaldiRecognizer(model, 16000)
recognizer.AcceptWaveform(b"\0" * 32000)
result = json.loads(recognizer.FinalResult())
assert not result.get("text"), "Unexpected transcript for synthetic silence"
report = {
    "approved_source": MODEL["url"],
    "size": MODEL["size"],
    "sha256": MODEL["sha256"],
    "checksum_verified_by_installer": True,
    "safe_extraction_completed": True,
    "vosk_model_initialized": True,
    "offline_silence_processed": True,
    "model_directory": path,
    "microphone_opened": False,
    "real_speech_accuracy": "NOT VERIFIED",
    "physical_device_switching": "NOT VERIFIED",
}
(root / "docs/v13-model-verification.json").write_text(
    json.dumps(report, indent=2), encoding="utf-8"
)
print(json.dumps(report, indent=2), flush=True)
