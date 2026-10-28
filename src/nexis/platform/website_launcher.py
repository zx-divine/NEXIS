"""Windows website launches without shell commands or implicit browser substitution."""

from dataclasses import dataclass
import os
from pathlib import Path
import re
import subprocess
import sys

from nexis.core.launch_policy import launch_risk
from nexis.core.results import Risk
from nexis.core.websites import website_url
from nexis.platform.discovery import verified_exe


ALIASES = {
    "edge": "edge", "microsoft edge": "edge", "chrome": "chrome", "google chrome": "chrome",
    "firefox": "firefox", "mozilla firefox": "firefox", "brave": "brave", "opera": "opera",
    "opera gx": "opera gx", "vivaldi": "vivaldi",
    "opera stable": "opera", "opera gx stable": "opera gx",
}
EXECUTABLES = {"edge": "msedge.exe", "chrome": "chrome.exe", "firefox": "firefox.exe",
               "brave": "brave.exe", "opera": "opera.exe", "opera gx": "opera.exe",
               "vivaldi": "vivaldi.exe"}


@dataclass(frozen=True)
class Browser:
    name: str
    path: str


def browser_name(value):
    if not isinstance(value, str) or len(value) > 100:
        raise ValueError("Choose an installed browser by its registered name.")
    value = " ".join(value.strip().casefold().split())
    if value in {"", "default", "my default browser", "default browser"}:
        return "default"
    if not re.fullmatch(r"[\w .()-]{1,100}", value):
        raise ValueError("Choose an installed browser by name, not a path or command.")
    return ALIASES.get(value, value)


def _registered_path(command):
    # Never reuse registry command arguments, even when they look harmless.
    match = re.fullmatch(r'"([^"\r\n]+\.exe)"(?:\s+[^\r\n]*)?', command.strip(), re.I)
    if match:
        return match[1]
    # Unquoted paths with spaces and arguments are ambiguous and are rejected.
    if re.fullmatch(r'[^\s"\r\n]+\.exe', command.strip(), re.I):
        return command.strip()
    return ""


def installed_browsers():
    """Read App Paths and registered browser clients; never search cwd or PATH."""
    if sys.platform != "win32":
        return []
    import winreg

    found = {}

    def add(label, candidate):
        try:
            path = verified_exe(candidate)
            # Reuse the established installed-location/elevation policy.
            if launch_risk(path) != Risk.LOW:
                return
            label = browser_name(label)
            found.setdefault(label, Browser(label, path))
        except (ValueError, OSError, TypeError):
            pass

    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
            for label, filename in EXECUTABLES.items():
                try:
                    with winreg.OpenKey(hive, "Software\\Microsoft\\Windows\\CurrentVersion\\App Paths\\" + filename,
                                        0, winreg.KEY_READ | view) as entry:
                        path = winreg.QueryValueEx(entry, "")[0]
                    if isinstance(path, str):
                        expanded = os.path.expandvars(path.strip().strip('"'))
                        if Path(expanded).name.casefold() == filename and (label != "opera gx" or "gx" in expanded.casefold()):
                            add(label, expanded)
                except OSError:
                    pass
            try:
                with winreg.OpenKey(hive, r"Software\Clients\StartMenuInternet", 0, winreg.KEY_READ | view) as clients:
                    for index in range(min(winreg.QueryInfoKey(clients)[0], 64)):
                        try:
                            child = winreg.EnumKey(clients, index)
                            with winreg.OpenKey(clients, child) as entry:
                                label = winreg.QueryValueEx(entry, "")[0]
                            with winreg.OpenKey(clients, child + r"\shell\open\command") as entry:
                                command = winreg.QueryValueEx(entry, "")[0]
                            candidate = _registered_path(command) if isinstance(command, str) else ""
                            if candidate:
                                add(label, os.path.expandvars(candidate))
                        except (OSError, ValueError, TypeError):
                            continue
            except OSError:
                pass
    return list(found.values())


def resolve_browser(request):
    wanted = browser_name(request)
    matches = [row for row in installed_browsers() if browser_name(row.name) == wanted]
    if not matches:
        raise ValueError(f"{wanted.title()} is not installed or cannot be safely found. You can explicitly choose your default browser instead. No other browser was opened.")
    paths = {row.path.casefold() for row in matches}
    if len(paths) != 1:
        raise ValueError("Multiple browser installations match. Choose a distinct registered browser name.")
    return matches[0]


def launch_website(target, browser="default", cancel=None):
    target, chosen = website_url(target), browser_name(browser)
    if sys.platform != "win32":
        raise OSError("Website opening requires Windows.")
    selected = resolve_browser(chosen) if chosen != "default" else None
    if cancel and cancel.is_set():
        raise ValueError("Website launch cancelled before submission.")
    if selected:
        path = verified_exe(selected.path)
        if launch_risk(path) != Risk.LOW:
            raise ValueError("Browser installation changed or requires elevation; launch cancelled.")
        if cancel and cancel.is_set():
            raise ValueError("Website launch cancelled before submission.")
        try:
            process = subprocess.Popen([path, target], shell=False, close_fds=True)
        except OSError:
            raise ValueError("The requested browser could not start. Retry or explicitly choose the default browser.") from None
        return {"request_accepted": True, "browser_process_started": True, "pid": process.pid,
                "browser": chosen, "loaded_page_verified": False}
    # os.startfile invokes ShellExecute on Windows' current URL association and
    # does not use Python's BROWSER environment variable or a command processor.
    try:
        os.startfile(target, "open")
    except OSError:
        raise ValueError("Windows could not submit the URL to its default browser. Check Default apps and retry.") from None
    return {"request_accepted": True, "browser_process_started": None,
            "browser": "Windows default", "loaded_page_verified": False}
