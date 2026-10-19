"""Bounded Windows registration discovery. Never executes shortcut metadata."""

import ctypes
import hashlib
import os
from pathlib import Path
import re
import struct
import sys
import unicodedata
import uuid
from dataclasses import dataclass, asdict

from nexis.utils.validation import executable, BLOCKED


def folded(text):
    return unicodedata.normalize("NFKC", text).strip().casefold()


def known_folder(identifier):
    guid = ctypes.create_string_buffer(uuid.UUID(identifier).bytes_le)
    result = ctypes.c_wchar_p()
    api = ctypes.windll.shell32.SHGetKnownFolderPath
    api.argtypes = [
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_wchar_p),
    ]
    api.restype = ctypes.c_long
    if api(guid, 0, None, ctypes.byref(result)) != 0:
        raise OSError("Windows folder is unavailable")
    try:
        return Path(result.value)
    finally:
        free = ctypes.windll.ole32.CoTaskMemFree
        free.argtypes = [ctypes.c_void_p]
        free(ctypes.cast(result, ctypes.c_void_p))


def verified_exe(target):
    path = executable(os.path.expandvars(str(target)))
    if path.stem.casefold() in BLOCKED or re.search(
        r"unins|uninstall|setup|installer", path.stem, re.I
    ):
        raise ValueError("Administrative launch target excluded")
    with path.open("rb") as stream:
        if stream.read(2) != b"MZ":
            raise ValueError("Not a Windows executable")
        stream.seek(60)
        offset = struct.unpack("<I", stream.read(4))[0]
        if offset > 16 * 1024 * 1024:
            raise ValueError("Invalid executable header")
        stream.seek(offset)
        if stream.read(4) != b"PE\0\0":
            raise ValueError("Invalid executable header")
    return str(path)


def valid_app_id(value):
    return (
        isinstance(value, str)
        and re.fullmatch(r"[A-Za-z0-9.\-_]+_[A-Za-z0-9]+![A-Za-z0-9.\-_]+", value) is not None
    )


def shortcut_targets(target, arguments):
    """Resolve a narrow Squirrel launcher format to its actual installed EXE.

    Arguments are never passed to execution. All other argument-bearing links
    are skipped rather than interpreted as commands.
    """
    if not arguments.strip():
        return [target]
    match = re.fullmatch(r'--processStart\s+"?([A-Za-z0-9_.-]+\.exe)"?', arguments.strip())
    base = Path(target)
    if base.name.casefold() != "update.exe" or not match or not base.is_absolute():
        return []
    paths = sorted(base.parent.glob("app-*"), reverse=True)[:50]
    for directory in paths:
        candidate = directory / match[1]
        if (
            not directory.is_symlink()
            and not getattr(directory, "is_junction", lambda: False)()
            and candidate.is_file()
        ):
            return [str(candidate)]
    return []


@dataclass(frozen=True)
class Application:
    id: str
    name: str
    target: str
    kind: str
    source: str
    available: bool = True

    @classmethod
    def create(cls, name, target, kind, source):
        if not name.strip() or len(name) > 200 or any(ord(c) < 32 for c in name):
            raise ValueError("Invalid application name")
        if kind == "exe":
            target = verified_exe(target)
        elif kind != "appx" or not valid_app_id(target):
            raise ValueError("Invalid registered application")
        identity = hashlib.sha256((kind + ":" + target.casefold()).encode()).hexdigest()[:24]
        return cls(identity, name.strip(), target, kind, source)


def deduplicate(candidates):
    found = {}
    for app in candidates:
        found.setdefault(app.id, app)
    return sorted(found.values(), key=lambda app: folded(app.name))


def discover(cancel, approved=()):
    if sys.platform != "win32":
        return [], ["Windows application discovery is unavailable on this platform."]
    import pythoncom
    import win32com.client
    import winreg

    found, issues = [], []

    def add(name, target, kind, source):
        if cancel.is_set():
            return
        try:
            found.append(Application.create(name, target, kind, source))
        except (ValueError, OSError, struct.error):
            pass

    pythoncom.CoInitialize()
    try:
        shell = win32com.client.Dispatch("WScript.Shell")
        for identifier, label in (
            ("A77F5D77-2E2B-44C3-A6A2-ABA601054A51", "User Start Menu"),
            ("0139D44E-6AFE-49F2-8690-3DAFCAE6FFB8", "Common Start Menu"),
        ):
            try:
                base = known_folder(identifier)
                visited = 0
                for directory, folders, files in os.walk(base, followlinks=False):
                    folders[:] = [
                        f
                        for f in folders
                        if not getattr(Path(directory) / f, "is_junction", lambda: False)()
                        and not (Path(directory) / f).is_symlink()
                    ]
                    if len(Path(directory).relative_to(base).parts) > 8:
                        folders.clear()
                    for filename in files:
                        visited += 1
                        if cancel.is_set() or visited > 5000:
                            break
                        path = Path(directory) / filename
                        if path.suffix.casefold() != ".lnk" or path.is_symlink():
                            continue
                        try:
                            link = shell.CreateShortcut(str(path))
                            # Never execute .lnk files or carry their arguments into a process.
                            for resolved in shortcut_targets(link.TargetPath, link.Arguments):
                                add(path.stem, resolved, "exe", label)
                        except Exception:
                            continue
                    if cancel.is_set() or visited > 5000:
                        break
            except OSError:
                issues.append(label + " could not be read.")
        for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
                for registry_path, source in (
                    (r"Software\Microsoft\Windows\CurrentVersion\App Paths", "App Paths"),
                    (
                        r"Software\Microsoft\Windows\CurrentVersion\Uninstall",
                        "Installation metadata",
                    ),
                ):
                    try:
                        with winreg.OpenKey(hive, registry_path, 0, winreg.KEY_READ | view) as key:
                            for index in range(min(winreg.QueryInfoKey(key)[0], 3000)):
                                if cancel.is_set():
                                    break
                                try:
                                    child = winreg.EnumKey(key, index)
                                    with winreg.OpenKey(key, child) as entry:
                                        if source == "App Paths":
                                            target = (
                                                winreg.QueryValueEx(entry, "")[0].strip().strip('"')
                                            )
                                            add(Path(child).stem, target, "exe", source)
                                        else:
                                            display = winreg.QueryValueEx(entry, "DisplayName")[0]
                                            icon = winreg.QueryValueEx(entry, "DisplayIcon")[0]
                                            target = (
                                                re.sub(r",\s*-?\d+$", "", icon).strip().strip('"')
                                            )
                                            add(display, target, "exe", source)
                                except (OSError, TypeError, ValueError):
                                    continue
                    except OSError:
                        continue
        try:
            apps = win32com.client.Dispatch("Shell.Application").NameSpace("shell:AppsFolder")
            if apps is not None:
                for index, item in enumerate(apps.Items()):
                    if cancel.is_set() or index >= 3000:
                        break
                    app_id = item.ExtendedProperty("System.AppUserModel.ID")
                    if valid_app_id(app_id):
                        add(item.Name, app_id, "appx", "Windows AppsFolder")
        except Exception:
            issues.append("Some registered Windows applications could not be read.")
        # Execution aliases are inspected only in the designated Windows directory.
        aliases = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft/WindowsApps"
        if aliases.is_absolute() and aliases.is_dir():
            for index, path in enumerate(aliases.glob("*.exe")):
                if cancel.is_set() or index >= 500:
                    break
                add(path.stem, str(path), "exe", "Windows execution alias")
        for row in approved:
            if row["kind"] == "application":
                add(row["name"], row["target"], "exe", "User approved")
    finally:
        pythoncom.CoUninitialize()
    return [asdict(app) for app in deduplicate(found)], issues


def current_app_ids():
    import pythoncom
    import win32com.client

    pythoncom.CoInitialize()
    try:
        folder = win32com.client.Dispatch("Shell.Application").NameSpace("shell:AppsFolder")
        return (
            {str(item.ExtendedProperty("System.AppUserModel.ID")) for item in folder.Items()}
            if folder
            else set()
        )
    finally:
        pythoncom.CoUninitialize()


def launch_registered(app_id):
    if not valid_app_id(app_id) or app_id not in current_app_ids():
        raise ValueError("Registered application is no longer available. Rescan applications.")
    # Fixed Explorer command, one validated registered identifier, no shell evaluation.
    import subprocess

    explorer = Path(os.environ.get("SystemRoot", "C:/Windows")) / "explorer.exe"
    subprocess.Popen([str(explorer), "shell:AppsFolder\\" + app_id], shell=False, close_fds=True)
