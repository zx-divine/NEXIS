"""Shared unrestricted decoder and bounded contextual assistant-greeting decoder."""
import json

from nexis.core.audio import contextual_greeting, greeting_recognizer


class TranscriptDecoder:
    def __init__(self, model, factory, rate):
        self.main = factory(model, rate)
        self.hint = greeting_recognizer(model, factory, rate)
        self.rate, self.samples = rate, 0
        self.parts, self.hints = [], []
        self.raw = ""

    def accept(self, data):
        self.samples += len(data) // 2
        if self.hint and self.samples <= self.rate * 4:
            if self.hint.AcceptWaveform(data):
                self.hints.append(json.loads(self.hint.Result()).get("text", ""))
        if self.main.AcceptWaveform(data):
            text = json.loads(self.main.Result()).get("text", "")
            if text:
                self.parts.append(text)
            return ""
        return json.loads(self.main.PartialResult()).get("partial", "")

    def finish(self):
        text = json.loads(self.main.FinalResult()).get("text", "")
        if text:
            self.parts.append(text)
        if self.hint:
            self.hints.append(json.loads(self.hint.FinalResult()).get("text", ""))
        self.raw = " ".join(self.parts).strip()
        return contextual_greeting(self.raw, " ".join(self.hints).strip())
