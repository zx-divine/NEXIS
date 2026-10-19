import hashlib
import io
import json
from pathlib import Path
import sys
from threading import Event
import zipfile

import pytest

from nexis.core.catalog import Catalog
from nexis.core.models import MODEL, safe_extract, install_model, Cancelled
from nexis.core.providers import ProviderStore, endpoint, list_models, chat, validate_profile
from nexis.core.router import Engine
from nexis.core.permissions import Permissions
from nexis.core.websites import resolve_website
from nexis.platform.discovery import Application, deduplicate, verified_exe, valid_app_id
from nexis.platform.speech import default_input
from nexis.storage.database import Database


def pe_file(path):
    binary = bytearray(128)
    binary[:2] = b"MZ"
    binary[60:64] = (64).to_bytes(4, "little")
    binary[64:68] = b"PE\0\0"
    path.write_bytes(binary)
    return path


def test_catalog_dedup_unicode_and_missing(tmp_path, db):
    exe = pe_file(tmp_path / "音乐.exe")
    app = Application.create("音乐播放器", str(exe), "exe", "Start Menu")
    assert len(deduplicate([app, app])) == 1
    catalog = Catalog(db)
    catalog.update([app.__dict__])
    assert catalog.matches("音乐播放器")[0]["target"] == str(exe.resolve())
    catalog.preferences(app.id, "音乐", hidden=True)
    assert not catalog.matches("音乐")
    catalog.preferences(app.id, "音乐")
    assert catalog.matches("音乐")
    exe.unlink()
    with pytest.raises(OSError):
        verified_exe(str(exe))
    catalog.update([])
    assert not catalog.matches("音乐")


def test_full_unicode_display_names_route_without_shell_parsing(tmp_path, db, platform):
    app = Application.create(
        "🚀 音乐 & Books", str(pe_file(tmp_path / "music.exe")), "exe", "Start Menu"
    )
    Catalog(db).update([app.__dict__])
    assert (
        Engine(db, platform, Permissions(lambda preview: True)).execute("open 🚀 音乐 & Books").ok
    )


def test_discovery_rejects_interpreters_fake_exes_and_unsafe_ids(tmp_path):
    for title in ("cmd.exe", "powershell.exe", "uninstall.exe"):
        with pytest.raises(ValueError):
            Application.create(title, str(pe_file(tmp_path / title)), "exe", "test")
    fake = tmp_path / "fake.exe"
    fake.write_text("not executable")
    with pytest.raises(ValueError):
        verified_exe(str(fake))
    assert valid_app_id("Microsoft.WindowsCalculator_8wekyb3d8bbwe!App")
    assert not valid_app_id("shell:AppsFolder\\bad & calc")


def test_discovered_apps_still_require_permission_and_revalidate(tmp_path, db, platform):
    exe = pe_file(tmp_path / "chrome.exe")
    app = Application.create("Google Chrome", str(exe), "exe", "Start Menu")
    Catalog(db).update([app.__dict__])
    assert not Engine(db, platform).execute("open Chrome").ok
    assert not platform.calls
    assert Engine(db, platform, Permissions(lambda preview: True)).execute("open Chrome").ok
    exe.unlink()
    assert not Engine(db, platform, Permissions(lambda preview: True)).execute("open Chrome").ok


@pytest.mark.parametrize("text", ["YouTube", "GitHub", "Wikipedia", "Google"])
def test_curated_websites(text, db, platform):
    value, confirm = resolve_website(text)
    assert value.startswith("https://") and not confirm
    assert Engine(db, platform).execute("open " + text).ok
    assert platform.calls[-1][0] == "website"


@pytest.mark.parametrize(
    "text",
    [
        "http://example.com",
        "javascript:alert(1)",
        "file:///C:/Windows",
        "data:text/plain,x",
        "example.com",
        "https://u:p@example.com",
    ],
)
def test_unsafe_or_invented_destinations_rejected(text):
    with pytest.raises(ValueError):
        resolve_website(text)


def test_unknown_domain_needs_confirmation_and_saved_shortcut_wins(db, platform):
    assert not Engine(db, platform).execute("open https://example.com").ok
    assert not platform.calls
    assert (
        Engine(db, platform, Permissions(lambda preview: True))
        .execute("open https://example.com")
        .ok
    )
    db.execute(
        "INSERT OR REPLACE INTO shortcuts VALUES (?,?,?)",
        ("youtube", "website", "https://www.youtube.com/feed/subscriptions"),
    )
    Engine(db, platform).execute("open youtube")
    assert platform.calls[-1][1].endswith("/feed/subscriptions")


@pytest.mark.parametrize(
    "path", ["../escape", "/absolute", "C:/escape", "x\\..\\escape", "folder./bad"]
)
def test_model_zip_paths_rejected(tmp_path, path):
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as archive:
        archive.writestr(path, b"bad")
    data.seek(0)
    with pytest.raises(ValueError):
        safe_extract(data, tmp_path, Event())


def test_model_zip_symlink_and_cancellation(tmp_path):
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as archive:
        info = zipfile.ZipInfo("link")
        info.external_attr = 0o120777 << 16
        archive.writestr(info, "target")
    data.seek(0)
    with pytest.raises(ValueError):
        safe_extract(data, tmp_path, Event())
    cancel = Event()
    cancel.set()
    with pytest.raises(Cancelled):
        install_model(tmp_path, cancel, consent=True)
    with pytest.raises(ValueError, match="Consent"):
        install_model(tmp_path, Event())


class Response(io.BytesIO):
    def __init__(self, data, status=200, headers=None):
        super().__init__(data)
        self.status, self.headers = status, headers or {}

    def geturl(self):
        return MODEL["url"]

    def read1(self, size):
        return self.read(size)


def fixture_model(monkeypatch):
    monkeypatch.setattr("nexis.core.models.validate_model", lambda path: None)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for item in ("am/final.mdl", "conf/model.conf", "graph/HCLr.fst", "graph/Gr.fst"):
            archive.writestr(MODEL["id"] + "/" + item, b"model fixture")
    binary = buffer.getvalue()
    monkeypatch.setitem(MODEL, "size", len(binary))
    monkeypatch.setitem(MODEL, "sha256", hashlib.sha256(binary).hexdigest())
    return binary


def test_model_download_integrity_activation_and_resume(tmp_path, monkeypatch):
    binary = fixture_model(monkeypatch)
    cache = tmp_path / "model-downloads"
    cache.mkdir()
    (cache / (MODEL["id"] + ".zip.part")).write_bytes(binary[:40])

    def opener(req, timeout):
        assert req.headers["Range"] == "bytes=40-"
        return Response(
            binary[40:], 206, {"Content-Range": f"bytes 40-{len(binary) - 1}/{len(binary)}"}
        )

    path = install_model(tmp_path, Event(), consent=True, opener=opener)
    assert (Path(path) / "am/final.mdl").is_file()
    assert not list((tmp_path / "models").glob(".speech-*"))


def test_model_corruption_rejected(tmp_path, monkeypatch):
    binary = fixture_model(monkeypatch)
    with pytest.raises(ValueError, match="integrity"):
        install_model(
            tmp_path, Event(), consent=True, opener=lambda *a, **k: Response(b"x" * len(binary))
        )
    assert not (tmp_path / "models" / MODEL["id"]).exists()


def test_interrupted_download_is_retained_for_retry(tmp_path, monkeypatch):
    binary = fixture_model(monkeypatch)

    class Interrupted(Response):
        calls = 0

        def read(self, size):
            self.calls += 1
            if self.calls > 1:
                raise OSError("offline")
            return super().read(40)

    with pytest.raises(OSError):
        install_model(tmp_path, Event(), consent=True, opener=lambda *a, **k: Interrupted(binary))
    part = tmp_path / "model-downloads" / (MODEL["id"] + ".zip.part")
    assert part.stat().st_size == 40


def test_default_audio_selection_and_missing_microphone():
    class Devices:
        def query_devices(self, kind=None):
            if kind:
                return {"name": "Default USB", "default_samplerate": 48000}
            return [{"name": "USB", "max_input_channels": 1}]

    assert default_input(Devices())[0] is None
    assert default_input(Devices(), "USB")[0] == 0
    assert default_input(Devices(), "Removed device")[1]["name"] == "Default USB"

    class Missing:
        def query_devices(self, **kwargs):
            raise OSError("No microphone")

    with pytest.raises(OSError):
        default_input(Missing())


def profile():
    return {
        "provider": "OpenRouter",
        "endpoint": "https://openrouter.ai/api/v1",
        "key": "TEST-SECRET-DO-NOT-LOG",
        "model": "fixture",
    }


def test_windows_credentials_persist_encrypted_and_corruption_preserved(tmp_path):
    if sys.platform != "win32":
        pytest.skip("Windows DPAPI test")
    store = ProviderStore(tmp_path)
    store.save(profile())
    assert profile()["key"].encode() not in store.path.read_bytes()
    assert ProviderStore(tmp_path).load()["key"] == profile()["key"]
    store.path.write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="preserved"):
        store.load()
    assert store.path.read_bytes() == b"corrupt"


@pytest.mark.parametrize(
    "address",
    [
        "http://example.com/v1",
        "https://key:secret@example.com",
        "https://example.com?key=x",
        "file:///tmp",
        "https://x\r\nInjected:x",
    ],
)
def test_provider_unsafe_endpoints(address):
    with pytest.raises(ValueError):
        endpoint(address)


def test_provider_models_response_and_secret_redaction():
    models = list_models(
        profile(),
        Event(),
        opener=lambda *a, **k: Response(json.dumps({"data": [{"id": "test"}]}).encode()),
    )
    assert models == ["test"]
    result = chat(
        profile(),
        "hello",
        Event(),
        opener=lambda *a, **k: Response(
            json.dumps({"choices": [{"message": {"content": profile()["key"]}}]}).encode()
        ),
    )
    assert result == "[redacted]"
    bad = profile() | {"headers": {"Host": "bad"}}
    with pytest.raises(ValueError):
        validate_profile(bad)


def test_provider_cancellation_never_sends_request():
    cancel = Event()
    cancel.set()
    with pytest.raises(ValueError, match="cancelled"):
        list_models(
            profile(), cancel, opener=lambda *a, **k: pytest.fail("Network accessed after cancel")
        )


def test_schema_one_migration_is_additive_and_idempotent(tmp_path):
    path = tmp_path / "legacy.db"
    old = Database(path)
    old.set_setting("history_enabled", False)
    old.execute("INSERT INTO snippets VALUES ('keep','legacy','preserved')")
    old.execute("DROP TABLE app_catalog")
    old.execute("DROP TABLE app_preferences")
    old.execute("PRAGMA user_version=1")
    old.close()
    for _ in range(2):
        upgraded = Database(path)
        assert upgraded.rows("PRAGMA user_version")[0]["user_version"] == 3
        assert not upgraded.setting("history_enabled")
        assert upgraded.rows("SELECT text FROM snippets")[0]["text"] == "preserved"
        upgraded.close()
