"""Signed, bounded Windows releases. Only python-tuf establishes update trust.

GitHub transports a standard TUF repository; it is never the trust anchor.
The installer adapter is deliberately separate from discovery and download.
"""

from contextlib import contextmanager
from dataclasses import dataclass, asdict
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from threading import Event
from time import monotonic
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from tuf.api import exceptions
from tuf.ngclient import Updater
from tuf.ngclient.config import UpdaterConfig
from tuf.ngclient.fetcher import FetcherInterface

from nexis import __version__, PUBLIC_VERSION

APP_ID = "F462E4BE-1F1F-428C-AD8C-4B5C06972164"
REPOSITORY = "https://github.com/zx-divine/NEXIS/releases/"
METADATA_URL = REPOSITORY + "latest/download/"
RELEASE_INDEX = "NEXIS-Windows-x64.json"
MAX_PACKAGE = 2 * 1024**3
MAX_METADATA = 1024 * 1024
CHECK_INTERVAL = 24 * 60 * 60
_VERSION = re.compile(r"(0|[1-9][0-9]{0,8})\.(0|[1-9][0-9]{0,8})\.(0|[1-9][0-9]{0,8})\Z")
_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,179}\Z")


class UpdateError(ValueError):
    """Safe user-facing error; never include URLs with temporary GitHub tokens."""


def semver(value):
    match = _VERSION.fullmatch(value) if isinstance(value, str) else None
    if not match:
        raise UpdateError("The signed release has an invalid stable semantic version.")
    return tuple(map(int, match.groups()))


def filename(value):
    if not isinstance(value, str) or not _NAME.fullmatch(value) or ".." in value:
        raise UpdateError("The update filename is unsafe.")
    return value


def regular_path(path):
    """Reject junctions/symlinks before reading, writing or executing update state."""
    path = Path(path).absolute()
    for part in (path, *path.parents):
        if part.is_symlink() or (part.exists() and getattr(part.lstat(), "st_file_attributes", 0) & 0x400):
            raise UpdateError("The update location contains a link. Use a regular local installation.")
    if str(path).startswith(("\\\\", "//")):
        raise UpdateError("Updates require a local disk.")
    return path


def atomic_json(path, value):
    path = regular_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".new")
    regular_path(temporary)
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def erase_recovery(directory):
    """Used only after the existing explicit Delete all data authorization.

    Refuse linked/junctioned directories before deleting any cache contents.
    Keep the held lock file, so another helper cannot enter during deletion.
    """
    root = regular_path(directory)
    if not root.exists():
        return
    with operation_lock(root):
        for current, dirs, files in os.walk(root, followlinks=False):
            for name in dirs + files:
                child = Path(current) / name
                if child == root / "metadata/root.json" and child.is_symlink():
                    continue  # TUF's own convenience link is unlinked by rmtree.
                regular_path(child)
                if not child.resolve().is_relative_to(root.resolve()):
                    raise UpdateError("Recovery cleanup refused a path outside the update cache.")
        for child in root.iterdir():
            if child.name == "operation.lock":
                continue
            # All descendants were checked above, and this resolved target is
            # inside the fixed profile/updates directory before recursive delete.
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()


@contextmanager
def operation_lock(directory):
    """A crash releases the OS lock; a second process cannot install concurrently."""
    directory = regular_path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    with regular_path(directory / "operation.lock").open("a+b") as stream:
        stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise UpdateError("Another update operation is already running.") from None
        try:
            if os.fstat(stream.fileno()).st_size == 0:
                stream.write(b"0")
                stream.flush()
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)


def validate_url(url, redirect=False):
    """Only the fixed repository and GitHub's release CDN can supply bytes."""
    try:
        parsed = urlsplit(url)
        if (parsed.scheme != "https" or parsed.username or parsed.password or parsed.port
                or parsed.fragment or any(ord(c) < 33 for c in url) or "\\" in url):
            raise ValueError()
        if parsed.hostname == "github.com":
            if parsed.query or not parsed.path.startswith("/zx-divine/NEXIS/releases/"):
                raise ValueError()
            tail = parsed.path[len("/zx-divine/NEXIS/releases/"):].split("/")
            if len(tail) != 3 or not ((tail[0:2] == ["latest", "download"])
                    or (tail[0] == "download" and re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", tail[1]))):
                raise ValueError()
            filename(tail[-1])
        elif not redirect or parsed.hostname != "release-assets.githubusercontent.com":
            raise ValueError()
        elif "%" in parsed.path or any(p in {".", ".."} for p in parsed.path.split("/")):
            raise ValueError()
    except (ValueError, TypeError):
        raise UpdateError("An update URL was outside the trusted HTTPS release infrastructure.") from None
    return url


class ReleaseRedirect(HTTPRedirectHandler):
    max_redirections = 5
    max_repeats = 2

    def redirect_request(self, request, fp, code, msg, headers, newurl):
        validate_url(newurl, redirect=True)
        return super().redirect_request(request, fp, code, msg, headers, newurl)


class HTTPSFetcher(FetcherInterface):
    """TLS stays enabled. Bounded reads, timeouts, cancellation and real progress."""

    def __init__(self, directory, cancel=None, progress=None):
        self.directory = regular_path(directory)
        self.cancel = cancel or Event()
        self.progress = progress or (lambda value: None)
        self.opener = build_opener(ReleaseRedirect())
        self.expected = 0

    def _fetch(self, url):
        validate_url(url)
        request = Request(url, headers={"User-Agent": "NEXIS-Desktop/" + __version__,
                                        "Accept-Encoding": "identity"})
        start, last, transferred = monotonic(), 0, 0
        try:
            with self.opener.open(request, timeout=12) as response:
                validate_url(response.geturl(), redirect=True)
                while True:
                    if self.cancel.is_set():
                        raise UpdateError("Update cancelled. Retry to download a fresh verified copy.")
                    if monotonic() - start > (3600 if self.expected else 45):
                        raise UpdateError("The update request timed out. Retry when the connection improves.")
                    chunk = response.read(128 * 1024)
                    if not chunk:
                        break
                    transferred += len(chunk)
                    now = monotonic()
                    if self.expected and (now - last >= .15 or transferred == self.expected):
                        self.progress({"transferred": transferred, "total": self.expected,
                                       "speed": int(transferred / max(.001, now - start))})
                        last = now
                    yield chunk
        except HTTPError as exc:
            status = exc.code
            exc.close()
            raise exceptions.DownloadHTTPError("Release service returned an HTTP error", status) from None

    @contextmanager
    def download_file(self, url, max_length):
        # TUF's default uses the system temp drive; use our measured local cache.
        if not 0 < max_length <= MAX_PACKAGE:
            raise UpdateError("The signed update exceeds the supported size limit.")
        self.directory.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryFile(dir=self.directory) as stream:
            size = 0
            for chunk in self.fetch(url):
                size += len(chunk)
                if size > max_length:
                    raise exceptions.DownloadLengthMismatchError("Update exceeded its signed length")
                stream.write(chunk)
            stream.seek(0)
            yield stream


class CachedFetcher(FetcherInterface):
    """Offline TUF replay for restart: validate cached signatures, expiry and hashes."""

    def __init__(self, metadata):
        self.metadata = regular_path(metadata)

    def _fetch(self, url):
        validate_url(url)
        name = filename(urlsplit(url).path.rsplit("/", 1)[-1])
        path = regular_path(self.metadata / ("root_history/" + name if name.endswith(".root.json") else name))
        if not path.is_file():
            # TUF caches targets/snapshot without version prefixes; roots are versioned.
            plain = re.sub(r"^[0-9]+\.(?=(snapshot|targets)\.json$)", "", name)
            path = regular_path(self.metadata / plain)
        if not path.is_file():
            raise exceptions.DownloadHTTPError("Metadata is not cached", 404)
        if path.stat().st_size > MAX_METADATA:
            raise UpdateError("Cached update metadata is too large.")
        yield path.read_bytes()


@dataclass(frozen=True)
class Release:
    public_version: str
    build_version: str
    tag: str
    installer: str
    notes: str
    size: int

    @property
    def page(self):
        return REPOSITORY + "tag/" + self.tag


def parse_descriptor(data, target):
    fields = {"schema", "app_id", "platform", "installer_kind", "public_version",
              "build_version", "tag", "installer", "notes", "data_schema"}
    if not isinstance(data, dict) or set(data) != fields:
        raise UpdateError("The signed release descriptor is invalid.")
    if (type(data["schema"]) is not int or data["schema"] != 1 or data["app_id"] != APP_ID
            or data["platform"] != "windows-x86_64" or data["installer_kind"] != "inno-per-user"
            or type(data["data_schema"]) is not int or data["data_schema"] != 5):
        raise UpdateError("This release is incompatible with this NEXIS installation.")
    semver(data["public_version"])
    semver(data["build_version"])
    expected = f"NEXIS-{data['public_version']}-{data['build_version']}-Windows-x64-Setup.exe"
    if filename(data["installer"]) != expected or data["tag"] != "v" + data["public_version"]:
        raise UpdateError("The signed installer identity does not match the release.")
    if not isinstance(data["notes"], str) or not 1 <= len(data["notes"]) <= 24000:
        raise UpdateError("The signed release notes are invalid.")
    if (target is None or target.path != expected or not 0 < target.length <= MAX_PACKAGE
            or not re.fullmatch(r"[0-9a-f]{64}", target.hashes.get("sha256", ""))):
        raise UpdateError("The installer is missing a signed SHA-256 hash or size.")
    return Release(data["public_version"], data["build_version"], data["tag"],
                   expected, data["notes"], target.length)


class UpdateService:
    """Platform-neutral signed repository client; no process execution occurs here."""

    def __init__(self, directory, bootstrap=None, current=__version__, public=PUBLIC_VERSION,
                 fetcher_factory=HTTPSFetcher):
        self.directory = regular_path(directory)
        self.metadata = self.directory / "metadata"
        self.targets = self.directory / "targets"
        self.bootstrap = bootstrap or Path(__file__).parents[1] / "assets/updates/root.json"
        self.current, self.public = current, public
        self.fetcher_factory = fetcher_factory

    def _client(self, cancel, progress, offline=False):
        for path in (self.directory, self.metadata, self.targets):
            regular_path(path).mkdir(parents=True, exist_ok=True)
        root = regular_path(self.bootstrap)
        if not root.is_file() or root.stat().st_size > MAX_METADATA:
            raise UpdateError("Updates are unavailable: this build has no publisher trust root.")
        # Check every cache entry before TUF opens its files (including versioned roots).
        for path in self.metadata.rglob("*"):
            # TUF 7 itself maintains root.json as a link. Bootstrap is always
            # embedded, so this convenience link is never a trust source.
            if path == self.metadata / "root.json":
                continue
            regular_path(path)
        fetcher = CachedFetcher(self.metadata) if offline else self.fetcher_factory(self.targets, cancel, progress)
        client = Updater(str(self.metadata), METADATA_URL, str(self.targets), METADATA_URL,
                         fetcher=fetcher, bootstrap=root.read_bytes(),
                         config=UpdaterConfig(root_max_length=MAX_METADATA,
                             targets_max_length=MAX_METADATA, snapshot_max_length=MAX_METADATA,
                             max_root_rotations=32, max_delegations=0))
        return client, fetcher

    def _release(self, client, download=True):
        client.refresh()
        index = client.get_targetinfo(RELEASE_INDEX)
        if index is None or not 0 < index.length <= 32768:
            raise UpdateError("No compatible signed Windows release is available.")
        path = regular_path(self.targets / RELEASE_INDEX)
        if download:
            client.download_target(index, str(path))
        else:
            with path.open("rb") as stream:
                index.verify_length_and_hashes(stream)
        data = json.loads(path.read_bytes())
        installer = filename(data.get("installer")) if isinstance(data, dict) else ""
        return parse_descriptor(data, client.get_targetinfo(installer))

    @contextmanager
    def _errors(self):
        try:
            yield
        except UpdateError:
            raise
        except exceptions.DownloadHTTPError as exc:
            if exc.status_code == 404:
                raise UpdateError("No signed update feed is published yet. NEXIS remains available.") from None
            raise UpdateError("The update server is unavailable or rate limited. Retry later.") from None
        except exceptions.RepositoryError:
            raise UpdateError("Update verification failed: invalid, expired or rolled-back signed metadata. Nothing was installed. Check your clock and retry; contact the publisher if it persists.") from None
        except exceptions.DownloadError:
            raise UpdateError("Download interrupted or offline. Nothing was installed. Check your connection and retry.") from None
        except (OSError, ValueError, TypeError, KeyError):
            raise UpdateError("Update could not complete. Check free storage and folder access, then retry. Existing data is preserved.") from None

    def check(self, cancel, progress=None):
        with self._errors(), operation_lock(self.directory):
            if cancel.is_set():
                raise UpdateError("Update check cancelled.")
            client, _ = self._client(cancel, progress)
            release = self._release(client)
            highest = self.read_state().get("highest_build", self.current)
            available = (semver(release.build_version) > semver(self.current)
                         and semver(release.public_version) >= semver(self.public)
                         and semver(release.build_version) >= semver(highest))
            if available:
                state = self.read_state()
                state["highest_build"] = release.build_version
                atomic_json(self.directory / "state.json", state)
            return release if available else None

    def read_state(self):
        path = regular_path(self.directory / "state.json")
        if not path.is_file():
            return {}
        if path.stat().st_size > 32768:
            raise UpdateError("Update recovery state is invalid. Preserve the updates folder for support.")
        data = json.loads(path.read_bytes())
        if not isinstance(data, dict):
            raise UpdateError("Update recovery state is invalid.")
        return data

    def record(self, **values):
        state = self.read_state()
        state.update(values)
        atomic_json(self.directory / "state.json", state)

    def download(self, release, cancel, progress=None):
        with self._errors(), operation_lock(self.directory):
            client, fetcher = self._client(cancel, progress)
            current_release = self._release(client)
            if current_release != release or semver(release.build_version) <= semver(self.current):
                raise UpdateError("The release changed. Check again before downloading.")
            if shutil.disk_usage(self.directory).free < release.size * 3 + 256 * 1024**2:
                raise UpdateError("Not enough storage to download and verify the update. Free space and retry.")
            target = client.get_targetinfo(release.installer)
            path = regular_path(self.targets / release.installer)
            if not client.find_cached_target(target, str(path)):
                fetcher.expected = release.size
                client.download_target(target, str(path),
                    target_base_url=REPOSITORY + "download/" + release.tag + "/")
            if cancel.is_set():
                raise UpdateError("Update download cancelled.")
            self.record(phase="ready", release=asdict(release), error="")
            return release

    def verified_staged(self):
        """Re-verify through TUF before *every* use, including after an app restart."""
        with self._errors():
            client, _ = self._client(Event(), None, offline=True)
            release = self._release(client, download=False)
            if (semver(release.build_version) <= semver(self.current)
                    or semver(release.public_version) < semver(self.public)
                    or semver(release.build_version) < semver(self.read_state().get("highest_build", self.current))):
                raise UpdateError("An older or already installed update was rejected.")
            target = client.get_targetinfo(release.installer)
            path = regular_path(self.targets / release.installer)
            with path.open("rb") as stream:
                target.verify_length_and_hashes(stream)
            return release, path
