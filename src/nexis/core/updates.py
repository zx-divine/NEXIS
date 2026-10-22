"""Official GitHub metadata discovery and explicit local checksum verification only."""

import hashlib
import json
from pathlib import Path
import re
from time import monotonic
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, unquote
from urllib.request import Request, build_opener

from nexis import __version__, PUBLIC_VERSION, RELEASE_CHANNEL
from nexis.core.providers import RejectRedirect

API = "https://api.github.com/repos/zx-divine/nexis/releases/latest"
_VERSION = re.compile(r"v?(0|[1-9][0-9]{0,8})\.(0|[1-9][0-9]{0,8})\.(0|[1-9][0-9]{0,8})\Z")


def version(value):
    match = _VERSION.fullmatch(value) if isinstance(value, str) else None
    if not match:
        raise ValueError("The release does not use a supported stable semantic version.")
    return tuple(int(part) for part in match.groups())


def official_url(value, tag, asset=False):
    if not isinstance(value, str) or len(value) > 2048 or any(c.isspace() or ord(c) < 32 for c in value):
        raise ValueError("Invalid official release destination.")
    parsed = urlsplit(value)
    parts = unquote(parsed.path).strip("/").split("/")
    if (parsed.scheme != "https" or parsed.hostname != "github.com" or parsed.username
            or parsed.password or parsed.port is not None or parsed.query or parsed.fragment
            or "//" in parsed.path
            or len(parts) != (6 if asset else 5) or [p.casefold() for p in parts[:3]] != ["zx-divine", "nexis", "releases"]
            or parts[3] != ("download" if asset else "tag") or parts[4] != tag
            or any(p in {".", ".."} or "\\" in p for p in parts)):
        raise ValueError("Updates must point to this project's official GitHub release.")
    if asset and (not re.fullmatch(r"[A-Za-z0-9_.()-]{1,180}", parts[5]) or Path(parts[5]).suffix.casefold() not in {".exe", ".zip"}):
        raise ValueError("Unsupported release asset filename.")
    return value


def parse_release(data, current=None):
    if not isinstance(data, dict) or data.get("draft") is not False or data.get("prerelease") is not False:
        raise ValueError("No supported public stable release was returned.")
    tag = data.get("tag_name")
    latest = version(tag)
    page = official_url(data.get("html_url"), tag)
    notes = data.get("body") or "No release notes provided."
    if not isinstance(notes, str) or not isinstance(data.get("assets", []), list):
        raise ValueError("The release metadata is malformed.")
    assets = []
    for entry in data.get("assets", [])[:20]:
        try:
            url = official_url(entry.get("browser_download_url"), tag, True)
            size = entry.get("size")
            if entry.get("state") != "uploaded" or type(size) is not int or not 0 < size <= 2 * 1024**3:
                continue
            digest = entry.get("digest") or ""
            digest = digest[7:].lower() if isinstance(digest, str) and re.fullmatch(r"sha256:[a-fA-F0-9]{64}", digest) else ""
            assets.append({"name": unquote(urlsplit(url).path).split("/")[-1], "url": url, "bytes": size, "sha256": digest})
        except (ValueError, AttributeError):
            continue
    # Public v1.0.0 follows internal engineering 1.3.x. Compare public versions,
    # and offer the stable build to a candidate of that same public version.
    baseline = version(PUBLIC_VERSION if current is None else current)
    available = latest > baseline or (
        current is None and RELEASE_CHANNEL != "stable" and latest == baseline
    )
    return {"available": available, "tag": tag, "page": page,
            "notes": notes[:12000], "assets": assets}


def check_updates(cancel, opener=None, current=None):
    if cancel.is_set():
        raise ValueError("Update check cancelled.")
    request = Request(API, headers={"Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "NEXIS-Desktop/" + __version__})
    try:
        with (opener or build_opener(RejectRedirect()).open)(request, timeout=8) as response:
            chunks, size, deadline = [], 0, monotonic() + 15
            while chunk := response.read(32768):
                if cancel.is_set():
                    raise ValueError("Update check cancelled.")
                if monotonic() > deadline:
                    raise ValueError("Update metadata timed out. The application remains usable.")
                size += len(chunk)
                if size > 1024 * 1024:
                    raise ValueError("Update metadata exceeded its size bound.")
                chunks.append(chunk)
        return parse_release(json.loads(b"".join(chunks)), current)
    except HTTPError as exc:
        code = exc.code
        exc.close()
        if code == 404:
            return {"available": False, "tag": "", "page": "", "notes": "No public stable release is available. Download links remain disabled.", "assets": []}
        if code in {403, 429}:
            raise ValueError("GitHub denied or rate-limited the update check. Retry later; no account or token is required.") from None
        raise ValueError(f"GitHub returned HTTP {code}. Retry later; no update was installed.") from None
    except (URLError, OSError, TimeoutError):
        raise ValueError("The official update service could not be reached. NEXIS remains usable; retry when connected.") from None
    except (json.JSONDecodeError, UnicodeError):
        raise ValueError("The official update response was invalid. No download or installation was started.") from None


def verify_download(path, expected, cancel):
    if not re.fullmatch(r"[a-fA-F0-9]{64}", expected):
        raise ValueError("This release has no valid SHA-256 metadata to compare.")
    path = Path(path)
    if str(path).startswith(("\\\\", "//")) or path.is_symlink() or not path.is_file() or path.stat().st_size > 2 * 1024**3:
        raise ValueError("Choose the regular downloaded file under 2 GB.")
    before = path.stat()
    digest, deadline, size = hashlib.sha256(), monotonic() + 120, 0
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            size += len(block)
            if size > 2 * 1024**3:
                raise ValueError("The selected file exceeded the 2 GB verification bound.")
            if cancel.is_set() or monotonic() > deadline:
                raise ValueError("Local checksum verification cancelled or timed out.")
            digest.update(block)
    after = path.stat()
    if cancel.is_set() or (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError("The file changed or verification was cancelled; do not use this result.")
    actual = digest.hexdigest()
    return {"matches": actual == expected.lower(), "sha256": actual}
