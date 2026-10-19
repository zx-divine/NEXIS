"""Brand resources resolve beside the package, independent of the working directory."""

import ctypes
import sys
from pathlib import Path

from PySide6.QtGui import QIcon

APP_USER_MODEL_ID = "NEXIS.Desktop"


def asset(name):
    if name not in {"NEXIS_logo.png", "NEXIS.ico"}:
        raise ValueError("Unknown branding asset")
    return Path(__file__).resolve().parent / "assets" / "branding" / name


def application_icon():
    return QIcon(str(asset("NEXIS.ico")))


def set_app_user_model_id():
    """Set the stable shell identity before Qt creates any native window."""
    if sys.platform != "win32":
        return False
    shell = ctypes.WinDLL("shell32", use_last_error=True)
    setter = shell.SetCurrentProcessExplicitAppUserModelID
    setter.argtypes = [ctypes.c_wchar_p]
    setter.restype = ctypes.c_long
    return setter(APP_USER_MODEL_ID) == 0
