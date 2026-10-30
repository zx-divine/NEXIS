"""Prepare a local signed TUF GitHub release. Never uploads or publishes anything.

Private Ed25519 keys are DPAPI protected for the current Windows user and must
live outside the source checkout. Production signing is separate from packaging.
"""

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import shutil
import site
import sys

ROOT = Path(__file__).resolve().parents[1]
for directory in (ROOT / ".dev-deps", ROOT / ".provider-deps"):
    site.addsitedir(str(directory))
sys.path.insert(0, str(ROOT / "src"))

from cryptography.hazmat.primitives.serialization import load_pem_private_key  # noqa: E402
from securesystemslib.signer import CryptoSigner  # noqa: E402
from tuf.api.metadata import Metadata, Root, Targets, TargetFile, Snapshot, Timestamp, MetaFile  # noqa: E402
from nexis.core.update_service import APP_ID, RELEASE_INDEX, semver, regular_path, atomic_json, operation_lock  # noqa: E402

ROLES = ("root-1", "root-2", "root-3", "targets", "snapshot", "timestamp")


def key_location(directory):
    directory = regular_path(directory).resolve()
    if directory.is_relative_to(ROOT):
        raise ValueError("Private signing material must be outside the project.")
    return directory


def initialize(directory, root_output):
    import win32crypt

    directory = key_location(directory)
    if directory.exists() or root_output.exists():
        raise ValueError("Refusing to replace existing keys or trust root.")
    directory.mkdir(parents=True)
    now = datetime.now(timezone.utc)
    root = Metadata(Root(expires=now + timedelta(days=730), consistent_snapshot=False))
    signers = {}
    for role in ROLES:
        signer = CryptoSigner.generate_ed25519()
        encrypted = win32crypt.CryptProtectData(signer.private_bytes, "NEXIS TUF " + role,
                                                None, None, None, 1)
        (directory / (role + ".dpapi")).write_bytes(encrypted)
        signers[role] = signer
        root.signed.add_key(signer.public_key, "root" if role.startswith("root-") else role)
    root.signed.roles["root"].threshold = 2
    for role in ROLES[:3]:
        root.sign(signers[role], append=True)
    root_output.parent.mkdir(parents=True, exist_ok=True)
    root.to_file(str(root_output))
    (directory / "1.root.json").write_bytes(root_output.read_bytes())
    atomic_json(directory / "signing-state.json", {"sequence": 0})
    return {"root_sha256": hashlib.sha256(root_output.read_bytes()).hexdigest(),
            "root_threshold": "2 of 3", "private_keys": "Current-user DPAPI, outside checkout"}


def load_signers(directory):
    import win32crypt

    return {role: CryptoSigner(load_pem_private_key(win32crypt.CryptUnprotectData(
        (directory / (role + ".dpapi")).read_bytes(), None, None, None, 1)[1], None))
        for role in ROLES[3:]}


def sign_release(directory, installer, notes, output, build, public, descriptor_changes=None):
    """The same standard TUF metadata writer is used by isolated integration tests."""
    directory = key_location(directory)
    semver(build)
    semver(public)
    if output.exists():
        raise ValueError("Use a new output directory; prior artifacts are preserved.")
    if not installer.is_file() or installer.suffix.lower() != ".exe":
        raise ValueError("Supply the completed Inno Setup EXE.")
    import win32api

    info = win32api.GetFileVersionInfo(str(installer.resolve()), "\\")
    high, low = info["FileVersionMS"], info["FileVersionLS"]
    if (high >> 16, high & 65535, low >> 16, low & 65535) != (*semver(build), 0):
        raise ValueError("Installer FileVersion does not match the requested engineering build.")
    text = notes.read_text(encoding="utf-8")
    if not 1 <= len(text) <= 24000:
        raise ValueError("Release notes must contain 1–24000 characters.")
    signers = load_signers(directory)
    state = json.loads((directory / "signing-state.json").read_bytes())
    sequence = state["sequence"] + 1
    now = datetime.now(timezone.utc)
    output.mkdir(parents=True)
    name = f"NEXIS-{public}-{build}-Windows-x64-Setup.exe"
    shutil.copyfile(installer, output / name)
    descriptor = {"schema": 1, "app_id": APP_ID, "platform": "windows-x86_64",
        "installer_kind": "inno-per-user", "public_version": public, "build_version": build,
        "tag": "v" + public, "installer": name, "notes": text, "data_schema": 5}
    descriptor.update(descriptor_changes or {})
    atomic_json(output / RELEASE_INDEX, descriptor)
    targets = Metadata(Targets(version=sequence, expires=now + timedelta(days=90)))
    for name in (name, RELEASE_INDEX):
        targets.signed.targets[name] = TargetFile.from_file(name, str(output / name), ["sha256"])
    targets.sign(signers["targets"])
    targets.to_file(str(output / "targets.json"))

    def metainfo(path):
        data = path.read_bytes()
        return MetaFile(sequence, len(data), {"sha256": hashlib.sha256(data).hexdigest()})

    snapshot = Metadata(Snapshot(version=sequence, expires=now + timedelta(days=30),
        meta={"targets.json": metainfo(output / "targets.json")}))
    snapshot.sign(signers["snapshot"])
    snapshot.to_file(str(output / "snapshot.json"))
    timestamp = Metadata(Timestamp(version=sequence, expires=now + timedelta(days=14),
        snapshot_meta=metainfo(output / "snapshot.json")))
    timestamp.sign(signers["timestamp"])
    timestamp.to_file(str(output / "timestamp.json"))
    roots = sorted(directory.glob("*.root.json"))
    for path in roots:
        shutil.copyfile(path, output / path.name)
    shutil.copyfile(roots[-1], output / "root.json")
    (output / "RELEASE-NOTES.md").write_text(text, encoding="utf-8")
    summary = {"framework": "python-tuf 7.0.1", "signatures": "Ed25519",
        "public_version": public, "build_version": build, "metadata_version": sequence,
        "repository": "https://github.com/zx-divine/NEXIS", "published": False,
        "timestamp_expires": timestamp.signed.expires.isoformat(),
        "authenticode": "Not asserted; sign the EXE before TUF metadata when a certificate is available",
        "target_signing_key": signers["targets"].public_key.keyid}
    atomic_json(output / "UPDATER-MANIFEST.json", summary)
    atomic_json(directory / "signing-state.json", {"sequence": sequence})
    write_checksums(output)
    return summary


def write_checksums(output):
    lines = []
    for path in sorted(output.iterdir()):
        if path.is_file() and path.name != "SHA256SUMS.txt":
            with path.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            lines.append(digest + "  " + path.name + "\n")
    (output / "SHA256SUMS.txt").write_text("".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("--keys-dir", type=Path, required=True)
    init.add_argument("--root-output", type=Path, required=True)
    sign = sub.add_parser("sign")
    for name in ("keys-dir", "installer", "notes", "output"):
        sign.add_argument("--" + name, type=Path, required=True)
    sign.add_argument("--build", required=True)
    sign.add_argument("--public", required=True)
    args = parser.parse_args()
    if args.command == "init":
        result = initialize(args.keys_dir, args.root_output)
    else:
        with operation_lock(key_location(args.keys_dir)):
            result = sign_release(args.keys_dir, args.installer, args.notes,
                                  args.output, args.build, args.public)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
