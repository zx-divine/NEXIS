"""Release identity cannot silently diverge between source and packaging."""

from pathlib import Path
import tomllib

from nexis import __version__, DISPLAY_VERSION, PUBLIC_NAME, PUBLIC_VERSION, RELEASE_CHANNEL


def test_candidate_identity_matches_packaging_and_preserves_history():
    root = Path(__file__).resolve().parents[2]
    assert tomllib.loads((root / "pyproject.toml").read_text())["project"]["version"] == __version__
    assert tuple(map(int, __version__.split("."))) > (1, 3, 3)
    assert RELEASE_CHANNEL == "development" and PUBLIC_VERSION == "1.1.0"
    assert PUBLIC_NAME == "Nexis v1"
    display_number = __version__[:-2] if __version__.endswith(".0") else __version__
    assert DISPLAY_VERSION.startswith("v" + display_number + " Development Candidate")
    assert "Candidate" in DISPLAY_VERSION and __version__ in DISPLAY_VERSION
    assert "Stable" not in DISPLAY_VERSION
    metadata = (root / "scripts/version.txt").read_text()
    assert "StringStruct('FileVersion', '" + __version__ + "')" in metadata
    assert "StringStruct('ProductVersion', '" + DISPLAY_VERSION + "')" in metadata
    installer = (root / "installer/NEXIS.iss").read_text()
    assert 'GetStringFileInfo(AddBackslash(AppSourceDir) + "NEXIS.exe", "ProductVersion")' in installer
    assert "VersionInfoProductTextVersion={#AppDisplayVersion}" in installer
    assert "VersionInfoTextVersion={#AppVersion}" in installer


def test_ca_bundle_security_floor_is_installed_and_declared():
    import certifi
    from importlib.metadata import version

    # GHSA-6q48-6c7w-9gw2 / PYSEC-2026-4320: replaced CA trust bundle.
    assert certifi.__version__ == version("certifi") == "2026.10.19"
    root = Path(__file__).resolve().parents[2]
    assert "certifi==2026.10.19" in (root / "requirements.txt").read_text()
