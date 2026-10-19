import pytest
from nexis.storage.database import Database


@pytest.fixture
def db(tmp_path):
    database = Database(tmp_path / "data" / "test.db")
    # Legacy feature fixtures explicitly grant categories; fresh-default tests use a separate DB.
    from nexis.core.access import CATEGORIES

    database.set_setting("system_access_acknowledged", True)
    database.set_setting(
        "access_permissions", {key: key != "terminal_commands" for key in CATEGORIES}
    )
    yield database
    database.close()


class FakePlatform:
    def __init__(self):
        self.calls = []
        self.startup = False

    def launch(self, target, builtin=False):
        self.calls.append(("launch", target, builtin))

    def website(self, target):
        self.calls.append(("website", target))

    def folder(self, target):
        self.calls.append(("folder", target))

    def startup_enabled(self):
        return self.startup

    def set_startup(self, enabled):
        self.startup = enabled


@pytest.fixture
def platform():
    return FakePlatform()
