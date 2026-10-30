"""Real Ed25519/TUF fixtures; no network and no production signing keys."""

from datetime import datetime, timedelta, timezone
import hashlib
import json
from threading import Event
from types import SimpleNamespace

import pytest
from securesystemslib.signer import CryptoSigner
from tuf.api import exceptions
from tuf.api.metadata import Metadata, Root, Targets, TargetFile, Snapshot, Timestamp, MetaFile

from nexis.core.update_service import (
    APP_ID, METADATA_URL, RELEASE_INDEX, HTTPSFetcher, UpdateError, UpdateService,
    operation_lock, semver, validate_url,
)
from nexis.platform.update_install import WindowsInstaller, snapshot_profile


class Repository:
    def __init__(self, directory):
        self.directory = directory
        directory.mkdir()
        self.signers = {role: CryptoSigner.generate_ed25519() for role in
                        ("root", "targets", "snapshot", "timestamp")}
        self.root = Metadata(Root(consistent_snapshot=False,
                                 expires=datetime.now(timezone.utc) + timedelta(days=365)))
        for role, signer in self.signers.items():
            self.root.signed.add_key(signer.public_key, role)
        self.root.sign(self.signers["root"])
        self.bootstrap = directory / "1.root.json"
        self.root.to_file(str(self.bootstrap))
        self.requests = []
        self.interrupt = False
        self.sequence = 0
        self.publish()

    def publish(self, build="1.4.3", public="1.1.0", changes=None, expired=False, wrong_key=False):
        self.sequence += 1
        now = datetime.now(timezone.utc)
        expires = now + timedelta(days=-1 if expired else 14)
        name = f"NEXIS-{public}-{build}-Windows-x64-Setup.exe"
        (self.directory / name).write_bytes(b"Signed fixture data; never executed." * 100)
        descriptor = {"schema": 1, "app_id": APP_ID, "platform": "windows-x86_64",
            "installer_kind": "inno-per-user", "public_version": public,
            "build_version": build, "tag": "v" + public, "installer": name,
            "notes": "Verified fixture release notes.", "data_schema": 5}
        descriptor.update(changes or {})
        (self.directory / RELEASE_INDEX).write_text(json.dumps(descriptor))
        targets = Metadata(Targets(version=self.sequence, expires=expires))
        for path in (name, RELEASE_INDEX):
            targets.signed.targets[path] = TargetFile.from_file(path, str(self.directory / path))
        targets.sign(CryptoSigner.generate_ed25519() if wrong_key else self.signers["targets"])
        targets.to_file(str(self.directory / "targets.json"))

        def meta(path):
            data = (self.directory / path).read_bytes()
            return MetaFile(self.sequence, len(data), {"sha256": hashlib.sha256(data).hexdigest()})

        snapshot = Metadata(Snapshot(version=self.sequence, expires=expires,
                                     meta={"targets.json": meta("targets.json")}))
        snapshot.sign(self.signers["snapshot"])
        snapshot.to_file(str(self.directory / "snapshot.json"))
        timestamp = Metadata(Timestamp(version=self.sequence, expires=expires,
                                       snapshot_meta=meta("snapshot.json")))
        timestamp.sign(self.signers["timestamp"])
        timestamp.to_file(str(self.directory / "timestamp.json"))
        return descriptor

    def fetcher(self, directory, cancel, progress):
        repo = self

        class LocalFetcher(HTTPSFetcher):
            def _fetch(self, url):
                validate_url(url)
                repo.requests.append(url)
                path = repo.directory / url.rsplit("/", 1)[-1]
                if not path.is_file():
                    raise exceptions.DownloadHTTPError("Fixture not found", 404)
                data = path.read_bytes()
                for offset in range(0, len(data), 200):
                    if cancel.is_set() or (repo.interrupt and path.suffix == ".exe" and offset > 0):
                        raise exceptions.DownloadError("Interrupted fixture")
                    block = data[offset:offset + 200]
                    if self.expected:
                        self.progress({"transferred": min(offset + 200, len(data)),
                                       "total": len(data), "speed": 1000})
                    yield block

        return LocalFetcher(directory, cancel, progress)

    def client(self, directory, **kwargs):
        return UpdateService(directory, bootstrap=self.bootstrap, current="1.4.2",
                             public="1.1.0", fetcher_factory=self.fetcher, **kwargs)


@pytest.fixture
def repo(tmp_path):
    return Repository(tmp_path / "repository")


def test_signed_download_progress_restart_reverification_and_no_downgrade(repo, tmp_path):
    service = repo.client(tmp_path / "client")
    release = service.check(Event())
    assert release.build_version == "1.4.3" and release.size > 0
    progress = []
    service.download(release, Event(), progress.append)
    assert progress[-1]["transferred"] == release.size and progress[-1]["speed"] > 0
    restored = repo.client(tmp_path / "client")
    assert restored.verified_staged()[0] == release
    newer = UpdateService(tmp_path / "newer", bootstrap=repo.bootstrap, current="1.4.4",
                         public="1.1.0", fetcher_factory=repo.fetcher)
    assert newer.check(Event()) is None
    repo.publish(build="1.4.1")
    assert service.check(Event()) is None


@pytest.mark.parametrize("wrong_key,expired", [(True, False), (False, True)])
def test_invalid_signatures_and_expiry_never_offer_a_package(repo, tmp_path, wrong_key, expired):
    repo.publish(wrong_key=wrong_key, expired=expired)
    service = repo.client(tmp_path / "client")
    with pytest.raises(UpdateError, match="verification failed"):
        service.check(Event())
    assert not list(service.targets.glob("*.exe"))


def test_corrupted_download_and_postponed_package_are_rejected(repo, tmp_path):
    service = repo.client(tmp_path / "client")
    release = service.check(Event())
    source = repo.directory / release.installer
    content = source.read_bytes()
    source.write_bytes(content[:-1] + b"!")
    with pytest.raises(UpdateError, match="verification failed"):
        service.download(release, Event())
    assert not (service.targets / release.installer).exists()
    source.write_bytes(content)
    service.download(release, Event())
    (service.targets / release.installer).write_bytes(b"tampered later")
    with pytest.raises(UpdateError, match="verification failed"):
        service.verified_staged()


def test_interrupted_download_retry_and_cancel_leave_no_installable_partial(repo, tmp_path):
    service = repo.client(tmp_path / "client")
    release = service.check(Event())
    repo.interrupt = True
    with pytest.raises(UpdateError, match="interrupted"):
        service.download(release, Event())
    assert not (service.targets / release.installer).exists()
    repo.interrupt = False
    assert service.download(release, Event()) == release
    cancelled = Event()
    cancelled.set()
    with pytest.raises(UpdateError, match="cancelled"):
        service.check(cancelled)


def test_rollback_of_previously_seen_metadata_is_rejected(repo, tmp_path):
    service = repo.client(tmp_path / "client")
    previous = {p.name: p.read_bytes() for p in repo.directory.glob("*.json")}
    service.check(Event())
    repo.publish(build="1.4.4")
    service.check(Event())
    for name, data in previous.items():
        (repo.directory / name).write_bytes(data)
    with pytest.raises(UpdateError, match="verification failed"):
        service.check(Event())


@pytest.mark.parametrize("changes", [
    {"installer": "../evil.exe"}, {"installer": "C:\\evil.exe"},
    {"app_id": "another-publisher"}, {"platform": "ipados"},
    {"installer_kind": "arbitrary-exe"}, {"build_version": "1.4.3-rc1"},
    {"tag": "../../../outside"}, {"schema": True}, {"data_schema": 6},
])
def test_even_signed_incompatible_descriptors_are_rejected(repo, tmp_path, changes):
    repo.publish(changes=changes)
    with pytest.raises(UpdateError):
        repo.client(tmp_path / "client").check(Event())


@pytest.mark.parametrize("url", [
    "http://github.com/zx-divine/NEXIS/releases/latest/download/root.json",
    "https://github.com.evil.test/zx-divine/NEXIS/releases/latest/download/root.json",
    "https://github.com/attacker/NEXIS/releases/latest/download/root.json",
    METADATA_URL + "../evil.exe", METADATA_URL + "%2e%2e.exe",
    METADATA_URL + "root.json?url=elsewhere", METADATA_URL + "root.json#fragment",
    "https://user:password@github.com/zx-divine/NEXIS/releases/latest/download/root.json",
    "https://release-assets.githubusercontent.com/file.exe",
])
def test_https_source_and_path_policy(url):
    with pytest.raises(UpdateError):
        validate_url(url)


def test_offline_missing_feed_low_storage_and_duplicate_operation(repo, tmp_path, monkeypatch):
    service = repo.client(tmp_path / "client")
    with operation_lock(service.directory), pytest.raises(UpdateError, match="already running"):
        service.check(Event())
    release = service.check(Event())
    monkeypatch.setattr("nexis.core.update_service.shutil.disk_usage", lambda path: SimpleNamespace(free=0))
    with pytest.raises(UpdateError, match="storage"):
        service.download(release, Event())
    (repo.directory / "timestamp.json").unlink()
    with pytest.raises(UpdateError, match="No signed update feed"):
        repo.client(tmp_path / "missing").check(Event())


def test_snapshot_preserves_entire_profile_and_consistent_database(db, tmp_path):
    profile = db.path.parent
    db.set_setting("preferred_name", "Update fixture")
    db.set_setting("theme", "matrix")
    (profile / "providers.dpapi").write_bytes(b"Opaque protected provider fixture")
    (profile / "plugins").mkdir()
    (profile / "plugins/custom.dat").write_bytes(b"Keep user file")
    destination = profile / "updates/backups/fixture"
    before = db.export()
    snapshot_profile(profile, db, destination)
    assert db.export() == before
    assert (destination / "providers.dpapi").read_bytes() == (profile / "providers.dpapi").read_bytes()
    assert (destination / "plugins/custom.dat").read_bytes() == b"Keep user file"
    assert not (destination / "updates").exists()
    import sqlite3

    with sqlite3.connect(destination / db.path.name) as backup:
        assert backup.execute("PRAGMA quick_check").fetchone()[0] == "ok"
        assert json.loads(backup.execute("SELECT value FROM settings WHERE key='preferred_name'").fetchone()[0]) == "Update fixture"


def test_tampered_package_never_reaches_installer_execution(repo, tmp_path, monkeypatch):
    service = repo.client(tmp_path / "client")
    release = service.check(Event())
    service.download(release, Event())
    (service.targets / release.installer).write_bytes(b"changed")
    service.record(phase="prepared")
    monkeypatch.setattr("nexis.platform.update_install.registered_directory", lambda app_id: tmp_path)
    monkeypatch.setattr("nexis.platform.update_install.subprocess.run", lambda *a, **k: pytest.fail("Tampered payload executed"))
    assert WindowsInstaller(service, tmp_path).apply(lambda: True) == 1
    assert service.read_state()["phase"] == "install_failed"


def test_semantic_numeric_comparison():
    assert semver("1.10.0") > semver("1.9.99")
    with pytest.raises(UpdateError):
        semver("01.1.0")


def test_installer_failure_retains_recovery_and_allows_retry(repo, tmp_path, monkeypatch):
    service = repo.client(tmp_path / "client")
    service.download(service.check(Event()), Event())
    service.record(phase="prepared", backup="retained-snapshot", runner="retained-program")
    monkeypatch.setattr("nexis.platform.update_install.registered_directory", lambda app_id: tmp_path)
    monkeypatch.setattr("nexis.platform.update_install.installed_build", lambda directory: "1.4.2")
    commands = []

    def failed(command, **kwargs):
        commands.append((command, kwargs))
        return SimpleNamespace(returncode=5)

    monkeypatch.setattr("nexis.platform.update_install.subprocess.run", failed)
    assert WindowsInstaller(service, tmp_path).apply(lambda: True) == 1
    state = service.read_state()
    assert state["phase"] == "install_failed" and "code 5" in state["error"]
    assert state["backup"] == "retained-snapshot" and state["runner"] == "retained-program"
    assert len(commands) == 1 and not commands[0][1].get("shell")
    assert "/NORESTART" in commands[0][0]
    assert "/NOCLOSEAPPLICATIONS" in commands[0][0]
    # A retry starts from newly verified state; failed installation never acknowledges success.
    assert service.download(service.check(Event()), Event())
    assert service.read_state()["phase"] == "ready"


def test_explicit_data_erasure_includes_snapshots_but_denial_erases_nothing(db, platform):
    from nexis.core.management import Management
    from nexis.core.permissions import Permissions

    private = db.path.parent / "updates/backups/fixture/private.txt"
    private.parent.mkdir(parents=True)
    private.write_text("Synthetic recovery data")
    db.set_setting("preferred_name", "Keep until authorized")
    with pytest.raises(ValueError):
        Management(db, platform, Permissions(lambda preview: False)).delete_all()
    assert private.exists() and db.setting("preferred_name") == "Keep until authorized"
    Management(db, platform, Permissions(lambda preview: True)).delete_all()
    assert not private.exists() and not db.setting("preferred_name")


def test_recovery_erasure_refuses_windows_junctions(db, tmp_path):
    import os
    import subprocess
    from nexis.core.update_service import erase_recovery

    if os.name != "nt":
        pytest.skip("Windows junction containment")
    outside = tmp_path / "outside-fixture"
    outside.mkdir()
    (outside / "keep.txt").write_text("Must survive")
    cache = db.path.parent / "updates"
    cache.mkdir()
    junction = cache / "unexpected-link"
    result = subprocess.run(["cmd", "/c", "mklink", "/J", str(junction), str(outside)], capture_output=True)
    if result.returncode:
        pytest.skip("Windows junction creation unavailable")
    with pytest.raises(UpdateError, match="contains a link"):
        erase_recovery(cache)
    assert (outside / "keep.txt").read_text() == "Must survive"
