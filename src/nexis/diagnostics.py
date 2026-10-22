"""Opt-in packaged smoke check. Never touches the normal user database or OS launchers."""

import json
import hashlib
import ctypes
import sys
import certifi
from pathlib import Path
import tempfile
from time import perf_counter

from PySide6.QtCore import QTimer, QLibraryInfo, qVersion
from PySide6.QtGui import QFontDatabase, QImage

from nexis.storage.database import Database
from nexis.branding import APP_USER_MODEL_ID, asset
from nexis.ui.branding import BrandLogo, WelcomeWizard, splash_screen
from nexis.ui.main_window import MainWindow
from nexis import __version__, DISPLAY_VERSION, PUBLIC_VERSION, RELEASE_CHANNEL


def smoke(app, output):
    started = perf_counter()
    network_attempts = []
    if "--offline-smoke" in sys.argv:
        import socket

        def blocked_connect(*args, **kwargs):
            network_attempts.append(True)
            raise OSError("Network disabled for isolated offline startup verification")

        socket.socket.connect = blocked_connect
        socket.socket.connect_ex = blocked_connect
        socket.create_connection = blocked_connect
    destination = Path(output).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    QFontDatabase.addApplicationFont("C:/Windows/Fonts/segoeui.ttf")
    with tempfile.TemporaryDirectory(prefix="nexis-smoke-") as temporary:
        db = Database(Path(temporary) / "smoke.db")
        window = MainWindow(db, temporary)
        window.show()
        capabilities = "--capability-smoke" in sys.argv
        if capabilities:
            window.start_services()

        def finish():
            wizard = WelcomeWizard(db)
            wizard.setStyleSheet(window.styleSheet())
            wizard.show()
            app.processEvents()
            wizard.grab().save(str(destination / "packaged-welcome.png"))
            wizard.next()
            app.processEvents()
            wizard.grab().save(str(destination / "packaged-access-disclosure.png"))
            wizard.access.acknowledged.setChecked(True)
            for _ in range(4):
                wizard.next()
            app.processEvents()
            wizard.grab().save(str(destination / "packaged-provider-setup.png"))
            wizard.next()
            wizard.accept()
            splash = splash_screen()
            splash.show()
            app.processEvents()
            splash.grab().save(str(destination / "packaged-splash.png"))
            splash.close()
            process_id = None
            native_icons = {}
            if sys.platform == "win32":
                value = ctypes.c_wchar_p()
                getter = ctypes.windll.shell32.GetCurrentProcessExplicitAppUserModelID
                getter.argtypes = [ctypes.POINTER(ctypes.c_wchar_p)]
                getter.restype = ctypes.c_long
                if getter(ctypes.byref(value)) == 0:
                    process_id = value.value
                    free = ctypes.windll.ole32.CoTaskMemFree
                    free.argtypes = [ctypes.c_void_p]
                    free(ctypes.cast(value, ctypes.c_void_p))
                if app.platformName() == "windows":
                    send = ctypes.windll.user32.SendMessageW
                    send.argtypes = [
                        ctypes.c_void_p,
                        ctypes.c_uint,
                        ctypes.c_size_t,
                        ctypes.c_ssize_t,
                    ]
                    send.restype = ctypes.c_void_p
                    for name, kind in (("small", 0), ("large", 1)):
                        handle = send(int(window.winId()), 0x7F, kind, 0)  # WM_GETICON
                        native_icons[name] = bool(handle)
                        if handle:
                            image = QImage.fromHICON(handle)
                            native_icons[name] = not image.isNull()
                            image.save(str(destination / ("native-window-icon-" + name + ".png")))
            report = {
                "ok": True,
                "app_version": __version__,
                "display_version": DISPLAY_VERSION,
                "public_version": PUBLIC_VERSION,
                "release_channel": RELEASE_CHANNEL,
                "certifi_version": certifi.__version__,
                "certifi_bundle_sha256": hashlib.sha256(Path(certifi.where()).read_bytes()).hexdigest(),
                "frozen": bool(getattr(sys, "frozen", False)),
                "python_network_blocked": "--offline-smoke" in sys.argv,
                "network_connection_attempts": len(network_attempts),
                "qt_version": qVersion(),
                "windows_plugin_present": (
                    Path(QLibraryInfo.path(QLibraryInfo.PluginsPath)) / "platforms" / "qwindows.dll"
                ).exists(),
                "qt_platform": app.platformName(),
                "window_ms": round((perf_counter() - started) * 1000, 1),
                "pages": list(window.pages),
                "stylesheet_loaded": bool(window.styleSheet()),
                "database": "isolated temporary storage",
                "logo_sha256": hashlib.sha256(asset("NEXIS_logo.png").read_bytes()).hexdigest(),
                "logo_path": str(asset("NEXIS_logo.png")),
                "application_icon_loaded": not app.windowIcon().isNull(),
                "window_icon_loaded": not window.windowIcon().isNull(),
                "about_logo_loaded": bool(
                    window.stack.widget(window.pages["About"]).findChildren(BrandLogo)
                )
                and all(
                    not logo.pixmap().isNull()
                    for logo in window.stack.widget(window.pages["About"]).findChildren(BrandLogo)
                ),
                "wizard_completed": db.setting("welcome_completed"),
                "app_user_model_id": process_id,
                "app_user_model_id_matches": process_id == APP_USER_MODEL_ID,
                "native_window_icons": native_icons,
                "voice_dependencies": {},
                "catalog_applications": len(window.discovery.catalog.rows()),
                "discovery_status": window.discovery.status.text(),
                "speech_status": window.settings_page.voice_setup.device_status.text(),
                "windows_voices": window.settings_page.voice_setup.voices.count() - 1,
                "schema_version": db.rows("PRAGMA user_version")[0]["user_version"],
            }
            for dependency in (
                "vosk",
                "sounddevice",
                "webrtcvad",
                "_webrtcvad",
                "win32crypt",
                "pythoncom",
                "google.genai",
                "send2trash",
                "websocket",
            ):
                try:
                    __import__(dependency)
                    report["voice_dependencies"][dependency] = "available"
                except Exception:
                    report["voice_dependencies"][dependency] = "unavailable"
            try:
                report["bundled_model"] = bundled_model_check(temporary)
            except Exception as exc:
                report["bundled_model"] = {"loaded": False, "error_type": type(exc).__name__}
                report["ok"] = False
            try:
                report["workflow_fixture_check"] = workflow_fixture_check(temporary)
            except Exception as exc:
                report["workflow_fixture_check"] = {"result": "FAIL", "error_type": type(exc).__name__}
                report["ok"] = False
            try:
                report["provider_adapter_checks"] = provider_sdk_fixture_check()
            except Exception as exc:
                report["provider_adapter_checks"] = {
                    "official_gemini_sdk_mock_transport": "FAIL",
                    "error_type": type(exc).__name__,
                    "network_used": False,
                }
                report["ok"] = False
            for label in window.pages:
                window.navigate(label)
                app.processEvents()
                if label == "About":
                    window.grab().save(str(destination / "packaged-about.png"))
                elif label in {"Applications", "Settings"}:
                    window.grab().save(str(destination / ("packaged-" + label.casefold() + ".png")))
            window.navigate("Dashboard")
            app.processEvents()
            window.grab().save(str(destination / "packaged-window.png"))
            (destination / "packaged-smoke.json").write_text(
                json.dumps(report, indent=2), encoding="utf-8"
            )
            window.close()

            def stopped():
                if any(job and job.isRunning() for job in window.background_jobs()):
                    QTimer.singleShot(100, stopped)
                else:
                    app.quit()

            stopped()

        QTimer.singleShot(5000 if capabilities else 100, finish)
        status = app.exec()
        db.close()
        return status


def workflow_fixture_check(temporary):
    """Exercise the frozen workflow backend without touching Windows clipboard."""
    from threading import Event
    from nexis.storage.repository import Repository
    from nexis.core.tools import ToolExecutor
    database = Database(Path(temporary) / "workflow-fixture.db")
    try:
        database.set_setting("system_access_acknowledged", True)
        database.set_setting("access_permissions", {"workflow_execution": True, "clipboard_access": True})
        Repository(database).save_snippet("fixture", "Test", "Disposable package fixture")
        Repository(database).save_workflow("fixture", ["copy fixture"])
        deliveries = []
        executor = ToolExecutor(database, temporary, object(), lambda preview: True, deliveries.append)
        result = executor.run({"tool": "workflow_run", "arguments": {"name": "fixture"}}, Event())
        if deliveries != ["Disposable package fixture"] or not result.get("request_accepted") or result.get("verified"):
            raise ValueError("Packaged workflow failed its clipboard delivery boundary check.")
        # Also test the final frozen cancellation boundary without Windows effects.
        cancelled, rejected_deliveries = Event(), []

        def cancelled_approval(preview):
            cancelled.set()
            return True

        blocked = ToolExecutor(database, temporary, object(), cancelled_approval, rejected_deliveries.append)
        try:
            blocked.run({"tool": "clipboard_copy", "arguments": {"text": "Must not be delivered"}}, cancelled)
        except ValueError:
            pass
        else:
            raise ValueError("Packaged cancellation fixture did not stop execution.")
        if rejected_deliveries:
            raise ValueError("Packaged cancelled request delivered a clipboard result.")
        return {"result": "PASS", "backend_deliveries": 1, "real_clipboard_modified": False,
                "cancelled_delivery_blocked": True, "os_effects_verified": False}
    finally:
        database.close()


def provider_sdk_fixture_check():
    """Exercise the bundled official SDK using an in-memory HTTP fixture, never a live key."""
    import httpx
    from google import genai
    from google.genai import types

    def response(request):
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {"role": "model", "parts": [{"text": "packaged SDK fixture"}]},
                        "finishReason": "STOP",
                    }
                ]
            },
            request=request,
        )

    with genai.Client(
        api_key="NEXIS-PACKAGE-FIXTURE-NOT-A-REAL-KEY",
        vertexai=False,
        http_options=types.HttpOptions(client_args={"transport": httpx.MockTransport(response)}),
    ) as client:
        answer = client.models.generate_content(model="fixture-only", contents="fixture")
        if answer.text != "packaged SDK fixture":
            raise ValueError("Bundled Gemini SDK fixture did not return its expected response.")
    return {
        "official_gemini_sdk_mock_transport": "PASS",
        "live_gemini_inference": "PENDING USER VERIFICATION",
        "network_used": False,
    }


def bundled_model_check(temporary):
    """Load the shipped decoder without opening a microphone or claiming real speech."""
    from nexis.core.models import detect_model, MODEL
    from nexis.core.voice import capture_rates
    from vosk import Model, KaldiRecognizer, SetLogLevel

    path = Path(detect_model("", temporary))
    manifest_path = path.parent / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["model"] != MODEL:
        raise ValueError("Unexpected bundled model manifest")
    for relative, expected in manifest["files"].items():
        with (path / relative).open("rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() != expected:
                raise ValueError("Bundled model integrity failure")
    SetLogLevel(-1)
    model = Model(str(path))
    selected_rate = capture_rates(path, 8000)[0]
    decoder = KaldiRecognizer(model, selected_rate)
    decoder.AcceptWaveform(bytes(selected_rate // 5 * 2))
    decoder.FinalResult()
    return {
        "id": MODEL["id"], "loaded": True, "files_verified": len(manifest["files"]),
        "bytes": manifest["bytes"], "path": str(path),
        "inside_package": path.is_relative_to(Path(__file__).resolve().parent),
        "microphone_opened": False, "real_speech": "NOT VERIFIED",
        "narrowband_default_selected_rate": selected_rate,
        "synthetic_pcm_decoder_check": "PASS",
    }
