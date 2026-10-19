"""Read an EXE's elevation manifest as data. Never load or run its code."""
import ctypes
from xml.etree import ElementTree

from nexis.core.results import Risk


def elevation_risk(path):
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    load = kernel.LoadLibraryExW
    load.argtypes = [ctypes.c_wchar_p, ctypes.c_void_p, ctypes.c_uint]
    load.restype = ctypes.c_void_p
    find = kernel.FindResourceW
    find.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
    find.restype = ctypes.c_void_p
    size = kernel.SizeofResource
    size.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    size.restype = ctypes.c_uint
    resource = kernel.LoadResource
    resource.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    resource.restype = ctypes.c_void_p
    lock = kernel.LockResource
    lock.argtypes = [ctypes.c_void_p]
    lock.restype = ctypes.c_void_p
    free = kernel.FreeLibrary
    free.argtypes = [ctypes.c_void_p]
    free.restype = ctypes.c_int
    handle = load(str(path), None, 0x02 | 0x20)  # AS_DATAFILE | AS_IMAGE_RESOURCE
    if not handle:
        return Risk.MEDIUM  # Unknown executable metadata never lowers risk.
    try:
        item = find(handle, 1, 24)  # Executable manifest resource, RT_MANIFEST.
        if not item:
            return Risk.LOW
        length = size(handle, item)
        pointer = lock(resource(handle, item))
        if not pointer or not 0 < length <= 1024 * 1024:
            return Risk.MEDIUM
        try:
            tree = ElementTree.fromstring(ctypes.string_at(pointer, length))
        except ElementTree.ParseError:
            return Risk.MEDIUM
        for element in tree.iter():
            if element.tag.rsplit("}", 1)[-1] == "requestedExecutionLevel":
                level = element.attrib.get("level", "").casefold()
                if level in {"requireadministrator", "highestavailable"}:
                    return Risk.HIGH
                if level != "asinvoker" or element.attrib.get("uiAccess", "false").lower() != "false":
                    return Risk.MEDIUM
        return Risk.LOW
    finally:
        free(handle)
