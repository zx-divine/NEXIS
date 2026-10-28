"""Risk of an explicit launch request; this grants no capability by itself.

PE structure alone does not establish that a downloaded program is a trusted app.
Only normal installed locations qualify for low risk; other executables keep fresh
review. Interpreter validation, category grants and target revalidation still apply.
"""
import os
from pathlib import Path
import re

from nexis.core.results import Risk
from nexis.platform.discovery import verified_exe
from nexis.platform.manifest import elevation_risk
from nexis.platform.trust import trusted_signature, original_filename, windows_directory
from nexis.utils.validation import BLOCKED

SENSITIVE = re.compile(
    r"setup|install|unins|updat|regedit|taskmgr|control|mmc|netsh|bcdedit|dism|terminal|powershell",
    re.IGNORECASE,
)


def launch_risk(target, *, appx=False):
    if not appx:
        path = Path(target).resolve(strict=True)
        windows = windows_directory()
        system_targets = [windows / "explorer.exe", *(windows / "System32" / name
                          for name in ("Taskmgr.exe", "notepad.exe", "calc.exe", "mspaint.exe"))]
        if path in [system_path.resolve() for system_path in system_targets]:
            verified_exe(target)
            return Risk.LOW
        identity = original_filename(path)
        if identity in BLOCKED:
            raise ValueError("Interpreters and indirect script hosts cannot be launched by NEXIS, including renamed executables.")
    if SENSITIVE.search(str(target) if appx else Path(target).stem):
        return Risk.HIGH
    if appx:
        # The caller separately validates the identifier against current Windows registrations.
        return Risk.LOW
    roots = [Path(value) for key in ("ProgramFiles", "ProgramFiles(x86)")
             if (value := os.environ.get(key))]
    local = os.environ.get("LOCALAPPDATA")
    if local:
        roots.extend(Path(local) / suffix for suffix in (
            "Programs", "Discord", "slack", "Spotify", "Google/Chrome/Application",
        ))
    roaming = os.environ.get("APPDATA")
    if roaming:
        roots.append(Path(roaming) / "Spotify")
    for root in roots:
        if path.is_relative_to(root.resolve()) and path != root.resolve():
            # Ordinary application EXEs still require a valid PE and no unsafe basename.
            verified_exe(path)
            if not identity or SENSITIVE.search(identity) or not trusted_signature(path):
                return Risk.HIGH
            return elevation_risk(path) if os.name == "nt" else Risk.LOW
    return Risk.HIGH
