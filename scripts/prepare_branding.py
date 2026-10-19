"""Generate Windows icon frames; copy the canonical PNG byte for byte.

Build-only dependency: Pillow. Runtime needs only Qt.
"""

from pathlib import Path
import hashlib
import shutil

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SIZES = (16, 24, 32, 48, 64, 128, 256)


def main():
    source = ROOT / "assets/branding/NEXIS_logo.png"
    target = ROOT / "assets/branding/NEXIS.ico"
    original = source.read_bytes()
    with Image.open(source) as image:
        rgba = image.convert("RGBA")
        side = max(rgba.size)
        square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
        square.paste(rgba, ((side - rgba.width) // 2, (side - rgba.height) // 2))
        square.save(target, format="ICO", sizes=[(s, s) for s in SIZES])
    with Image.open(target) as icon:
        assert icon.ico.sizes() == {(s, s) for s in SIZES}
    package = ROOT / "src/nexis/assets/branding"
    package.mkdir(parents=True, exist_ok=True)
    for path in (source, target):
        shutil.copyfile(path, package / path.name)
    assert source.read_bytes() == original
    print("PNG preserved, SHA256:", hashlib.sha256(original).hexdigest())
    print("ICO sizes:", ", ".join(map(str, SIZES)))


if __name__ == "__main__":
    main()
