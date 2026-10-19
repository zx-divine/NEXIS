"""Small read-only Windows sensors; no services, WMI polling or extra dependencies."""

import ctypes
from ctypes import wintypes
from dataclasses import dataclass
import sys


@dataclass(frozen=True)
class SystemSample:
    cpu: float | None = None
    memory: float | None = None
    total_memory_mb: float | None = None
    uptime_seconds: int | None = None


class SystemSampler:
    def __init__(self):
        self.previous = None
        self.kernel = (
            ctypes.WinDLL("kernel32", use_last_error=True) if sys.platform == "win32" else None
        )
        if self.kernel:
            self.kernel.GetTickCount64.restype = ctypes.c_ulonglong

    def reset(self):
        self.previous = None

    def sample(self):
        if not self.kernel:
            return SystemSample()

        class Memory(ctypes.Structure):
            _fields_ = [("length", wintypes.DWORD), ("load", wintypes.DWORD)] + [
                (name, ctypes.c_ulonglong)
                for name in (
                    "total",
                    "available",
                    "page_total",
                    "page_available",
                    "virtual_total",
                    "virtual_available",
                    "extended",
                )
            ]

        memory = Memory()
        memory.length = ctypes.sizeof(memory)
        memory_ok = self.kernel.GlobalMemoryStatusEx(ctypes.byref(memory))
        times = [wintypes.FILETIME() for _ in range(3)]
        cpu = None
        if self.kernel.GetSystemTimes(*[ctypes.byref(t) for t in times]):
            idle, kernel, user = [(t.dwHighDateTime << 32) + t.dwLowDateTime for t in times]
            total = kernel + user
            if self.previous:
                delta = total - self.previous[1]
                if delta > 0:
                    cpu = max(0.0, min(100.0, 100 * (1 - (idle - self.previous[0]) / delta)))
            self.previous = (idle, total)
        return SystemSample(
            cpu,
            float(memory.load) if memory_ok else None,
            memory.total / 1048576 if memory_ok else None,
            self.kernel.GetTickCount64() // 1000,
        )


def process_working_set_mb():
    """Current process working set, or None when the OS query is unavailable."""
    if sys.platform != "win32":
        return None

    class Counters(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("faults", wintypes.DWORD)] + [
            (name, ctypes.c_size_t)
            for name in (
                "peak",
                "working",
                "peak_paged",
                "paged",
                "peak_nonpaged",
                "nonpaged",
                "pagefile",
                "peak_pagefile",
            )
        ]

    info = Counters()
    info.cb = ctypes.sizeof(info)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
    if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(info), info.cb):
        return None
    return info.working / 1048576
