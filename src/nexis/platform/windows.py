import os
import subprocess
import sys
import webbrowser
from pathlib import Path

from nexis.utils.validation import executable, url

BUILTINS = {
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "explorer": "explorer.exe",
    "paint": "mspaint.exe",
}


class Windows:
    def launch(self, target: str, builtin=False):
        self.require_windows()
        if builtin:
            if target not in BUILTINS:
                raise ValueError("Application is not approved.")
            base = Path(os.environ.get("SystemRoot", "C:/Windows"))
            path = base / (
                "explorer.exe" if target == "explorer" else "System32/" + BUILTINS[target]
            )
        else:
            path = executable(target)
        if not path.is_file():
            raise ValueError("This Windows application is not installed or is unavailable.")
        subprocess.Popen([str(path)], shell=False, close_fds=True)

    def website(self, target):
        if not webbrowser.open(url(target), new=2):
            raise OSError("No default browser accepted the request.")

    def folder(self, path):
        self.require_windows()
        explorer = Path(os.environ.get("SystemRoot", "C:/Windows")) / "explorer.exe"
        subprocess.Popen([str(explorer), str(path)], shell=False, close_fds=True)

    @staticmethod
    def require_windows():
        if sys.platform != "win32":
            raise OSError("This action requires Windows.")

    @staticmethod
    def startup_command():
        if getattr(sys, "frozen", False):
            args = [sys.executable, "--minimised"]
        else:
            pythonw = Path(sys.executable).with_name("pythonw.exe")
            interpreter = str(pythonw if pythonw.exists() else sys.executable)
            entry = Path(__file__).resolve().parents[3] / "scripts" / "entry.py"
            args = (
                [interpreter, str(entry), "--minimised"]
                if entry.exists()
                else [interpreter, "-m", "nexis.main", "--minimised"]
            )
        return subprocess.list2cmdline(args)

    def startup_enabled(self):
        self.require_windows()
        import winreg

        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run"
            ) as key:
                return winreg.QueryValueEx(key, "NEXIS Desktop")[0] == self.startup_command()
        except FileNotFoundError:
            return False

    def set_startup(self, enabled):
        self.require_windows()
        import winreg

        with winreg.CreateKey(
            winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run"
        ) as key:
            if enabled:
                winreg.SetValueEx(key, "NEXIS Desktop", 0, winreg.REG_SZ, self.startup_command())
            else:
                try:
                    winreg.DeleteValue(key, "NEXIS Desktop")
                except FileNotFoundError:
                    pass
