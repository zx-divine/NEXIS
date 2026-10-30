"""Verify real Inno maintenance helpers using an explicitly isolated test identity.

Installs/removes only a synthetic package containing the newest real EXE and a
fixture marker, never the owner's registered NEXIS or personal profile. The
fixture is not delivered and is not claimed to be a working application bundle.
"""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import uuid
import winreg

ROOT = Path(__file__).resolve().parents[1]


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--iscc', required=True, type=Path)
    parser.add_argument('--payload', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT) or output == ROOT:
        raise SystemExit('Verification output must be a new directory within this workspace.')
    output.mkdir(parents=True, exist_ok=False)
    source = output / 'fixture-source'
    source.mkdir()
    shutil.copy2(args.payload / 'NEXIS.exe', source / 'NEXIS.exe')
    (source / 'fixture-payload.txt').write_text('Synthetic installer verification fixture. Not a distributable app.\n')
    identity = str(uuid.uuid4()).upper()
    key_name = 'Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\{' + identity + '}_is1'
    target = output / 'installed-fixture'
    evidence = {'app_identity': identity, 'owner_identity_used': False,
                'fixture_exe_sha256': sha256(source / 'NEXIS.exe'), 'steps': {}, 'status': 'RUNNING'}
    evidence['installer_source_sha256'] = {name: sha256(ROOT / name) for name in (
        'installer/NEXIS.iss', 'installer/maintenance.iss', 'tests/installer/maintenance_fixture.iss')}

    def run(name, command, accepted=(0,)):
        result = subprocess.run([str(part) for part in command], cwd=ROOT, capture_output=True,
                                text=True, encoding='utf-8', errors='replace', timeout=240)
        (output / (name + '.log')).write_text(result.stdout + result.stderr, encoding='utf-8')
        evidence['steps'][name] = {'exit_code': result.returncode}
        if result.returncode not in accepted:
            raise AssertionError(name + ' failed: ' + str(result.returncode))

    run('compile', [args.iscc.resolve(), '/DAppIdentity=' + identity, '/DProjectRoot=' + str(ROOT),
                    '/DAppSourceDir=' + str(source), '/O' + str(output), '/Fmaintenance-fixture',
                    ROOT / 'tests/installer/maintenance_fixture.iss'])
    fixture = output / 'maintenance-fixture.exe'

    def inspect(mode, label=None):
        label = label or mode
        report = output / (label + '.txt')
        run(label, [fixture, '/NEXISVERIFY=' + mode, '/NEXISREPORT=' + str(report),
                   '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/LOG=' + str(output / (label + '-inno.log'))], accepted=(1,))
        checks = report.read_text()
        assert checks and all(line.startswith('PASS: ') for line in checks.splitlines())
        evidence['steps'][label]['checks'] = checks.splitlines()

    inspect('missing')
    run('install', [fixture, '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/NOICONS',
                    '/DIR=' + str(target), '/LOG=' + str(output / 'install-inno.log')])
    assert (target / 'NEXIS.exe').is_file()
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_name, access=winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
        location = Path(winreg.QueryValueEx(key, 'InstallLocation')[0]).resolve()
        assert location == target
    assert location.is_relative_to(output) and location != output
    personal = target / 'user-created-keep.txt'
    personal.write_text('This synthetic user-created file must survive uninstall.\n')
    personal_hash = sha256(personal)
    inspect('installed')
    # Only the isolated test identity and resolved directory above may be removed.
    inspect('remove')
    assert personal.is_file() and sha256(personal) == personal_hash
    assert not (target / 'NEXIS.exe').exists()
    inspect('missing', 'missing-after-uninstall')
    evidence['status'] = 'PASS'
    evidence['user_created_file_preserved'] = True
    evidence['production_install_uninstall_performed'] = False
    evidence['limitation'] = 'Fixture verifies actual compiled shared helpers and Inno install/removal; production confirmation UI and clean-OS lifecycle are separate checks.'
    (output / 'results.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')
    print(json.dumps(evidence, indent=2))


if __name__ == '__main__':
    main()
