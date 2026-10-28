from threading import Event
from types import SimpleNamespace

import pytest

from nexis.core.permissions import Permissions
from nexis.core.router import Engine
from nexis.core.tools import ToolExecutor
from nexis.core.websites import resolve_website, website_command, website_url
from nexis.platform import website_launcher as launcher


@pytest.mark.parametrize(("source", "expected"), [
    ("example.com", "https://example.com"),
    ("github.com/path?q=x&y=2#section", "https://github.com/path?q=x&y=2#section"),
    ("HTTPS://EXAMPLE.COM:443/a", "https://example.com:443/a"),
    ("http://example.com/a", "http://example.com/a"),
    ("bücher.de/suche?q=rot", "https://xn--bcher-kva.de/suche?q=rot"),
    ("https://[::1]:8080/a", "https://[::1]:8080/a"),
    ("example.com:8080/long/" + "x" * 3000, "https://example.com:8080/long/" + "x" * 3000),
])
def test_normalized_web_destinations(source, expected):
    assert website_url(source) == expected


@pytest.mark.parametrize("source", [
    "javascript:alert(1)", "data:text/plain,test", "file:///C:/Windows/notepad.exe",
    "ftp://example.com", "mailto:user@example.com", "ms-settings:display",
    "https://user:password@example.com", "https://user@example.com", "https://example.com:",
    "https://example.com:99999", "https://-bad.example", "https://example..com",
    "https://a.example/\nrun", "https://example.com/%0d%0aInjected", "https://example.com/\x7f",
    "https://example.com/\u202eexe", "https://example.com\\@evil.example", "https://example.com/\"run",
    "//evil.example", "-incognito", "ambiguous", "example.com & calc.exe", "x" * 8193,
])
def test_reject_unsafe_or_ambiguous_destination(source):
    with pytest.raises(ValueError):
        website_url(source)


@pytest.mark.parametrize(("spoken", "command"), [
    ("NEXIS, open YouTube.", "open YouTube"),
    ("Hey NEXIS, open GitHub in Chrome.", "open GitHub in chrome"),
    ("Open Reddit in Brave.", "open Reddit in brave"),
    ("Open Gmail in Firefox.", "open Gmail in firefox"),
    ("Open youtube.com.", "open youtube.com"),
    ("Open https://github.com/path?q=one&two=2", "open https://github.com/path?q=one&two=2"),
    ("Open YouTube using my default browser.", "open YouTube"),
    ("Open Google in Microsoft Edge.", "open Google in edge"),
])
def test_single_natural_website_commands(spoken, command):
    assert website_command(spoken) == command


def test_no_domain_guessing_and_unfamiliar_or_http_requires_review():
    assert resolve_website("ambiguous") == (None, False)
    assert website_command("Open Notepad.") is None
    assert website_command("Open this website in Edge.") is None
    assert resolve_website("example.com")[1] is True
    assert resolve_website("http://github.com")[1] is True
    assert resolve_website("github.com")[1] is False


def test_explicit_browser_engine_and_tool_keep_choice_and_truthful_result(db, platform):
    calls = []
    platform.website = lambda target, **kwargs: calls.append((target, kwargs))
    result = Engine(db, platform).execute("open YouTube in Brave")
    assert result.ok and "not been independently verified" in result.message
    assert calls[-1][1]["browser"] == "brave"
    executor = ToolExecutor(db, ".", platform, lambda preview: True)
    result = executor.run({"tool": "website_open", "arguments": {"site": "github.com", "browser": "Firefox"}}, Event())
    assert result["request_accepted"] and result["loaded_page_verified"] is False
    assert calls[-1][1]["browser"] == "firefox"


def test_valid_site_automatic_and_optional_approval_cancellation_precedes_native_callback(db, platform):
    assert Engine(db, platform).execute("open example.com").ok
    assert platform.calls == [("website", "https://example.com")]
    platform.calls.clear()
    db.set_setting("confirm_low_risk", True)
    cancel = Event()
    def approval(preview):
        cancel.set()
        return True
    result = Engine(db, platform, Permissions(approval)).execute("open http://example.com", cancel)
    assert not result.ok and not platform.calls
    db.set_setting("access_permissions", {})
    assert not Engine(db, platform).execute("open github in Chrome").ok
    assert not platform.calls


def test_windows_default_uses_current_url_association_and_ignores_browser_environment(monkeypatch):
    calls = []
    monkeypatch.setenv("BROWSER", "malicious-command %s")
    monkeypatch.setattr(launcher.os, "startfile", lambda *args: calls.append(args))
    monkeypatch.setattr(launcher.subprocess, "Popen", lambda *args, **kw: pytest.fail("No command processor or explicit process for Windows default"))
    result = launcher.launch_website("github.com")
    assert calls == [("https://github.com", "open")]
    assert result["request_accepted"] and not result["loaded_page_verified"]
    assert not result["browser_process_started"]


def test_missing_browser_never_falls_back(monkeypatch):
    monkeypatch.setattr(launcher, "installed_browsers", lambda: [])
    monkeypatch.setattr(launcher.os, "startfile", lambda *args: pytest.fail("Silent fallback"))
    with pytest.raises(ValueError, match="default browser instead"):
        launcher.launch_website("github.com", "Brave")


def test_explicit_browser_uses_argument_array_and_cancels_after_discovery(monkeypatch):
    calls, cancel = [], Event()
    monkeypatch.setattr(launcher, "resolve_browser", lambda name: launcher.Browser(name, "C:/Apps/browser.exe"))
    monkeypatch.setattr(launcher, "verified_exe", lambda path: path)
    monkeypatch.setattr(launcher, "launch_risk", lambda path: launcher.Risk.LOW)
    monkeypatch.setattr(launcher.subprocess, "Popen", lambda args, **kwargs: calls.append((args, kwargs)) or SimpleNamespace(pid=123))
    target = "https://example.com/path?q=$(calc)&value=a;cmd"
    result = launcher.launch_website(target, "chrome", cancel)
    assert calls == [(["C:/Apps/browser.exe", target], {"shell": False, "close_fds": True})]
    assert result["browser_process_started"] and not result["loaded_page_verified"]
    calls.clear()
    def discovery(name):
        cancel.set()
        return launcher.Browser(name, "C:/Apps/browser.exe")
    monkeypatch.setattr(launcher, "resolve_browser", discovery)
    with pytest.raises(ValueError, match="cancelled"):
        launcher.launch_website(target, "chrome", cancel)
    assert not calls


def test_default_launch_failure_is_actionable_and_no_success(monkeypatch):
    def denied(*args):
        raise OSError("private system error")
    monkeypatch.setattr(launcher.os, "startfile", denied)
    with pytest.raises(ValueError, match="Default apps"):
        launcher.launch_website("github.com")


def test_registry_commands_never_supply_launch_arguments():
    assert launcher._registered_path('"C:\\Program Files\\Browser\\browser.exe" --flag "%1"') == "C:\\Program Files\\Browser\\browser.exe"
    assert launcher._registered_path("C:\\Program Files\\Browser\\browser.exe %1") == ""
    for text in ("cmd.exe /c launch", "powershell -c test", "x.exe\ncmd.exe"):
        assert launcher._registered_path(text) == ""
