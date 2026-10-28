import pytest

from nexis.platform.hotkeys import HotkeyRegistration, HOTKEYS, MOD_NOREPEAT


class API:
    def __init__(self):
        self.keys = {}
        self.blocked = set()
        self.calls = []

    def RegisterHotKey(self, hwnd, identifier, modifiers, key):
        self.calls.append((identifier, modifiers, key))
        if (modifiers, key) in self.blocked:
            return 0
        self.keys[identifier] = (modifiers, key)
        return 1

    def UnregisterHotKey(self, hwnd, identifier):
        self.keys.pop(identifier, None)
        return 1


def test_conflict_keeps_prior_registration_and_successful_rebind_releases_it():
    api = API()
    registration = HotkeyRegistration(api)
    assert registration.configure("Ctrl+Space").ok
    first = registration.identifier
    modifiers, key = HOTKEYS["Ctrl+Alt+Space"]
    api.blocked.add((modifiers | MOD_NOREPEAT, key))
    result = registration.configure("Ctrl+Alt+Space")
    assert not result.ok and result.active_chord == "Ctrl+Space"
    assert registration.identifier == first and len(api.keys) == 1
    assert "another app" in result.message
    api.blocked.clear()
    assert registration.configure("Ctrl+Alt+Space").ok
    assert first not in api.keys and len(api.keys) == 1
    assert registration.stop() and not api.keys


def test_repeated_enable_is_idempotent_and_disable_releases():
    api = API()
    registration = HotkeyRegistration(api)
    assert registration.configure("Ctrl+Space").ok
    assert registration.configure("Ctrl+Space").ok
    assert len(api.calls) == 1 and api.calls[0][1] & MOD_NOREPEAT
    assert registration.configure("Ctrl+Space", False).ok
    assert not api.keys and not registration.chord
    assert registration.stop()


@pytest.mark.parametrize("chord", ["Win+R", "Enter", "F12", "cmd.exe", ""])
def test_only_supported_shortcuts_are_accepted(chord, db):
    with pytest.raises(ValueError):
        HotkeyRegistration(API()).configure(chord)
    with pytest.raises(ValueError):
        db.set_setting("global_launcher_hotkey", chord)
