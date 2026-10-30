"""Derive release artwork from ASH's approved source, without redrawing it.

Pillow is a build-only dependency. Runtime branding uses Qt alone.
Run from any directory; the approved original is never written to.
"""

import hashlib
import json
from pathlib import Path
import shutil

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "NEXIS LOGO.png"
SOURCE_SHA256 = "cee617446391da8bf0f3d348f96e0f629e11aa8c9dc9e30356c577d721794b4c"
# Pixel bounds exclude the wordmark while retaining the approved N and its glow.
SYMBOL_CROP = (265, 155, 995, 855)
SIZES = (16, 20, 24, 32, 40, 48, 64, 96, 128, 256)
PNG_SIZES = (*SIZES, 512)
PACKAGE_ASSETS = ("NEXIS_logo.png", "NEXIS_symbol.png", "NEXIS.ico")


def generate(root=ROOT):
    directory = root / "assets/branding"
    source = directory / SOURCE
    original = source.read_bytes()
    digest = hashlib.sha256(original).hexdigest()
    if digest != SOURCE_SHA256:
        raise ValueError("Approved source hash changed; owner review required before regenerating")
    records = []

    def record(path, role, dimensions=None):
        row = {"file": path.relative_to(directory).as_posix(), "role": role,
               "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        if dimensions:
            row["pixels"] = list(dimensions)
        records.append(row)

    with Image.open(source) as image:
        if image.size != (1254, 1254):
            raise ValueError("Unexpected approved source dimensions")
        full = image.convert("RGB")
        cropped = full.crop(SYMBOL_CROP)
        symbol = ImageOps.pad(cropped, (730, 730), color="black",
                              method=Image.Resampling.LANCZOS)
        shutil.copyfile(source, directory / "NEXIS_logo.png")
        record(source, "approved original, unchanged", full.size)
        record(directory / "NEXIS_logo.png", "runtime full artwork, byte-identical", full.size)
        symbol.resize((512, 512), Image.Resampling.LANCZOS).save(directory / "NEXIS_symbol.png")
        record(directory / "NEXIS_symbol.png", "runtime N symbol", (512, 512))
        scaled = directory / "scaled"
        scaled.mkdir(exist_ok=True)
        for size in PNG_SIZES:
            path = scaled / f"NEXIS-symbol-{size}.png"
            symbol.resize((size, size), Image.Resampling.LANCZOS).save(path)
            record(path, "N symbol for shell and release assets", (size, size))
        for size in (128, 256, 512, 1024):
            path = scaled / f"NEXIS-logo-{size}.png"
            full.resize((size, size), Image.Resampling.LANCZOS).save(path)
            record(path, "full artwork for documentation and release assets", (size, size))
        icon = directory / "NEXIS.ico"
        symbol.save(icon, format="ICO", sizes=[(size, size) for size in SIZES])
        with Image.open(icon) as generated:
            if generated.ico.sizes() != {(size, size) for size in SIZES}:
                raise ValueError("Incomplete Windows icon frames")
        record(icon, "Windows multi-resolution N symbol")
        # Inno Setup preserves a 164:314 sidebar area at every display scale.
        sidebar = Image.new("RGB", (492, 942), "black")
        sidebar.paste(full.resize((492, 492), Image.Resampling.LANCZOS), (0, 225))
        sidebar.save(directory / "installer-sidebar.png")
        record(directory / "installer-sidebar.png", "installer full artwork sidebar", sidebar.size)

    package = root / "src/nexis/assets/branding"
    package.mkdir(parents=True, exist_ok=True)
    for name in PACKAGE_ASSETS:
        shutil.copyfile(directory / name, package / name)
    if source.read_bytes() != original:
        raise ValueError("Approved original changed during generation")
    manifest = {"source": SOURCE, "source_sha256": digest, "symbol_crop": list(SYMBOL_CROP),
                "icon_sizes": list(SIZES), "assets": records}
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    result = generate()
    print(f"Approved original preserved; generated {len(result['assets']) - 1} assets.")
    print("ICO frames:", ", ".join(map(str, SIZES)))
