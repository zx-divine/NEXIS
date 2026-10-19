"""Fixed documented Windows operations. No shells, elevation or credential automation."""

import ctypes
from ctypes import wintypes
from contextlib import contextmanager
import os
from pathlib import Path
import platform
import shutil
import subprocess
from uuid import UUID

SETTINGS = {
    "settings": "",
    "display": "display",
    "wallpaper": "personalization-background",
    "themes": "themes",
    "sound": "sound",
    "audio_input": "sound",
    "audio_output": "sound",
    "microphone": "privacy-microphone",
    "bluetooth": "bluetooth",
    "wifi": "network-wifi",
    "network": "network-status",
    "battery": "batterysaver",
    "power": "powersleep",
    "storage": "storagesense",
    "default_apps": "defaultapps",
    "startup_apps": "startupapps",
    "notifications": "notifications",
    "date_time": "dateandtime",
    "language": "regionlanguage",
    "accessibility": "easeofaccess",
    "windows_update": "windowsupdate",
    "installed_programs": "appsfeatures",
    "printers": "printers",
    "security": "windowsdefender",
    "accounts": "yourinfo",
    "system_information": "about",
    "pin": "signinoptions",
    "password": "signinoptions",
    "hello": "signinoptions",
    "sign_in": "signinoptions",
    "recovery": "signinoptions",
    "account_recovery": "signinoptions",
    "system_recovery": "recovery",
}
PROTECTED_PAGES = {
    "pin",
    "password",
    "hello",
    "sign_in",
    "recovery",
    "account_recovery",
    "system_recovery",
    "security",
    "accounts",
}


def open_settings(page):
    if page not in SETTINGS:
        raise ValueError("This Windows settings page is not supported.")
    os.startfile("ms-settings:" + SETTINGS[page])
    return {
        "requested_page": page,
        "request_accepted": True,
        "setting_changed": False,
        "user_completion_required": page in PROTECTED_PAGES,
    }


def open_utility(name):
    base = Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32"
    commands = {
        "task_manager": [str(base / "Taskmgr.exe")],
        "device_manager": [str(base / "mmc.exe"), str(base / "devmgmt.msc")],
    }
    if name not in commands:
        raise ValueError("Unsupported Windows utility.")
    subprocess.Popen(commands[name], shell=False, close_fds=True)
    return {"request_accepted": True, "administrator_approval_bypassed": False}


def list_windows():
    import win32gui
    import win32process

    rows = []

    def collect(handle, _):
        if win32gui.IsWindowVisible(handle):
            title = win32gui.GetWindowText(handle)
            if title:
                rows.append(
                    {
                        "window_id": handle,
                        "title": title[:200],
                        "pid": win32process.GetWindowThreadProcessId(handle)[1],
                    }
                )

    win32gui.EnumWindows(collect, None)
    return rows[:100]


def change_window(identifier, action, cancel, expected_pid):
    import win32gui
    import win32con
    import win32process

    if not win32gui.IsWindow(identifier) or not win32gui.IsWindowVisible(identifier):
        raise ValueError("The selected window is no longer available. Refresh the window list.")
    if win32process.GetWindowThreadProcessId(identifier)[1] != expected_pid:
        raise ValueError(
            "Window identity changed. Refresh the window list; no action was performed."
        )
    if action == "focus":
        win32gui.ShowWindow(identifier, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(identifier)
        verified = win32gui.GetForegroundWindow() == identifier
    elif action == "minimize":
        win32gui.ShowWindow(identifier, win32con.SW_MINIMIZE)
        verified = bool(win32gui.IsIconic(identifier))
    elif action == "maximize":
        win32gui.ShowWindow(identifier, win32con.SW_MAXIMIZE)
        is_zoomed = ctypes.windll.user32.IsZoomed
        is_zoomed.argtypes = [wintypes.HWND]
        is_zoomed.restype = wintypes.BOOL
        verified = bool(is_zoomed(identifier))
    elif action == "close":
        win32gui.PostMessage(identifier, win32con.WM_CLOSE, 0, 0)
        for _ in range(25):
            if not win32gui.IsWindow(identifier) or cancel.wait(0.1):
                break
        verified = not win32gui.IsWindow(identifier)
    else:
        raise ValueError("Unsupported window operation.")
    return {
        "verified": verified,
        "operation": action,
        "message": "Window operation verified."
        if verified
        else "Windows did not confirm completion; an unsaved-data or protected-window prompt may need your action.",
    }


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]

    @classmethod
    def parse(cls, value):
        return cls.from_buffer_copy(UUID(value).bytes_le)


def com_call(pointer, index, argtypes, *args):
    table = ctypes.cast(pointer, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    function = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, *argtypes)(table[index])
    result = function(pointer, *args)
    if result < 0:
        raise OSError("Windows audio endpoint operation failed.")


@contextmanager
def volume_endpoint(capture=False):
    import pythoncom

    pythoncom.CoInitialize()
    enumerator, device, endpoint = ctypes.c_void_p(), ctypes.c_void_p(), ctypes.c_void_p()
    try:
        clsid = GUID.parse("BCDE0395-E52F-467C-8E3D-C4579291692E")
        iid = GUID.parse("A95664D2-9614-4F35-A746-DE8DB63617E6")
        create = ctypes.windll.ole32.CoCreateInstance
        create.argtypes = [
            ctypes.POINTER(GUID),
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(GUID),
            ctypes.POINTER(ctypes.c_void_p),
        ]
        create.restype = ctypes.c_long
        if create(ctypes.byref(clsid), None, 23, ctypes.byref(iid), ctypes.byref(enumerator)) < 0:
            raise OSError("Windows audio endpoint is unavailable.")
        com_call(
            enumerator,
            4,
            [ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_void_p)],
            1 if capture else 0,
            0,
            ctypes.byref(device),
        )
        iid = GUID.parse("5CDF2C82-841E-4546-9722-0CF74078229A")
        com_call(
            device,
            3,
            [
                ctypes.POINTER(GUID),
                wintypes.DWORD,
                ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_void_p),
            ],
            ctypes.byref(iid),
            23,
            None,
            ctypes.byref(endpoint),
        )
        yield endpoint
    finally:
        for pointer in (endpoint, device, enumerator):
            if pointer:
                table = ctypes.cast(
                    pointer, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))
                ).contents
                ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(table[2])(pointer)
        pythoncom.CoUninitialize()


def audio_volume(percent=None, muted=None, *, capture=False):
    with volume_endpoint(capture) as pointer:
        if percent is not None:
            if type(percent) is not int or not 0 <= percent <= 100:
                raise ValueError("Volume must be an integer from 0 to 100.")
            com_call(pointer, 7, [ctypes.c_float, ctypes.c_void_p], percent / 100, None)
        if muted is not None:
            if type(muted) is not bool:
                raise ValueError("Mute must be true or false.")
            com_call(pointer, 14, [wintypes.BOOL, ctypes.c_void_p], muted, None)
        level, mute = ctypes.c_float(), wintypes.BOOL()
        com_call(pointer, 9, [ctypes.POINTER(ctypes.c_float)], ctypes.byref(level))
        com_call(pointer, 15, [ctypes.POINTER(wintypes.BOOL)], ctypes.byref(mute))
        actual = round(level.value * 100)
        return {
            "percent": actual,
            "muted": bool(mute.value),
            "verified": (percent is None or abs(actual - percent) <= 1)
            and (muted is None or bool(mute.value) == muted),
        }


def system_information():
    class Power(ctypes.Structure):
        _fields_ = [
            ("ac", ctypes.c_ubyte),
            ("flags", ctypes.c_ubyte),
            ("percent", ctypes.c_ubyte),
            ("reserved", ctypes.c_ubyte),
            ("remaining", wintypes.DWORD),
            ("full", wintypes.DWORD),
        ]

    power = Power()
    available = bool(ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(power)))
    disk = shutil.disk_usage(Path(os.environ.get("SystemRoot", "C:/Windows")).anchor)
    return {
        "windows": platform.version(),
        "architecture": platform.machine(),
        "storage_free_bytes": disk.free,
        "storage_total_bytes": disk.total,
        "battery_percent": power.percent if available and power.percent <= 100 else None,
        "ac_connected": power.ac == 1 if available else None,
    }
