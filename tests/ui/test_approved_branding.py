"""The owner-approved source, N-only shell assets and DPI presentation contract."""

import hashlib
import importlib.util
import json
from pathlib import Path
import shutil

from PIL import Image, ImageChops
import pytest
from PySide6.QtCore import QEvent

from nexis.branding import asset
from nexis.ui.branding import BrandLogo, brand_pixmap

ROOT = Path(__file__).resolve().parents[2]
APPROVED_SHA256 = "cee617446391da8bf0f3d348f96e0f629e11aa8c9dc9e30356c577d721794b4c"


def generator():
    spec = importlib.util.spec_from_file_location("approved_branding", ROOT / "scripts/prepare_branding.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_approved_artwork_identity_and_asset_manifest():
    directory = ROOT / "assets/branding"
    original = (directory / "NEXIS LOGO.png").read_bytes()
    assert hashlib.sha256(original).hexdigest() == APPROVED_SHA256
    assert original == asset("NEXIS_logo.png").read_bytes()
    manifest = json.loads((directory / "manifest.json").read_text())
    assert manifest["source_sha256"] == APPROVED_SHA256
    for row in manifest["assets"]:
        path = directory / row["file"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row["sha256"]
        if "pixels" in row:
            with Image.open(path) as image:
                assert list(image.size) == row["pixels"]
                image.verify()
    for name in generator().PACKAGE_ASSETS:
        assert (directory / name).read_bytes() == asset(name).read_bytes()


def test_icon_frames_use_symbol_instead_of_whole_wordmark():
    with Image.open(asset("NEXIS.ico")) as icon, Image.open(asset("NEXIS_logo.png")) as full:
        assert icon.ico.sizes() == {(s, s) for s in (16, 20, 24, 32, 40, 48, 64, 96, 128, 256)}
        for size in icon.ico.sizes():
            frame = icon.ico.getimage(size).convert("RGB")
            # The full source's wide gold wordmark is absent from every icon frame.
            whole_logo = full.convert("RGB").resize(size, Image.Resampling.LANCZOS)
            assert ImageChops.difference(frame, whole_logo).getbbox()
            assert max(frame.getextrema()[0]) > 100
        large = icon.ico.getimage((256, 256)).convert("RGB")
        # Bright approved N edges fill the crop, rather than sitting above a wordmark.
        assert large.getpixel((128, 130))[0] > 100


def test_generation_is_repeatable_and_preserves_original(tmp_path):
    directory = tmp_path / "assets/branding"
    directory.mkdir(parents=True)
    original = ROOT / "assets/branding/NEXIS LOGO.png"
    shutil.copyfile(original, directory / original.name)
    first = generator().generate(tmp_path)
    assert generator().generate(tmp_path) == first
    assert (directory / original.name).read_bytes() == original.read_bytes()


def test_unapproved_source_is_rejected_before_writing(tmp_path):
    directory = tmp_path / "assets/branding"
    directory.mkdir(parents=True)
    (directory / "NEXIS LOGO.png").write_bytes(b"unapproved artwork")
    with pytest.raises(ValueError, match="Approved source hash changed"):
        generator().generate(tmp_path)
    assert {path.name for path in directory.iterdir()} == {"NEXIS LOGO.png"}


@pytest.mark.parametrize("ratio", (1.0, 1.5, 2.0, 3.0))
@pytest.mark.parametrize("symbol", (False, True))
def test_pixmap_keeps_logical_size_at_display_scale(qapp, ratio, symbol):
    image = brand_pixmap(128, ratio, symbol=symbol)
    assert not image.isNull()
    assert image.width() == round(128 * ratio)
    assert image.devicePixelRatio() == ratio
    assert image.deviceIndependentSize().width() == 128


def test_logo_refreshes_when_display_scale_changes(qtbot, monkeypatch):
    logo = BrandLogo(48, symbol=True)
    qtbot.addWidget(logo)
    rendered = []
    # QLabel.pixmap() uses the real native screen DPR, even when the Python
    # accessor is mocked. Inspect the render request for this simulated event.
    monkeypatch.setattr(logo, "devicePixelRatioF", lambda: 2.0)
    monkeypatch.setattr(logo, "setPixmap", rendered.append)
    logo.event(QEvent(QEvent.DevicePixelRatioChange))
    assert rendered[-1].width() == 96
    assert rendered[-1].devicePixelRatio() == 2.0
    assert rendered[-1].deviceIndependentSize().width() == 48


@pytest.mark.parametrize("name", ("../NEXIS.ico", "C:/other/icon.png", "NEXIS LOGO.png"))
def test_runtime_branding_only_resolves_packaged_assets(name):
    with pytest.raises(ValueError, match="Unknown branding asset"):
        asset(name)
