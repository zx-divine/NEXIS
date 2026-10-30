"""Official release metadata and local integrity tests; no installer execution."""

import hashlib
import io
import json
from threading import Event
from urllib.error import HTTPError, URLError

import pytest

from nexis.core.updates import official_url, parse_release, version, check_updates, verify_download


def release(**changes):
    return {"draft": False, "prerelease": False, "tag_name": "v1.3.9",
        "html_url": "https://github.com/zx-divine/nexis/releases/tag/v1.3.9",
        "body": "Fixture notes, never executed", "assets": [], **changes}


def test_semantic_versions_and_missing_public_release():
    assert version("v1.10.0") > version("1.9.99")
    assert parse_release(release(), "1.3.2")["available"]
    assert not parse_release(release(), "1.4.0")["available"]

    def missing(*args, **kwargs):
        raise HTTPError("https://api.github.com", 404, "not found", {}, io.BytesIO())

    result = check_updates(Event(), opener=missing)
    assert not result["available"] and not result["assets"] and not result["page"]


def test_first_public_stable_is_offered_to_internal_launch_candidate():
    # This legacy discovery helper cannot install; production uses signed build versions.
    data = release(tag_name="v1.1.0", html_url="https://github.com/zx-divine/nexis/releases/tag/v1.1.0")
    assert parse_release(data)["available"]
    assert not parse_release(data, "1.1.0")["available"]


def test_stable_channel_does_not_offer_same_public_version(monkeypatch):
    monkeypatch.setattr("nexis.core.updates.RELEASE_CHANNEL", "stable")
    data = release(tag_name="v1.0.0", html_url="https://github.com/zx-divine/nexis/releases/tag/v1.0.0")
    assert not parse_release(data)["available"]


def test_launch_candidate_never_offers_older_public_release():
    data = release(tag_name="v0.9.0", html_url="https://github.com/zx-divine/nexis/releases/tag/v0.9.0")
    assert not parse_release(data)["available"]


@pytest.mark.parametrize("url", [
    "http://github.com/zx-divine/nexis/releases/tag/v1.3.9",
    "https://github.com.evil.example/zx-divine/nexis/releases/tag/v1.3.9",
    "https://github.com/another/repo/releases/tag/v1.3.9",
    "https://github.com/zx-divine/nexis/releases/tag/v1.3.9?token=private",
    "https://github.com/zx-divine/nexis/releases/tag/../else",
    "https://github.com:443/zx-divine/nexis/releases/tag/v1.3.9",
    "https://github.com/zx-divine/nexis/releases/tag/v1.3.9#fragment",
    "https://github.com/zx-divine/nexis/releases/%2ftag/v1.3.9",
])
def test_unintended_destinations_are_rejected(url):
    with pytest.raises(ValueError):
        official_url(url, "v1.3.9")


def test_assets_need_official_location_uploaded_state_and_supported_type():
    asset = {"state": "uploaded", "size": 123, "digest": "sha256:" + "a" * 64,
             "browser_download_url": "https://github.com/zx-divine/nexis/releases/download/v1.3.9/NEXIS-Setup.exe"}
    result = parse_release(release(assets=[asset, {**asset, "browser_download_url": "https://evil.example/program.exe"},
                                           {**asset, "state": "new"}, {**asset, "size": True}]))
    assert len(result["assets"]) == 1 and result["assets"][0]["sha256"] == "a" * 64
    with pytest.raises(ValueError):
        parse_release(release(prerelease=True))


def test_check_sends_only_version_and_plain_http_headers_not_provider_credentials():
    seen = []

    def opener(request, timeout):
        seen.append(request)
        return io.BytesIO(json.dumps(release()).encode())

    assert check_updates(Event(), opener=opener)["tag"] == "v1.3.9"
    assert len(seen) == 1 and seen[0].full_url.endswith("/zx-divine/nexis/releases/latest")
    assert "authorization" not in {key.casefold() for key in seen[0].headers}
    assert seen[0].data is None


@pytest.mark.parametrize("error", [HTTPError("https://api.github.com", 429, "private", {}, io.BytesIO()), URLError("private host")])
def test_offline_and_rate_limit_failures_do_not_leak_or_install(error):
    def opener(*args, **kwargs):
        raise error

    with pytest.raises(ValueError) as raised:
        check_updates(Event(), opener=opener)
    assert "private" not in str(raised.value)


def test_local_hash_match_mismatch_and_cancel(tmp_path):
    path = tmp_path / "fixture.zip"
    path.write_bytes(b"a local fixture, not an executable")
    expected = hashlib.sha256(path.read_bytes()).hexdigest()
    assert verify_download(path, expected, Event())["matches"]
    assert not verify_download(path, "0" * 64, Event())["matches"]
    cancel = Event()
    cancel.set()
    with pytest.raises(ValueError, match="cancel"):
        verify_download(path, expected, cancel)
    assert path.read_bytes() == b"a local fixture, not an executable"
