from nexis.platform.speech import SpeechService
from nexis.ui.branding import WelcomeWizard
from nexis.ui.main_window import MainWindow
from nexis.ui.setup_services import ProviderPanel, Task


def test_simple_onboarding_and_reused_key(qtbot, db, tmp_path):
    wizard = WelcomeWizard(db)
    qtbot.addWidget(wizard)
    assert wizard.pageIds() == list(range(9))
    assert wizard.provider.address.text() == "https://openrouter.ai/api/v1"
    assert not wizard.provider.advanced.isChecked()
    wizard.provider.key.setText("fixture-api-key")
    wizard.provider.model.setCurrentText("fixture-model")
    wizard.provider.save()
    wizard.provider.manager.select(wizard.provider.current_id)
    second = ProviderPanel(db.path.parent)
    qtbot.addWidget(second)
    assert second.key.text() == ""
    assert second.profile()["key"] == "fixture-api-key"
    assert second.profile()["model"] == "fixture-model"
    second.provider.setCurrentText("OmniRoute")
    assert second.profile()["key"] == ""  # Never carry credentials to a different host.
    wizard.accept()
    assert db.setting("welcome_completed")


def test_shutdown_cancels_jobs_before_window_disappears(qtbot, db, tmp_path, platform):
    window = MainWindow(db, tmp_path, platform)
    qtbot.addWidget(window)
    window.show()
    task = Task(lambda cancel, progress: cancel.wait(5), window)
    window.ai_jobs.append(task)
    task.start()
    qtbot.waitUntil(task.isRunning)
    window.close()
    qtbot.waitUntil(lambda: not task.isRunning() and not window.isVisible(), timeout=3000)
    assert task.cancel.is_set()


def test_startup_never_prechecks_network_or_opens_microphone(
    qtbot, db, tmp_path, platform, monkeypatch
):
    import nexis.ui.setup_services as services

    calls = []
    monkeypatch.setattr(services, "discover", lambda cancel, approved: ([], []))
    monkeypatch.setattr(
        services.urllib
        if hasattr(services, "urllib")
        else __import__("urllib.request", fromlist=["urlopen"]),
        "urlopen",
        lambda *a, **k: calls.append("network"),
    )
    window = MainWindow(db, tmp_path, platform)
    qtbot.addWidget(window)
    window.show()
    window.start_services()
    qtbot.waitUntil(lambda: not any(job.isRunning() for job in window.discovery.jobs))
    assert window.voice.worker is None
    assert not calls and not platform.calls
    window.close()
    qtbot.waitUntil(
        lambda: not any(job and job.isRunning() for job in window.background_jobs()), timeout=5000
    )


def test_speech_initializes_with_missing_saved_voice_and_cancels(qtbot, monkeypatch):
    import win32com.client

    calls = []

    class Token:
        Id = "default"

        def GetDescription(self):
            return "Default Windows voice"

    class Tokens:
        Count = 1

        def Item(self, index):
            return Token()

    class Speaker:
        def GetVoices(self):
            return Tokens()

        def Speak(self, text, flags):
            calls.append((text, flags))

    monkeypatch.setattr(win32com.client, "Dispatch", lambda name: Speaker())
    worker = SpeechService("removed voice")
    statuses = []
    worker.status.connect(statuses.append)
    worker.start()
    qtbot.waitUntil(lambda: any("ready" in value for value in statuses))
    worker.say("Hello <literal>")
    qtbot.waitUntil(lambda: any(text == "Hello <literal>" and flags & 16 for text, flags in calls))
    worker.cancel.set()
    qtbot.waitUntil(lambda: not worker.isRunning())


def test_task_failure_is_isolated_and_cancelled_result_suppressed(qtbot):
    def failure(cancel, progress):
        raise RuntimeError("sensitive internals")

    task = Task(failure)
    failed = []
    task.failed.connect(failed.append)
    task.start()
    qtbot.waitUntil(lambda: not task.isRunning())
    qtbot.waitUntil(lambda: bool(failed))
    assert "sensitive" not in failed[0]
    cancel = Task(lambda flag, progress: flag.wait(5))
    results = []
    cancel.result.connect(results.append)
    cancel.start()
    cancel.cancel.set()
    qtbot.waitUntil(lambda: not cancel.isRunning())
    assert not results


def test_async_catalog_storage_failure_is_reported(qtbot, db, tmp_path, platform, monkeypatch):
    window = MainWindow(db, tmp_path, platform)
    qtbot.addWidget(window)

    def fail(apps):
        raise OSError("sensitive storage details")

    monkeypatch.setattr(window.discovery.catalog, "update", fail)
    window.discovery.discovered(([], []))
    assert "could not complete" in window.discovery.status.text()
    assert "sensitive" not in window.discovery.status.text()


def test_device_and_voice_selector_signals_save_preferences(qtbot, db, tmp_path, platform):
    window = MainWindow(db, tmp_path, platform)
    qtbot.addWidget(window)
    panel = window.settings_page.voice_setup
    panel.voices.addItem("Fixture voice", "voice-fixture")
    panel.voices.setCurrentIndex(1)
    assert db.setting("tts_voice") == "voice-fixture"
    panel.input.addItem("Fixture microphone", "mic-fixture")
    panel.input.setCurrentIndex(1)
    assert db.setting("audio_input") == "mic-fixture"


def test_data_reset_refreshes_new_catalog_and_voice_controls(
    qtbot, db, tmp_path, platform, monkeypatch
):
    from types import SimpleNamespace

    window = MainWindow(db, tmp_path, platform)
    qtbot.addWidget(window)
    db.execute("INSERT INTO app_catalog VALUES ('fixture','Fixture','unavailable','exe','test',0)")
    window.discovery.refresh()
    window.settings_page.voice_setup.tts_enabled.setChecked(False)
    assert window.discovery.list.count() == 1
    monkeypatch.setattr(
        window.settings_page, "management", lambda: SimpleNamespace(delete_all=db.reset)
    )
    window.settings_page.delete()
    assert window.discovery.list.count() == 0
    assert window.settings_page.voice_setup.tts_enabled.isChecked()


def test_first_run_save_updates_already_constructed_settings(qtbot, db, platform):
    window = MainWindow(db, db.path.parent, platform)
    qtbot.addWidget(window)
    assert window.settings_page.provider.saved is None
    wizard = WelcomeWizard(db)
    qtbot.addWidget(wizard)
    wizard.show()
    for _ in range(5):
        wizard.next()
    assert wizard.currentId() == 5
    wizard.provider.provider.setCurrentText("OmniRoute")
    wizard.provider.key.setText("first-run-fixture-key")
    wizard.provider.model.setCurrentText("first-run-model")
    wizard.provider.save()
    wizard.provider.manager.select(wizard.provider.current_id)
    wizard.next()
    assert wizard.currentId() == 6
    wizard.accept()
    window.settings_page.provider.reload_saved()
    profile = window.settings_page.provider.profile()
    assert profile["key"] == "first-run-fixture-key"
    assert profile["model"] == "first-run-model"
    assert window.settings_page.provider.key.text() == ""
