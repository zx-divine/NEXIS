"""Opt-in real Windows upgrade test in a separately registered QA installation.

Builds two frozen copies, with isolated identity/profile/keys. A loopback HTTPS
adapter in QA builds routes otherwise unchanged production URLs to a local TLS
server. No OS certificate trust is changed. Production source and release feeds
are not modified. Real TUF verification, installer, helper and restart are used.
"""

import argparse
from datetime import datetime, timedelta, timezone
from functools import partial
import hashlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import site
import ssl
import subprocess
import sys
from threading import Thread
from time import monotonic, sleep
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / ".dev-deps", ROOT / ".provider-deps"):
    site.addsitedir(str(path))
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

from cryptography import x509  # noqa: E402
from cryptography.hazmat.primitives import hashes, serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import rsa  # noqa: E402
from cryptography.x509.oid import NameOID  # noqa: E402
from nexis.storage.database import Database  # noqa: E402
from nexis.storage.conversations import Conversations  # noqa: E402
from nexis.platform.update_install import registered_directory  # noqa: E402
from update_repository import initialize, sign_release  # noqa: E402

QA_MODULE = '''"""ISOLATED QA BUILD ONLY. Never distribute this module."""
import json, ssl, os
from pathlib import Path
from urllib.request import Request, build_opener, HTTPSHandler
from PySide6.QtCore import QTimer
from nexis import __version__
from nexis.core.update_service import HTTPSFetcher
from nexis.ui.main_window import MainWindow

BASE = __BASE__
CA = __CA__
EVIDENCE = Path(__EVIDENCE__)

def install():
    original_fetcher = HTTPSFetcher.__init__
    opener = build_opener(HTTPSHandler(context=ssl.create_default_context(cadata=CA)))
    class Transport:
        def open(self, request, timeout):
            original_url = request.full_url
            local = Request(BASE + original_url.rsplit('/', 1)[-1], headers=dict(request.headers))
            result = opener.open(local, timeout=timeout)
            result.geturl = lambda: original_url
            return result
    def initialize(self, *args, **kwargs):
        original_fetcher(self, *args, **kwargs)
        self.opener = Transport()
    HTTPSFetcher.__init__ = initialize
    original_start = MainWindow.start_services
    def start(window):
        original_start(window)
        attempts = [0]
        def poll():
            attempts[0] += 1
            page = window.updates_page
            if __version__ == '1.4.2':
                if page.ready and not page.busy() and not page.active_work():
                    window.navigate('Updates')
                    window.grab().save(str(EVIDENCE / 'older-verified-ready.png'))
                    (EVIDENCE / 'before.json').write_text(json.dumps(window.db.export()))
                    page.restart_install()
                    return
            elif page.service.read_state().get('phase') == 'complete':
                window.open_settings('General')
                window.grab().save(str(EVIDENCE / 'newer-restarted.png'))
                (EVIDENCE / 'after.json').write_text(json.dumps(window.db.export()))
                (EVIDENCE / 'restarted.json').write_text(json.dumps({'version': __version__, 'pid': os.getpid(), 'state': page.service.read_state()}))
                QTimer.singleShot(500, window.close)
                return
            if attempts[0] < 360:
                QTimer.singleShot(500, poll)
            else:
                (EVIDENCE / 'qa-timeout.txt').write_text(page.status.text())
                window.close()
        QTimer.singleShot(500, poll)
    MainWindow.start_services = start
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise SystemExit("Use a new output folder; existing evidence is preserved.")
    if sys.platform != "win32":
        raise SystemExit("Requires Windows x64.")
    import ctypes

    if ctypes.windll.shell32.IsUserAnAdmin():
        raise SystemExit("Run this qualification without elevation to test standard-user installation.")
    output.mkdir(parents=True)
    report = {"status": "RUNNING", "elevated": False, "transport": "Loopback HTTPS with explicit QA CA; production URL policy unchanged", "steps": {}}

    def save():
        (output / "results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    def run(label, command, cwd=ROOT, timeout=1200):
        save()
        start = monotonic()
        with (output / (label + ".log")).open("w", encoding="utf-8") as log:
            result = subprocess.run(command, cwd=cwd, stdout=log, stderr=subprocess.STDOUT,
                                    timeout=timeout, creationflags=subprocess.CREATE_NO_WINDOW)
        report["steps"][label] = {"exit_code": result.returncode, "seconds": round(monotonic() - start, 2)}
        save()
        print(label + ": " + str(result.returncode), flush=True)
        if result.returncode:
            raise RuntimeError(label + " failed; inspect the retained log")

    token = uuid4().hex[:10]
    app_id = str(uuid4()).upper()
    app_name, organization = "NEXIS Update QA " + token, "NEXIS QA"
    report.update({"isolated_app_id": app_id, "isolated_app_name": app_name})
    keys = Path(os.environ["LOCALAPPDATA"]) / "NEXIS-Release-Signing" / ("qa-" + token)
    stage = output / "source"
    stage.mkdir()
    for folder in ("src", "scripts", "installer", "assets"):
        shutil.copytree(ROOT / folder, stage / folder, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "model-downloads"))
    for name in ("NEXIS.spec", "LICENSE", "pyproject.toml"):
        shutil.copy2(ROOT / name, stage / name)
    trust = stage / "src/nexis/assets/updates/root.json"
    # This is a copied public root in the new QA directory, never the production file.
    trust.unlink()
    initialize(keys, trust)
    service_path = stage / "src/nexis/core/update_service.py"
    service_path.write_text(service_path.read_text().replace("F462E4BE-1F1F-428C-AD8C-4B5C06972164", app_id))
    main_path = stage / "src/nexis/main.py"
    main_path.write_text(main_path.read_text().replace('setApplicationName("NEXIS Desktop")',
        'setApplicationName(' + repr(app_name) + ')').replace('setOrganizationName("NEXIS")',
        'setOrganizationName(' + repr(organization) + ')'))
    entry_path = stage / "scripts/entry.py"
    entry_path.write_text(entry_path.read_text().replace('if __name__ == "__main__":',
        'from nexis.update_qa import install\ninstall()\n\nif __name__ == "__main__":'))
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "NEXIS isolated update QA")])
    import ipaddress

    cert = (x509.CertificateBuilder().subject_name(subject).issuer_name(subject)
        .public_key(key.public_key()).serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(timezone.utc) - timedelta(minutes=5))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(days=2))
        .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]), False)
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), True).sign(key, hashes.SHA256()))
    cert_path, key_path = keys / "tls-cert.pem", keys / "tls-key.pem"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    # Test-only TLS private key is outside the workspace, never copied into a build.
    key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    repository = output / "server"
    repository.mkdir()

    class Handler(SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(Handler, directory=str(repository)))
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert_path, key_path)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    Thread(target=server.serve_forever, daemon=True).start()
    module = QA_MODULE.replace("__BASE__", repr(f"https://127.0.0.1:{server.server_port}/"))
    module = module.replace("__CA__", repr(cert_path.read_text())).replace("__EVIDENCE__", repr(str(output)))
    (stage / "src/nexis/update_qa.py").write_text(module, encoding="utf-8")
    version_template = (ROOT / "scripts/version.txt").read_text()
    init_template = (ROOT / "src/nexis/__init__.py").read_text()
    installers = {}
    try:
        for label, build, public in (("older", "1.4.2", "1.1.0"), ("newer", "1.4.3", "1.1.1")):
            (stage / "src/nexis/__init__.py").write_text(init_template.replace("1.4.2", build).replace('PUBLIC_VERSION = "1.1.0"', 'PUBLIC_VERSION = "' + public + '"'))
            (stage / "scripts/version.txt").write_text(version_template.replace("1,4,2,0", build.replace(".", ",") + ",0").replace("1.4.2", build))
            payload = output / label
            run(label + "-build", [sys.executable, str(ROOT / "scripts/dev.py"), "build", "--noconfirm",
                "--distpath", str(payload), "--workpath", str(output / (label + "-work")), str(stage / "NEXIS.spec")], timeout=2400)
            run(label + "-installer", [str(ROOT / ".tools/InnoSetup/ISCC.exe"),
                "/DAppSourceDir=" + str(payload / "NEXIS"), "/DProjectRoot=" + str(stage),
                "/DAppIdentity=" + app_id, "/DIsolatedCandidate=UpdateQA-" + token,
                "/O" + str(output / (label + "-setup")), str(stage / "installer/NEXIS.iss")])
            installers[label] = next((output / (label + "-setup")).glob("*.exe"))
        signed_old = output / "signed-older"
        sign_release(keys, installers["older"], ROOT / "assets/release/UPDATE-RELEASE-NOTES.md",
                     signed_old, "1.4.2", "1.1.0", {"app_id": app_id})
        # Publish only to the isolated local TLS server, with independent QA keys.
        signed = output / "signed-newer"
        sign_release(keys, installers["newer"], ROOT / "assets/release/UPDATE-RELEASE-NOTES.md",
                     signed, "1.4.3", "1.1.1", {"app_id": app_id})
        for path in signed.iterdir():
            shutil.copy2(path, repository / path.name)
        report["installers_sha256"] = {name: hashlib.sha256(path.read_bytes()).hexdigest()
                                        for name, path in installers.items()}
        run("install-older", [str(installers["older"]), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-", "/LOG=" + str(output / "install-older-inno.log")])
        directory = registered_directory(app_id)
        # QStandardPaths uses these unchanged application/organization names in both builds.
        from PySide6.QtCore import QCoreApplication, QStandardPaths

        app = QCoreApplication([])
        app.setOrganizationName(organization)
        app.setApplicationName(app_name)
        profile = Path(QStandardPaths.writableLocation(QStandardPaths.AppLocalDataLocation))
        report["isolated_profile"] = str(profile)
        with_profile = Database(profile / "nexis.db")
        for name, value in {"welcome_completed": True, "system_access_acknowledged": True,
            "preferred_name": "Signed upgrade fixture", "default_launch_mode": "manual",
            "start_maximized": False, "theme": "matrix", "tts_enabled": False,
            "global_launcher_enabled": False, "access_permissions": {"network_actions": True}}.items():
            with_profile.set_setting(name, value)
        Conversations(with_profile).save("Upgrade fixture", [{"role": "user", "content": "Preserve this saved conversation."}])
        with_profile.close()
        (profile / "plugins").mkdir(exist_ok=True)
        (profile / "plugins/fixture.dat").write_bytes(b"Preserve plugins and skills")
        (profile / "fixture.dpapi").write_bytes(b"Opaque synthetic protected configuration")
        save()
        process = subprocess.Popen([str(directory / "NEXIS.exe")], cwd=directory)
        deadline = monotonic() + 240
        while monotonic() < deadline and not (output / "restarted.json").exists():
            if (output / "qa-timeout.txt").exists():
                raise RuntimeError("QA application timed out")
            sleep(.5)
        if not (output / "restarted.json").exists():
            raise RuntimeError("The newer frozen application did not acknowledge startup")
        process.wait(timeout=30)
        completed = json.loads((output / "restarted.json").read_bytes())
        assert completed["version"] == "1.4.3" and completed["state"]["phase"] == "complete"
        before, after = [json.loads((output / (name + ".json")).read_bytes()) for name in ("before", "after")]
        # Compare all user records except volatile operational history and updater preferences.
        for table in ("snippets", "shortcuts", "workflows", "local_memories", "conversations"):
            if table in before:
                assert before[table] == after[table], table
        settings_before, settings_after = before["settings"], after["settings"]
        for name in settings_before:
            if not name.startswith("update_") and name not in {"catalog_scanned_at", "voice_model_path"}:
                assert settings_before[name] == settings_after[name], name
        assert (profile / "plugins/fixture.dat").read_bytes() == b"Preserve plugins and skills"
        assert (profile / "fixture.dpapi").read_bytes() == b"Opaque synthetic protected configuration"
        assert Path(completed["state"]["backup"]).is_dir()
        report.update({"status": "PASS", "from_build": "1.4.2", "to_build": "1.4.3",
            "verified_signature": "Ed25519 via real python-tuf client", "installer": "Real Inno per-user Setup, no elevation",
            "restart": "New frozen NEXIS window acknowledged startup", "data_preservation": "PASS",
            "normal_profile_touched": False, "production_published": False})
        save()
    except Exception as exc:
        report.update({"status": "FAIL", "error": str(exc)})
        save()
        raise
    finally:
        server.shutdown()
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
