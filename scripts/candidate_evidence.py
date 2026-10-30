"""Source fingerprint shared by regression and isolated development builds."""

import hashlib
from pathlib import Path
from runtime_ssl import ssl_runtime_data

ROOT = Path(__file__).resolve().parents[1]


def fingerprint():
    paths = set()
    for directory in ("src", "tests", "scripts"):
        paths.update(path for path in (ROOT / directory).rglob("*") if path.suffix in {".py", ".qss"})
    paths.update(path for path in (ROOT / "assets/licenses").rglob("*") if path.is_file())
    paths.update(path for path in (ROOT / "assets/release").rglob("*") if path.is_file())
    paths.update(path for path in (ROOT / "installer").rglob("*.iss") if path.is_file())
    paths.update(path for path in (ROOT / "tests/installer").rglob("*.iss") if path.is_file())
    for directory in ("assets/branding", "src/nexis/assets/branding"):
        paths.update(path for path in (ROOT / directory).rglob("*") if path.is_file())
    paths.update(ROOT / value for value in (
        "NEXIS.spec", "pyproject.toml", "requirements.txt", "requirements-dev.txt",
        "installer/NEXIS.iss", "scripts/version.txt", "assets/models/manifest.json",
        "assets/branding/NEXIS_logo.png", "assets/branding/NEXIS.ico", "assets/RELEASE_CHANNEL.txt", "LICENSE",
        "README.md", "requirements-verified.txt", "docs/BRANDING.md", "docs/ASCENSION_BASELINE.md",
        "src/nexis/assets/updates/root.json",
        "docs/ASCENSION_DEVELOPMENT.md", "docs/ASCENSION_OWNER_CHECKLIST.md", "docs/ASCENSION_HANDOFF.md", "docs/ASCENSION_FREEDOM_GUIDE.md",
    ))
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(path.relative_to(ROOT).as_posix().encode() + b"\0" + path.read_bytes())
    for filename, _ in ssl_runtime_data():
        resource = Path(filename)
        digest.update(b"interpreter_tls_policy/" + resource.name.encode() + b"\0" + resource.read_bytes())
    return digest.hexdigest()
