"""On-demand, read-only host information. No shell, WMI or internet probes."""

import ctypes
from ctypes import wintypes
import shutil
import sys
from time import monotonic

from nexis.platform.system import SystemSampler


def top_processes(cancel, limit=10):
    """Best-effort bounded working-set ranking, not a global CPU ranking."""
    if sys.platform != "win32":
        return []
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)

    class Entry(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("usage", wintypes.DWORD),
                    ("pid", wintypes.DWORD), ("heap", ctypes.c_size_t),
                    ("module", wintypes.DWORD), ("threads", wintypes.DWORD),
                    ("parent", wintypes.DWORD), ("priority", wintypes.LONG),
                    ("flags", wintypes.DWORD), ("name", wintypes.WCHAR * 260)]

    class Counters(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("faults", wintypes.DWORD)] + [
            (name, ctypes.c_size_t) for name in ("peak", "working", "peak_paged", "paged",
                                               "peak_nonpaged", "nonpaged", "pagefile", "peak_pagefile")]

    kernel.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(Entry)]
    kernel.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(Entry)]
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
    snapshot = kernel.CreateToolhelp32Snapshot(2, 0)
    if snapshot in (None, ctypes.c_void_p(-1).value):
        return []
    result, inspected, deadline = [], 0, monotonic() + 2
    entry = Entry()
    entry.size = ctypes.sizeof(entry)
    try:
        found = kernel.Process32FirstW(snapshot, ctypes.byref(entry))
        while found and inspected < 512 and monotonic() < deadline and not cancel.is_set():
            inspected += 1
            handle = kernel.OpenProcess(0x410, False, entry.pid)  # Query + read only; no elevation.
            if handle:
                try:
                    info = Counters()
                    info.cb = ctypes.sizeof(info)
                    if psapi.GetProcessMemoryInfo(handle, ctypes.byref(info), info.cb):
                        result.append({"pid": int(entry.pid), "name": entry.name,
                                       "working_set_mb": round(info.working / 1048576, 1)})
                finally:
                    kernel.CloseHandle(handle)
            found = kernel.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel.CloseHandle(snapshot)
    return sorted(result, key=lambda row: row["working_set_mb"], reverse=True)[:limit]


def power_status():
    if sys.platform != "win32":
        return "Unavailable"

    class Power(ctypes.Structure):
        _fields_ = [(name, ctypes.c_ubyte) for name in ("ac", "flags", "percent", "reserved")] + [
            ("remaining", wintypes.DWORD), ("full", wintypes.DWORD)]

    value = Power()
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    if not kernel.GetSystemPowerStatus(ctypes.byref(value)):
        return "Unavailable"
    if value.flags != 255 and value.flags & 128:
        return "No system battery detected"
    percent = str(value.percent) + "%" if value.percent <= 100 else "level unavailable"
    charging = "charging" if value.flags != 255 and value.flags & 8 else "not charging"
    supply = {0: "battery power", 1: "AC power"}.get(value.ac, "power source unavailable")
    return f"{percent}; {supply}; {charging}"


def network_status():
    if sys.platform != "win32":
        return "Unavailable; no internet probe performed"
    flags = wintypes.DWORD()
    wininet = ctypes.WinDLL("wininet", use_last_error=True)
    reported = bool(wininet.InternetGetConnectedState(ctypes.byref(flags), 0))
    return ("Windows reports a connection" if reported else "Windows reports no connection") + "; internet and provider reachability not verified"


def health_snapshot(directory, cancel):
    sampler = SystemSampler()
    sampler.sample()
    if cancel.wait(0.25):
        return None
    sample = sampler.sample()
    result = {"cpu_percent": sample.cpu, "memory_percent": sample.memory,
              "total_memory_mb": sample.total_memory_mb, "available_memory_mb": None,
              "uptime_seconds": sample.uptime_seconds, "disk_free_gb": None, "disk_total_gb": None,
              "battery": "Unavailable", "network": "Unavailable", "temperature": "Unavailable: no reliable sensor backend configured",
              "top_processes": []}
    if sys.platform == "win32":
        # Reuse the documented physical-memory layout; available is not estimated from percentage.
        class Memory(ctypes.Structure):
            _fields_ = [("length", wintypes.DWORD), ("load", wintypes.DWORD)] + [
                (name, ctypes.c_ulonglong) for name in ("total", "available", "page_total", "page_available", "virtual_total", "virtual_available", "extended")]
        info = Memory()
        info.length = ctypes.sizeof(info)
        if ctypes.WinDLL("kernel32", use_last_error=True).GlobalMemoryStatusEx(ctypes.byref(info)):
            result["available_memory_mb"] = round(info.available / 1048576)
    try:
        disk = shutil.disk_usage(directory)
        result.update(disk_free_gb=round(disk.free / 1073741824, 1), disk_total_gb=round(disk.total / 1073741824, 1))
    except OSError:
        pass
    for key, operation in (("battery", power_status), ("network", network_status),
                           ("top_processes", lambda: top_processes(cancel))):
        if cancel.is_set():
            return None
        try:
            result[key] = operation()
        except (OSError, AttributeError):
            pass
    return result
