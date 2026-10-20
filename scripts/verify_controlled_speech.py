"""Native Windows SAPI-to-file → shared offline STT tests. No hardware capture/playback.

Use an output directory argument for local evidence. Generated audio stays in a
temporary directory and is removed. These are synthetic, not human accuracy tests.
"""
from array import array
import json
from pathlib import Path
import random
import sys
import tempfile
from time import perf_counter
import wave


def verify(output):
    from nexis.core.audio import AudioConditioner
    from nexis.core.recognition import TranscriptDecoder
    import pythoncom
    import win32com.client
    from vosk import Model, KaldiRecognizer, SetLogLevel

    root = Path(__file__).resolve().parents[1]
    SetLogLevel(-1)
    model = Model(str(root / "assets/models/vosk-model-small-en-us-0.15"))
    rows = []

    def decode(pcm, rate):
        decoder = TranscriptDecoder(model, KaldiRecognizer, rate)
        conditioner = AudioConditioner(rate)
        started = perf_counter()
        for offset in range(0, len(pcm), rate // 10 * 2):
            data, _ = conditioner.process(pcm[offset:offset + rate // 10 * 2])
            decoder.accept(data)
        return decoder.finish(), decoder.raw, round(perf_counter() - started, 3)

    pythoncom.CoInitialize()
    speaker = stream = tokens = None
    try:
        speaker = win32com.client.Dispatch("SAPI.SpVoice")
        tokens = speaker.GetVoices()
        if not tokens.Count:
            raise RuntimeError("No Windows SAPI voice; synthetic verification NOT VERIFIED")
        with tempfile.TemporaryDirectory(prefix="nexis-controlled-speech-") as temporary:
            for voice in range(min(2, tokens.Count)):
                speaker.Voice = tokens.Item(voice)
                for phrase in ("Hi NEXIS", "Hi mate", "Open calculator"):
                    target = Path(temporary) / "speech.wav"
                    stream = win32com.client.Dispatch("SAPI.SpFileStream")
                    stream.Open(str(target), 3, False)
                    speaker.AudioOutputStream = stream
                    speaker.Speak(phrase, 0)
                    stream.Close()
                    stream = None
                    with wave.open(str(target), "rb") as audio:
                        rate = audio.getframerate()
                        assert audio.getnchannels() == 1 and audio.getsampwidth() == 2
                        original = array("h", audio.readframes(audio.getnframes()))
                    for amplitude in (1.0, 0.1):
                        pcm = array("h", (round(v * amplitude) for v in original)).tobytes()
                        text, raw, seconds = decode(pcm, rate)
                        expected = "Hi NEXIS" if phrase == "Hi NEXIS" else phrase.lower()
                        rows.append({"voice_index": voice, "spoken": phrase, "amplitude_scale": amplitude,
                                     "recognized": text, "raw": raw, "seconds": seconds,
                                     "expected": expected, "pass": text == expected})
            rng = random.Random(42)
            noise = array("h", (round(rng.gauss(0, 30)) for _ in range(32000))).tobytes()
            text, raw, seconds = decode(noise, 16000)
            rows.append({"spoken": "noise only", "recognized": text, "raw": raw, "seconds": seconds,
                         "expected": "", "pass": text == ""})
    finally:
        if stream is not None:
            stream.Close()
        speaker = stream = tokens = None
        pythoncom.CoUninitialize()
    report = {"audio_source": "Windows SAPI synthetic fixtures and seeded noise; not human speech",
              "microphone_opened": False, "speaker_played": False, "audio_saved": False,
              "samples": rows, "passed": sum(row["pass"] for row in rows),
              "failed": sum(not row["pass"] for row in rows), "real_hardware": "NOT VERIFIED",
              "Hindi_Hinglish": "NOT VERIFIED: no compatible verified model/representative human samples in this run"}
    output.mkdir(parents=True, exist_ok=True)
    (output / "controlled-speech.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 1 if report["failed"] else 0


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    sys.path[:0] = [str(root / name) for name in (".dev-deps", ".provider-deps", ".dev-deps/win32", ".dev-deps/win32/lib", "src")]
    raise SystemExit(verify(Path(sys.argv[1]) if len(sys.argv) > 1 else root / ".verification-launch-v1"))
