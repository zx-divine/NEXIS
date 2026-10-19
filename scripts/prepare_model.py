"""Prepare the pinned redistributable default model before a release build.

A source checkout can run with a separately installed model. Release builds cannot
omit it. --download explicitly permits the 41.2 MB official archive on build hosts;
installed users never need this script or a network download for default voice.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
from threading import Event

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from nexis.core.models import MODEL, install_model  # noqa: E402


def verify_model(directory, manifest):
    if manifest["model"] != MODEL:
        raise ValueError("Build manifest does not match the pinned model configuration.")
    for name, expected in manifest["files"].items():
        path = directory / name
        if not path.is_file() or path.is_symlink():
            raise ValueError("Missing or unsafe model resource: " + name)
        with path.open("rb") as source:
            if hashlib.file_digest(source, "sha256").hexdigest() != expected:
                raise ValueError("Model integrity failed: " + name)
    actual = {p.relative_to(directory).as_posix() for p in directory.rglob("*") if p.is_file()}
    if actual != set(manifest["files"]):
        raise ValueError("Unexpected files in bundled model; release build stopped.")
    return sum((directory / name).stat().st_size for name in manifest["files"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", action="store_true", help="Permit approved model download")
    args = parser.parse_args()
    manifest = json.loads((ROOT / "assets/models/manifest.json").read_text())
    directory = ROOT / "assets/models" / MODEL["id"]
    if not directory.is_dir():
        if not args.download:
            raise SystemExit("Default model missing. Run prepare_model.py --download before building.")
        print("Preparing official English (US) offline model: 41.2 MB; Apache-2.0.", flush=True)
        install_model(ROOT / "assets", Event(), print, consent=True)
    size = verify_model(directory, manifest)
    print(f"Verified {len(manifest['files'])} model files, {size} bytes; no microphone opened.")


if __name__ == "__main__":
    main()
