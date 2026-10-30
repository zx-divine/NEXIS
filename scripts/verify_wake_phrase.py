"""Actual Vosk wake spotting on SAPI file fixtures; never opens physical audio.

Synthetic results are not certification of human accuracy or room false-positive
rates. Generated fixture audio stays only in the new private evidence directory.
"""

import argparse
import json
from pathlib import Path
import sys
import wave
from threading import Event, Thread
from time import sleep
from types import SimpleNamespace
from unittest.mock import patch


def verify_worker_pipeline(output):
    from nexis.core.wake_word import WakeWordWorker

    def audio(name):
        with wave.open(str(output / name), 'rb') as source:
            return source.getframerate(), source.readframes(source.getnframes())

    rate, wake_pcm = audio('voice-0-0.wav')
    other_rate, command_pcm = audio('voice-0-3.wav')
    assert rate == other_rate
    _, negative_pcm = audio('voice-0-1.wav')
    rows = []
    for label, initial, expected in (('wake-command', wake_pcm, 'open notepad'),
                                      ('nonwake-command', negative_pcm, ''),
                                      ('permission-revoked', wake_pcm, '')):
        pcm = initial + bytes(rate * 4) + command_pcm + bytes(rate * 6)
        allowed, closed, stop = Event(), Event(), Event()
        allowed.set()
        worker = WakeWordWorker(str(Path(__file__).resolve().parents[1] / 'assets/models/vosk-model-small-en-us-0.15'), allowed=allowed.is_set)
        commands, errors, awakened = [], [], []
        worker.command.connect(commands.append)
        worker.failed.connect(errors.append)
        worker.awakened.connect(lambda: awakened.append(True))

        class FileInput:
            def __init__(self, **kwargs):
                self.callback = kwargs['callback']

            def __enter__(self):
                def feed():
                    for index, offset in enumerate(range(0, len(pcm), rate // 10 * 2)):
                        if stop.is_set():
                            return
                        if label == 'permission-revoked' and index == 3:
                            allowed.clear()
                        block = pcm[offset:offset + rate // 10 * 2]
                        self.callback(block, len(block) // 2, None, None)
                        sleep(.1)
                    sleep(.3)
                    worker.cancel.set()
                self.thread = Thread(target=feed, daemon=True)
                self.thread.start()
                return self

            def __exit__(self, *args):
                stop.set()
                self.thread.join(2)
                closed.set()

        fake_sd = SimpleNamespace(RawInputStream=FileInput, check_input_settings=lambda **kwargs: None, CallbackAbort=RuntimeError)
        with patch.dict(sys.modules, {'sounddevice': fake_sd}), patch('nexis.core.wake_word.default_input', return_value=(0, {'name': 'SAPI file fixture', 'default_samplerate': rate})):
            worker.run()
        actual = commands[-1] if commands else ''
        rows.append({'case': label, 'recognized_command': actual, 'expected': expected,
                     'wake_events': len(awakened), 'errors': errors,
                     'file_input_closed': closed.is_set(), 'physical_microphone_opened': False,
                     'pass': actual == expected and closed.is_set() and not errors})
    return rows


def main():
    root = Path(__file__).resolve().parents[1]
    sys.path[:0] = [str(root / name) for name in ('.dev-deps', '.provider-deps', '.dev-deps/win32', '.dev-deps/win32/lib', 'src')]
    import pythoncom
    import win32com.client
    from vosk import Model, KaldiRecognizer, SetLogLevel
    from nexis.core.wake_word import wake_detected

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--model', type=Path, default=root / 'assets/models/vosk-model-small-en-us-0.15')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    SetLogLevel(-1)
    model = Model(str(args.model))
    rows = []
    pythoncom.CoInitialize()
    try:
        voice = win32com.client.Dispatch('SAPI.SpVoice')
        voices = voice.GetVoices()
        for index in range(min(2, voices.Count)):
            voice.Voice = voices.Item(index)
            for count, phrase in enumerate(('Hey NEXIS', 'Hey Charlie', 'Hello NEXIS', 'Open notepad')):
                target = args.output / f'voice-{index}-{count}.wav'
                stream = win32com.client.Dispatch('SAPI.SpFileStream')
                stream.Open(str(target.resolve()), 3, False)
                try:
                    voice.AudioOutputStream = stream
                    voice.Speak(phrase, 0)
                finally:
                    stream.Close()
                with wave.open(str(target), 'rb') as audio:
                    rate = audio.getframerate()
                    assert audio.getnchannels() == 1 and audio.getsampwidth() == 2
                    pcm = audio.readframes(audio.getnframes()) + bytes(rate * 2 * 2)
                recognizer = KaldiRecognizer(model, rate, json.dumps(['hey nexis', '[unk]']))
                recognizer.SetWords(True)
                results = []
                for offset in range(0, len(pcm), rate // 10 * 2):
                    if recognizer.AcceptWaveform(pcm[offset:offset + rate // 10 * 2]):
                        results.append(json.loads(recognizer.Result()))
                results.append(json.loads(recognizer.FinalResult()))
                detected = any(wake_detected(value) for value in results)
                rows.append({'voice_index': index, 'synthetic_phrase': phrase, 'detected': detected,
                             'expected': phrase == 'Hey NEXIS', 'pass': detected == (phrase == 'Hey NEXIS'),
                             'recognizer_results': results})
    finally:
        voice = stream = voices = None
        pythoncom.CoUninitialize()
    report = {'status': 'PASS' if rows and all(row['pass'] for row in rows) else 'FAIL',
              'microphone_opened': False, 'speaker_played': False,
              'real_room_accuracy': 'NOT VERIFIED', 'samples': rows}
    report['worker_file_pipeline'] = verify_worker_pipeline(args.output)
    if not all(row['pass'] for row in report['worker_file_pipeline']):
        report['status'] = 'FAIL'
    (args.output / 'wake-phrase-results.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))
    return int(report['status'] != 'PASS')


if __name__ == '__main__':
    raise SystemExit(main())
