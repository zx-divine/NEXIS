"""Review actual staged blobs for private files and credential-like literals.

A heuristic check supplements, not replaces, source review. Values are never printed.
"""
import json
from pathlib import Path
import re
import subprocess
import argparse

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--output", type=Path, default=ROOT / "docs/installer-overhaul/staged-source-audit.json")
args = parser.parse_args()
items = subprocess.check_output(["git", "ls-files", "--stage", "-z"], cwd=ROOT).split(b"\0")
entries = []
for item in items:
    if item:
        metadata, name = item.split(b"\t", 1)
        entries.append((metadata.split()[1].decode(), name.decode("utf-8")))
raw = subprocess.check_output(["git", "cat-file", "--batch"], cwd=ROOT,
                              input="".join(sha + "\n" for sha, _ in entries).encode())
position = 0
findings = []
reviewed_fixture_matches = 0
reviewed_header_fixtures = 0
size = 0
patterns = {
    "private key block": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH |ENCRYPTED )?PRIVATE KEY-----"),
    "API credential": re.compile(rb"(?:\bsk-(?:proj-)?[A-Za-z0-9_-]{30,}|AIza[A-Za-z0-9_-]{30,}|GOCSPX-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{24,}|github_pat_[A-Za-z0-9_]{30,})"),
    "embedded credential URL": re.compile(rb"https?://[^\s/'\"<>:@]+:[^\s/'\"<>@]+@"),
    "developer personal directory": re.compile(rb"C:(?:\\+|/+)Users(?:\\+|/+)kingb", re.I),
}
for sha, name in entries:
    end = raw.index(b"\n", position)
    length = int(raw[position:end].split()[2])
    data = raw[end + 1:end + 1 + length]
    position = end + length + 2
    size += length
    if Path(name).suffix.lower() in {".exe", ".dll", ".pyd", ".zip", ".db", ".sqlite", ".dpapi", ".wav", ".mp3", ".pfx", ".p12", ".pem", ".key", ".mdl", ".fst"} or name.startswith(("dist/", ".dev-", ".provider-deps/", ".tools/", "docs/installer-overhaul/")):
        findings.append({"file": name, "issue": "Private/generated/binary artifact staged"})
    if Path(name).suffix.lower() in {".png", ".ico"}:
        continue
    for label, pattern in patterns.items():
        matches = list(pattern.finditer(data))
        if label == "private key block" and name == "tests/unit/test_runtime_ssl_packaging.py":
            remaining = []
            for match in matches:
                if (match.group() == b"-----BEGIN " + b"PRIVATE KEY-----"
                        and data[match.end():].startswith(b"\\nDo not package")):
                    reviewed_header_fixtures += 1  # Header-only rejection fixture, no key data.
                else:
                    remaining.append(match)
            matches = remaining
        if label == "embedded credential URL" and name in {"tests/unit/test_core.py", "tests/unit/test_public_setup.py", "tests/unit/test_website_launcher.py", "tests/unit/test_secure_updates.py"}:
            remaining = []
            for match in matches:
                pair = match.group().split(b"://", 1)[1].rstrip(b"@")
                if pair in {b"u:p", b"key:secret", b"user:pass", b"user:password"} and data[match.end():].startswith(b"example.com"):
                    reviewed_fixture_matches += 1  # Explicit dummy credentials used to test URL rejection.
                elif (name == "tests/unit/test_secure_updates.py" and pair == b"user:password"
                      and data[match.end():].startswith(b"github.com/zx-divine/NEXIS/releases/latest/download/root.json")):
                    reviewed_fixture_matches += 1  # Fixed dummy URL rejected by the updater test.
                else:
                    remaining.append(match)
            matches = remaining
        if matches:
            findings.append({"file": name, "issue": label})
report = {"staged_files": len(entries), "staged_bytes": size, "findings": findings,
          "reviewed_dummy_url_fixtures": reviewed_fixture_matches,
          "reviewed_header_only_fixtures": reviewed_header_fixtures,
          "scope": "Actual staged blobs, not ignored local databases/logs; heuristic scan plus reviewed publication allowlist."}
output = args.output
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2))
raise SystemExit(1 if findings else 0)
