"""Per-user Inno Setup handoff. No elevation, shell commands or URL execution.

The helper runs from a separate copy of the installed bundle, waits for the
application lock to be released, then re-verifies the staged package through TUF.
The original profile and a consistent recovery snapshot are always retained.
"""

from datetime import datetime, timezone
from contextlib import contextmanager
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
from time import monotonic, sleep
from uuid import uuid4

from nexis import __version__
from nexis.core.update_service import (
    APP_ID, UpdateError, UpdateService, operation_lock, regular_path, semver,
)


def registered_directory(app_id=APP_ID):
    if sys.platform != "win32":
        raise UpdateError("Automatic installation is currently supported on Windows x64 only.")
    import winreg

    try:
        key_name = "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\{" + app_id + "}_is1"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_name, 0,
                            winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
            directory, kind = winreg.QueryValueEx(key, "InstallLocation")
        if kind != winreg.REG_SZ or not Path(directory).is_absolute():
            raise ValueError()
        directory = regular_path(directory)
        if not (directory / "NEXIS.exe").is_file():
            raise ValueError()
        return directory
    except (OSError, ValueError):
        raise UpdateError("This copy is not the registered per-user installation. Install NEXIS with the official Setup before using Restart & Install. Portable copies are preserved.") from None


def require_standard_user():
    if sys.platform != "win32":
        raise UpdateError("Automatic installation is currently supported on Windows x64 only.")
    import ctypes

    if ctypes.windll.shell32.IsUserAnAdmin():
        raise UpdateError("Close NEXIS and start it normally without administrator rights before updating. This per-user installer does not require elevation.")


def installed_build(directory):
    import win32api

    info = win32api.GetFileVersionInfo(str(regular_path(directory / "NEXIS.exe")), "\\")
    high, low = info["FileVersionMS"], info["FileVersionLS"]
    return f"{high >> 16}.{high & 65535}.{low >> 16}"


@contextmanager
def package_read_lock(path):
    """Deny replacement/writes between final TUF verification and execution."""
    if sys.platform != "win32":
        raise UpdateError("Windows installation is unavailable on this platform.")
    import win32con
    import win32file

    handle = win32file.CreateFile(str(regular_path(path)), win32con.GENERIC_READ,
        win32con.FILE_SHARE_READ, None, win32con.OPEN_EXISTING, 0, None)
    try:
        yield
    finally:
        handle.Close()


def snapshot_profile(profile, db, destination):
    """Online SQLite backup plus all adjacent user files; never restore implicitly."""
    profile, destination = regular_path(profile), regular_path(destination)
    files = []
    for current, dirs, names in os.walk(profile, followlinks=False):
        current = regular_path(current)
        if current == profile:
            dirs[:] = [name for name in dirs if name != "updates"]
        for name in dirs:
            regular_path(current / name)
        for name in names:
            source = regular_path(current / name)
            if (source == db.path or source.name in {"nexis.lock", db.path.name + "-wal", db.path.name + "-shm"}
                    or source.name.startswith("nexis.log")):
                continue
            files.append(source)
    required = sum(p.stat().st_size for p in files) + db.path.stat().st_size + 64 * 1024**2
    if shutil.disk_usage(profile).free < required:
        raise UpdateError("Not enough storage for a recovery snapshot. Free space before restarting.")
    destination.mkdir(parents=True, exist_ok=False)
    try:
        with sqlite3.connect(destination / db.path.name) as backup, db.lock:
            db.connection.backup(backup)
            if backup.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise UpdateError("Recovery database verification failed. Installation was not started.")
        for source in files:
            target = destination / source.relative_to(profile)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    except Exception:
        # Keep an incomplete snapshot for diagnosis; it is never used automatically.
        raise UpdateError("The recovery snapshot could not finish. No installer was started; free space and retry.") from None


class WindowsInstaller:
    """The only production process-execution boundary for updates."""

    def __init__(self, service, profile, app_id=APP_ID):
        self.service, self.profile, self.app_id = service, regular_path(profile), app_id

    def prepare(self, db, cancel, progress):
        if sys.platform != "win32" or not getattr(sys, "frozen", False):
            raise UpdateError("Restart & Install requires the installed Windows application.")
        require_standard_user()
        directory = registered_directory(self.app_id)
        if regular_path(sys.executable).parent != directory:
            raise UpdateError("Run the registered NEXIS installation to apply an update.")
        with operation_lock(self.service.directory):
            release, _ = self.service.verified_staged()
            if semver(release.build_version) <= semver(installed_build(directory)):
                raise UpdateError("An older or already installed build was rejected.")
            token = uuid4().hex
            runner = regular_path(self.service.directory / "runners" / token)
            sources = []
            for path in directory.rglob("*"):
                regular_path(path)
                if path.is_file():
                    sources.append(path)
            required = sum(p.stat().st_size for p in sources)
            # Allow both a copied helper bundle and installer expansion on the app drive.
            if (shutil.disk_usage(self.profile).free < required + release.size * 6 + 256 * 1024**2
                    or shutil.disk_usage(directory).free < release.size * 6 + 256 * 1024**2):
                raise UpdateError("Not enough storage to install safely. Free space on the application and profile drives, then retry.")
            progress("Preparing a recovery copy of NEXIS…")
            runner.mkdir(parents=True, exist_ok=False)
            for source in sources:
                if cancel.is_set():
                    raise UpdateError("Restart preparation cancelled. The current application is unchanged.")
                target = runner / source.relative_to(directory)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
            progress("Saving a consistent recovery snapshot of your profile…")
            backup = self.service.directory / "backups" / token
            snapshot_profile(self.profile, db, backup)
            if cancel.is_set():
                raise UpdateError("Restart preparation cancelled. No installer was started.")
            self.service.record(phase="prepared", token=token, runner=str(runner),
                backup=str(backup), from_build=__version__, to_build=release.build_version,
                prepared_at=datetime.now(timezone.utc).isoformat(), error="")
            return token

    def launch_helper(self, token):
        with operation_lock(self.service.directory):
            state = self.service.read_state()
            if state.get("phase") != "prepared" or state.get("token") != token:
                raise UpdateError("The prepared update changed. Retry Restart & Install.")
            # Never take an executable path from persisted state.
            if len(token) != 32 or any(c not in "0123456789abcdef" for c in token):
                raise UpdateError("Invalid update handoff.")
            executable = regular_path(self.service.directory / "runners" / token / "NEXIS.exe")
            subprocess.Popen([str(executable), "--apply-update"], cwd=executable.parent,
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW,
                close_fds=True)

    def apply(self, wait_for_exit, restart=None):
        """Helper entry point. Callbacks make actual installer integration testable."""
        require_standard_user()
        with operation_lock(self.service.directory):
            state = self.service.read_state()
            if state.get("phase") != "prepared":
                raise UpdateError("No prepared update is available.")
            self.service.record(phase="waiting")
            if not wait_for_exit():
                self.service.record(phase="install_failed", error="NEXIS did not close. No installation was started. Close active work and retry.")
                return 1
            try:
                directory = registered_directory(self.app_id)
                release, package = self.service.verified_staged()
                if semver(release.build_version) <= semver(installed_build(directory)):
                    raise UpdateError("An older or already installed build was rejected.")
                self.service.record(phase="installing")
                log = regular_path(self.service.directory / "installer.log")
                # Fixed switches; neither URLs nor release metadata supply arguments.
                with package_read_lock(package):
                    self.service.verified_staged()
                    result = subprocess.run([str(package), "/VERYSILENT", "/SUPPRESSMSGBOXES",
                        "/NORESTART", "/SP-", "/NOCLOSEAPPLICATIONS", "/NORESTARTAPPLICATIONS",
                        "/DIR=" + str(directory), "/LOG=" + str(log)], cwd=package.parent,
                        timeout=1200, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                        check=False)
                if result.returncode != 0:
                    raise UpdateError(f"Setup failed (code {result.returncode}). Your profile snapshot and previous application copy are retained. See UPDATE-GUIDE.md or rerun the verified Setup to repair.")
                if installed_build(directory) != release.build_version:
                    raise UpdateError("Setup finished without the expected application version. Use the retained recovery copy or repair with verified Setup.")
                self.service.record(phase="awaiting_restart", error="")
                if restart:
                    restart(directory / "NEXIS.exe")
                else:
                    subprocess.Popen([str(directory / "NEXIS.exe")], cwd=directory, close_fds=True)
                # New app acknowledges readiness after opening its database and window.
                deadline = monotonic() + 60
                while monotonic() < deadline:
                    if self.service.read_state().get("phase") == "complete":
                        return 0
                    sleep(.25)
                self.service.record(phase="restart_failed", error="The update installed, but startup was not confirmed. Launch NEXIS from the Start menu. If it cannot open, use the retained recovery copy and profile snapshot; see UPDATE-GUIDE.md.")
                return 2
            except Exception as exc:
                message = str(exc) if isinstance(exc, UpdateError) else "The installer or restart could not finish. Recovery files are retained. See UPDATE-GUIDE.md."
                self.service.record(phase="install_failed", error=message)
                return 1


def acknowledge_startup(service):
    """Called only once the normal application has opened its profile and window."""
    state = service.read_state()
    if state.get("to_build") == __version__ and state.get("phase") in {
            "awaiting_restart", "restart_failed", "install_failed"}:
        service.record(phase="complete", completed_at=datetime.now(timezone.utc).isoformat(), error="")


def helper_main(profile):
    from PySide6.QtCore import QLockFile

    profile = regular_path(profile)
    service = UpdateService(profile / "updates")

    def wait_for_exit():
        lock = QLockFile(str(profile / "nexis.lock"))
        deadline = monotonic() + 60
        while monotonic() < deadline:
            if lock.tryLock(100):
                lock.unlock()
                return True
            sleep(.2)
        return False

    try:
        return WindowsInstaller(service, profile).apply(wait_for_exit)
    except (ValueError, OSError):
        return 1
