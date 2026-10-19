import re
from pathlib import Path
from urllib.parse import urlsplit


NAME = re.compile(r"[^\W_][\w .()-]{0,99}\Z", re.UNICODE)
BLOCKED = {
    "cmd",
    "powershell",
    "pwsh",
    "python",
    "pythonw",
    "py",
    "wscript",
    "cscript",
    "mshta",
    "rundll32",
    "regsvr32",
    "bash",
    "wsl",
    "sh",
    "reg",
    "schtasks",
    "msiexec",
    "installutil",
    "certutil",
    "wmic",
    "cdb",
    "csi",
    "dotnet",
    "msbuild",
    "node",
    "java",
    "javaw",
    "perl",
    "ruby",
}


def name(value: str) -> str:
    value = value.strip().lower()
    if not NAME.fullmatch(value):
        raise ValueError(
            "Use a name of 1–64 letters, numbers, spaces, dots, dashes or underscores."
        )
    return value


def url(value: str) -> str:
    if len(value) > 2048 or any(c.isspace() or ord(c) < 32 for c in value):
        raise ValueError("Enter a valid HTTPS address without whitespace.")
    try:
        parts = urlsplit(value)
        if (
            parts.scheme != "https"
            or not parts.hostname
            or parts.username
            or parts.password
            or "\\" in value
            or not parts.port
            and parts.netloc.endswith(":")
        ):
            raise ValueError()
        parts.hostname.encode("idna")
    except (ValueError, UnicodeError):
        raise ValueError("Only HTTPS URLs without embedded credentials are supported.") from None
    return value


def executable(value: str) -> Path:
    if value.startswith(("\\\\", "//")):
        raise ValueError("Network executables are not supported.")
    path = Path(value)
    if not path.is_absolute() or path.suffix.lower() != ".exe":
        raise ValueError("Choose an absolute path to an .exe application.")
    path = path.resolve(strict=True)
    if not path.is_file() or path.stem.lower() in BLOCKED:
        raise ValueError("Scripts and command interpreters are not allowed.")
    if str(path).startswith("\\\\"):
        raise ValueError("Network executables are not supported.")
    return path


def approved_root(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute() or not path.is_dir():
        raise ValueError("Choose an existing absolute folder path.")
    path = path.resolve(strict=True)
    if path == Path(path.anchor) or str(path).startswith("\\\\"):
        raise ValueError("Choose a local subfolder, not a drive root or network share.")
    return path
