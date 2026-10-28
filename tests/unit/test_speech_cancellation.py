from nexis.platform.speech import SpeechService


def test_precancelled_speech_never_initializes_native_com(monkeypatch):
    import win32com.client
    calls = []
    monkeypatch.setattr(win32com.client, "Dispatch", lambda name: calls.append(name))
    service = SpeechService()
    service.cancel.set()
    service.run()
    assert not calls


def test_cancellation_during_sapi_creation_skips_device_enumeration(monkeypatch):
    import win32com.client
    calls = []
    service = SpeechService()
    def dispatch(name):
        calls.append(name)
        service.cancel.set()
        return object()
    monkeypatch.setattr(win32com.client, "Dispatch", dispatch)
    monkeypatch.setattr(service, "bind_output", lambda speaker: calls.append("must-not-enumerate"))
    service.run()
    assert calls == ["SAPI.SpVoice"]
