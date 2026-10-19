"""Read actual Windows shell icons and installed shortcut metadata.

No Explorer restart, pin changes, or icon-cache deletion. Run with the dev Qt runtime.
"""

import argparse
import ctypes
from ctypes import wintypes
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".dev-deps"))
from PySide6.QtWidgets import QApplication  # noqa: E402
from PySide6.QtGui import QImage  # noqa: E402


class SHFILEINFO(ctypes.Structure):
    _fields_ = [
        ("hIcon", wintypes.HICON),
        ("iIcon", ctypes.c_int),
        ("dwAttributes", wintypes.DWORD),
        ("szDisplayName", wintypes.WCHAR * 260),
        ("szTypeName", wintypes.WCHAR * 80),
    ]


def main():
    app = QApplication([])
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=root / "docs/branding-windows")
    parser.add_argument("paths", nargs="*")
    args = parser.parse_args()
    destination = args.output.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    paths = [Path(p).resolve(strict=True) for p in args.paths]
    if not paths:
        paths = [root / "dist/NEXIS/NEXIS.exe"]
    shell = ctypes.WinDLL("shell32", use_last_error=True)
    get_info = shell.SHGetFileInfoW
    get_info.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        ctypes.POINTER(SHFILEINFO),
        wintypes.UINT,
        wintypes.UINT,
    ]
    get_info.restype = ctypes.c_size_t
    destroy = ctypes.windll.user32.DestroyIcon
    destroy.argtypes = [wintypes.HICON]
    reports = []
    for index, path in enumerate(paths):
        result = {"path": str(path), "shell_icons": []}
        for label, flags in (("small", 0x101), ("large", 0x100)):
            info = SHFILEINFO()
            assert get_info(str(path), 0, ctypes.byref(info), ctypes.sizeof(info), flags)
            try:
                image = QImage.fromHICON(int(info.hIcon))
                assert not image.isNull()
                filename = destination / f"{index}-{label}.png"
                assert image.save(str(filename))
                result["shell_icons"].append(
                    {"size": [image.width(), image.height()], "image": str(filename)}
                )
            finally:
                destroy(info.hIcon)
        reports.append(result)
    (destination / "shell-icons.json").write_text(json.dumps(reports, indent=2), encoding="utf-8")
    print(json.dumps(reports, indent=2))
    app.quit()


if __name__ == "__main__":
    main()
