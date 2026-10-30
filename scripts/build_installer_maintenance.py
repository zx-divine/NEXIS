"""Recompile only Setup around an unchanged, previously verified application payload.

This does not refreeze the app, replace the portable ZIP, install NEXIS, or relax
the five-regression gate for application builds. Its report distinguishes the
original payload revision from the new installer source revision.
"""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from time import monotonic
import zipfile

from candidate_evidence import ROOT, fingerprint


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--application-build', required=True, type=Path)
    parser.add_argument('--verification', required=True, type=Path)
    parser.add_argument('--iscc', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    build = args.application_build.resolve()
    manifest = json.loads((build / 'RELEASE-MANIFEST.json').read_text())
    assert json.loads((build / 'BUILD-REPORT.json').read_text())['status'] == 'PASS'
    verified = json.loads(args.verification.read_text())
    assert verified['status'] == 'PASS' and verified['owner_identity_used'] is False
    for name in ('installer/NEXIS.iss', 'installer/maintenance.iss'):
        assert verified['installer_source_sha256'][name] == sha256(ROOT / name), 'Installer changed after fixture checks'
    for row in manifest['artifacts']:
        assert sha256(build / row['file']) == row['sha256'], 'Previously verified artifact changed'
    payload = build / 'payload/NEXIS'
    archive = next(build.glob('*Portable.zip'))
    with zipfile.ZipFile(archive) as zipped:
        assert zipped.testzip() is None
        members = [item for item in zipped.infolist() if not item.is_dir()]
        paths = {item.filename.removeprefix('NEXIS/') for item in members}
        assert paths == {path.relative_to(payload).as_posix() for path in payload.rglob('*') if path.is_file()}
        for item in members:
            assert item.filename.startswith('NEXIS/')
            relative = Path(item.filename.removeprefix('NEXIS/'))
            assert not relative.is_absolute() and '..' not in relative.parts
            with zipped.open(item) as stream:
                assert hashlib.file_digest(stream, 'sha256').hexdigest() == sha256(payload / relative)
    output = args.output.resolve()
    assert output.is_relative_to(ROOT) and output != ROOT
    output.mkdir(parents=True, exist_ok=False)
    before = fingerprint()
    command = [str(args.iscc.resolve()), '/DAppSourceDir=' + str(payload),
               '/O' + str(output), '/FNEXIS-V1-Setup', str(ROOT / 'installer/NEXIS.iss')]
    started = monotonic()
    with (output / 'compile.log').open('w', encoding='utf-8') as log:
        result = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=900)
    assert result.returncode == 0, 'Installer compilation failed; previous deliveries were not changed'
    assert fingerprint() == before, 'Source changed while compiling Setup'
    setup = output / 'NEXIS-V1-Setup.exe'
    report = {'status': 'PASS', 'application_version': manifest['version'], 'maintenance_revision': 2,
              'application_source_sha256': manifest['source_sha256'], 'current_source_sha256': before,
              'installer_sources': verified['installer_source_sha256'],
              'application_exe_sha256': sha256(payload / 'NEXIS.exe'),
              'portable_zip_sha256': sha256(archive), 'payload_file_count_verified': len(paths),
              'installer_sha256': sha256(setup), 'installer_bytes': setup.stat().st_size,
              'compile_seconds': round(monotonic() - started, 2),
              'application_payload_changed': False, 'signed': False, 'published': False,
              'public_release_ready': False}
    (output / 'MAINTENANCE-BUILD-REPORT.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
