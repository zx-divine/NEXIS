"""Opt-in packaged smoke check. Never touches the normal user database or OS launchers."""

import json
import hashlib
import ctypes
import sys
import ssl
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
            wizard.preferred_name.setText("Package verification")
            wizard.next()
            assert wizard.currentId() == 1
            app.processEvents()
            wizard.grab().save(str(destination / "packaged-access-disclosure.png"))
            wizard.access.acknowledged.setChecked(True)
            for _ in range(4):
                wizard.next()
            assert wizard.currentId() == 5
            wizard.api_setup_choice.setCurrentIndex(wizard.api_setup_choice.findData('later'))
            app.processEvents()
            wizard.grab().save(str(destination / "packaged-provider-setup.png"))
            while wizard.currentId() < 8:
                wizard.next()
            wizard.accept()
            assert db.setting("welcome_completed")
            window.settings_page.reload_profile()
            window.welcome.refresh()
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
                "window_title": window.windowTitle(),
                "stylesheet_loaded": bool(app.styleSheet()),
                "openssl_version": ssl.OPENSSL_VERSION,
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
            try:
                report["latest_feature_checks"] = latest_feature_check(window, db)
            except Exception as exc:
                report["latest_feature_checks"] = {"status": "FAIL", "error_type": type(exc).__name__}
                report["ok"] = False
            try:
                from nexis.core.themes import THEMES
                from nexis.storage.database import read_appearance
                report["themes"] = []
                panel = window.settings_page.appearance
                db.set_setting("reduced_motion", True)
                for selected in THEMES:
                    panel.theme.setCurrentIndex(panel.theme.findData(selected))
                    assert panel.preview()
                    panel.save()
                    assert read_appearance(db.path)[0] == selected
                    window.navigate("Dashboard")
                    app.processEvents()
                    assert window.grab().save(str(destination / ("theme-" + selected + ".png")))
                    report["themes"].append(selected)
                panel.reset()
                panel.save()
                report["theme_persistence"] = "PASS: isolated temporary settings only"
                if sys.platform == "win32":
                    from nexis.platform.trust import trusted_signature, original_filename, windows_directory
                    system_target = windows_directory() / "System32/Taskmgr.exe"
                    report["native_trust"] = {"signature_backend_validated": trusted_signature(system_target),
                                              "identity_backend_validated": original_filename(system_target) == "taskmgr"}
                    assert all(report["native_trust"].values())
            except Exception as exc:
                report["theme_or_native_trust_error"] = type(exc).__name__
                report["ok"] = False
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

        def guarded_finish():
            try:
                finish()
            except Exception as exc:
                (destination / "packaged-smoke.json").write_text(json.dumps({
                    "ok": False, "error_type": type(exc).__name__,
                    "frozen": bool(getattr(sys, "frozen", False)), "app_version": __version__,
                }, indent=2), encoding="utf-8")
                window.close()
                app.quit()

        QTimer.singleShot(5000 if capabilities else 100, guarded_finish)
        status = app.exec()
        db.close()
        report_path = destination / "packaged-smoke.json"
        passed = report_path.is_file() and json.loads(report_path.read_text(encoding="utf-8")).get("ok") is True
        return status if passed else 1


def latest_feature_check(window, db):
    """Exercise actual new UI/storage using disposable data, without OS actions."""
    from nexis.core.access import require_access
    from nexis.storage.conversations import Conversations

    checks = {}
    assert window.windowTitle() == "NEXIS"
    checks["nexis_window_title"] = "PASS"
    assert db.setting("welcome_completed") and db.setting("preferred_name") == "Package verification"
    checks["onboarding_identity_and_completion"] = "PASS"
    assert db.setting('ai_setup_choice') == 'later'
    assert not db.setting('wake_word_enabled') and not window.desktop_experience.wake.worker
    window.always_active_button.click()
    assert window.stack.currentIndex() == window.pages['Desktop Companion']
    checks['explicit_api_choice_and_visible_always_active'] = 'PASS'
    history = [{"role": "user", "content": "Disposable package context"}]
    window.conversation_history = list(history)
    window.chat.input.setText("Disposable unsent draft")
    for key, label in (("voice", "Voice Chat"), ("chat", "Chat"), ("manual", "Dashboard")):
        window.welcome.mode_buttons[key].click()
        assert window.stack.currentIndex() == window.pages[label]
        assert window.conversation_history == history
        assert window.chat.input.text() == "Disposable unsent draft"
        assert window.voice.worker is None
    checks["three_modes_and_context_preservation"] = "PASS"
    window.settings_button.click()
    assert window.stack.currentIndex() == window.pages["Settings"]
    assert len(window.settings_page.category_order) == 8
    window.settings_page.preferred_name.setText("Package Tester")
    window.settings_page.launcher_enabled.setChecked(False)
    window.settings_page.save()
    assert db.setting("preferred_name") == "Package Tester"
    assert "Package Tester" in window.welcome.greeting.text()
    checks["settings_and_name_persistence"] = "PASS"
    identifier = window.chat.archive.save("Disposable package chat", history)
    reopened = Database(db.path)
    try:
        saved = Conversations(reopened)
        assert saved.search("package chat")[0]["id"] == identifier
        assert saved.get(identifier)["messages"] == history
    finally:
        reopened.close()
    window.saved_conversations.refresh()
    window.saved_conversations.results.setCurrentRow(0)
    window.saved_conversations.open_selected()
    assert window.conversation_history == history
    assert not window.ai_jobs
    try:
        window.chat.archive.delete(identifier)
    except ValueError:
        pass
    else:
        raise ValueError("Saved-chat deletion bypassed authorization")
    assert window.chat.archive.get(identifier)
    checks["saved_chat_search_reopen_and_delete_policy"] = "PASS"
    try:
        require_access(db, "approved_folder_access")
    except ValueError:
        pass
    else:
        raise ValueError("A clean profile unexpectedly grants file access")
    checks["clean_profile_permissions_fail_closed"] = "PASS"
    window.set_microphone_muted(True)
    assert window.reactor.state.value == "MUTED" and window.voice.worker is None
    window.set_microphone_muted(False)
    assert window.reactor.state.value == "IDLE" and window.voice.worker is None
    checks["hard_mute_and_explicit_capture_only"] = "PASS"
    assert window.providers.provider.findText("Ollama") >= 0
    window.providers.provider.setCurrentText("Ollama")
    assert window.providers.auth.currentText() == "None"
    assert window.providers.address.text() == "http://127.0.0.1:11434/v1"
    assert not window.providers.jobs
    checks["explicit_ollama_configuration_no_service_start"] = "PASS"
    return checks


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
