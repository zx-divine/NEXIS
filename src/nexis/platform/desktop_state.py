"""Documented Windows notification eligibility; no hooks or window interception."""

import ctypes
import sys
from functools import lru_cache


@lru_cache(maxsize=1)
def notification_query():
    if sys.platform != "win32":
        return None
    try:
        query = ctypes.WinDLL("shell32", use_last_error=True).SHQueryUserNotificationState
        query.argtypes = [ctypes.POINTER(ctypes.c_int)]
        query.restype = ctypes.c_long
        return query
    except (OSError, AttributeError):
        return None


def notification_state():
    query = notification_query()
    if query is None:
        return None
    state = ctypes.c_int()
    return state.value if query(ctypes.byref(state)) == 0 else None
