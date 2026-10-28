"""Offline Windows Authenticode verification; no publisher names or network probes."""
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
from uuid import UUID


def trusted_signature(path):
    if os.name != "nt":
        return False

    class FileInfo(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("path", wintypes.LPCWSTR),
                    ("file", wintypes.HANDLE), ("subject", ctypes.c_void_p)]

    class TrustData(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("policy", ctypes.c_void_p),
                    ("sip", ctypes.c_void_p), ("ui", wintypes.DWORD),
                    ("revocation", wintypes.DWORD), ("choice", wintypes.DWORD),
                    ("file_info", ctypes.POINTER(FileInfo)), ("state_action", wintypes.DWORD),
                    ("state", wintypes.HANDLE), ("url", wintypes.LPCWSTR),
                    ("flags", wintypes.DWORD), ("context", wintypes.DWORD),
                    ("signature_settings", ctypes.c_void_p)]

    info = FileInfo(ctypes.sizeof(FileInfo), str(Path(path).resolve(strict=True)), None, None)
    # UI_NONE, CHOICE_FILE, STATEACTION_IGNORE: no retained handles or certificate UI.
    data = TrustData()
    data.size, data.ui, data.choice = ctypes.sizeof(TrustData), 2, 1
    data.file_info = ctypes.pointer(info)
    # Follow local Windows trust policy, disallow network retrieval and obsolete hashes.
    data.flags = 0x1000 | 0x2000
    action = (ctypes.c_ubyte * 16).from_buffer_copy(UUID("00AAC56B-CD44-11D0-8CC2-00C04FC295EE").bytes_le)
    verify = ctypes.WinDLL("wintrust", use_last_error=True).WinVerifyTrust
    verify.argtypes = [wintypes.HWND, ctypes.c_void_p, ctypes.POINTER(TrustData)]
    verify.restype = ctypes.c_long
    return verify(wintypes.HWND(-1), ctypes.byref(action), ctypes.byref(data)) == 0


def original_filename(path):
    if os.name != "nt":
        return ""
    try:
        import win32api
        for language, codepage in win32api.GetFileVersionInfo(str(path), "\\VarFileInfo\\Translation"):
            query = f"\\StringFileInfo\\{language:04x}{codepage:04x}\\OriginalFilename"
            value = win32api.GetFileVersionInfo(str(path), query)
            if value:
                if value.casefold().endswith(".mui"):
                    value = value[:-4]
                return Path(value).stem.casefold()
    except Exception:
        # Missing/unreadable identity cannot establish an ordinary trusted app.
        return ""
    return ""


def windows_directory():
    if os.name != "nt":
        return Path(os.environ.get("SystemRoot", "C:/Windows"))
    buffer = ctypes.create_unicode_buffer(32768)
    function = ctypes.WinDLL("kernel32", use_last_error=True).GetWindowsDirectoryW
    function.argtypes = [wintypes.LPWSTR, wintypes.UINT]
    function.restype = wintypes.UINT
    length = function(buffer, len(buffer))
    if not 0 < length < len(buffer):
        raise OSError("Windows directory could not be resolved safely.")
    return Path(buffer.value)
