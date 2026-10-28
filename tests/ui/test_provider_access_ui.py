"""First-run access and provider switching controls, without live API keys."""

from nexis.storage.database import Database
from nexis.ui.branding import WelcomeWizard
from nexis.ui.providers_page import AIProvidersPage
from nexis.ui.system_access import SystemAccessPanel
from nexis.core.provider_manager import ProviderManager


def sample(endpoint="https://gateway.example/v1"):
    return {
        "provider": "Custom API Gateway",
        "display_name": "Fixture",
        "endpoint": endpoint,
        "key": "PRIVATE-UI-FIXTURE",
        "model": "fixture-model",
        "headers": {"X-Private": "header-fixture-secret"},
    }


def test_manager_editor_hides_keys_and_does_not_forward_to_changed_destination(qtbot, tmp_path):
    manager = ProviderManager(tmp_path)
    identifier = manager.save(sample())
    manager.select(identifier)
    page = AIProvidersPage(tmp_path)
    qtbot.addWidget(page)
    assert page.key.text() == "" and page.headers.text() == ""
    assert page.profile()["key"] == "PRIVATE-UI-FIXTURE"
    page.address.setText("https://different.example/v1")
    assert page.profile()["key"] == "" and page.profile()["headers"] == {}


def test_declined_switch_and_failed_save_keep_default(qtbot, tmp_path, monkeypatch):
    manager = ProviderManager(tmp_path)
    original = manager.save(sample())
    other = manager.save(sample("https://other.example/v1"))
    manager.select(original)
    page = AIProvidersPage(tmp_path)
    qtbot.addWidget(page)
    page.profiles.setCurrentRow(
        next(i for i, p in enumerate(page.profile_rows) if p["id"] == other)
    )
    monkeypatch.setattr(page, "approve_switch", lambda: False)
    page.select_default()
    assert manager.active()["id"] == original
    monkeypatch.setattr(page, "approve_switch", lambda: True)
    page.address.setText("file:///bad")
    page.save_and_select()
    assert manager.active()["id"] == original


def test_first_run_requires_real_acknowledgment_and_starts_no_microphone(qtbot, tmp_path):
    database = Database(tmp_path / "fresh.db")
    wizard = WelcomeWizard(database)
    wizard.preferred_name.setText("Fixture user")
    qtbot.addWidget(wizard)
    wizard.show()
    wizard.next()
    wizard.next()
    assert wizard.currentId() == 2
    assert not wizard.access.acknowledged.isChecked()
    assert not wizard.currentPage().isComplete()
    assert not any(choice.isChecked() for choice in wizard.access.choices.values())
    wizard.accept()
    assert not database.setting("welcome_completed")
    wizard.reject()
    database.close()


def test_access_revocation_is_persisted_without_erasing_other_preferences(qtbot, db):
    db.set_setting("reduced_motion", True)
    panel = SystemAccessPanel(db)
    qtbot.addWidget(panel)
    panel.revoke()
    assert not any(db.setting("access_permissions").values())
    assert db.setting("reduced_motion")
