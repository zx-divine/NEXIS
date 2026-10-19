"""Policy-enforced entry points for sensitive local-data and system changes."""

import json
from pathlib import Path

from nexis.core.permissions import Permissions
from nexis.core.results import Preview, Risk
from nexis.utils.validation import approved_root


class Management:
    def __init__(self, db, platform, permissions=None):
        self.db, self.platform = db, platform
        self.permissions = permissions or Permissions()

    def require(self, preview):
        if not self.permissions.authorise(preview):
            raise ValueError("Cancelled: permission was not granted.")

    def startup(self, enabled):
        self.require(
            Preview(
                "Change Windows startup",
                "Current-user Run registry key",
                "Enable startup" if enabled else "Disable startup",
                Risk.HIGH,
            )
        )
        self.platform.set_startup(enabled)

    def approve_folder(self, target):
        target = str(approved_root(target))
        self.require(
            Preview(
                "Approve search folder",
                target,
                "Allow filename searches inside this folder.",
                Risk.MEDIUM,
            )
        )
        roots = self.db.setting("search_roots")
        if target not in roots:
            self.db.set_setting("search_roots", [*roots, target])

    def export(self, target):
        target = Path(target)
        # Do not allow export to clobber the live database or its journal files.
        if target.resolve() in {
            self.db.path.resolve(),
            Path(str(self.db.path) + "-wal").resolve(),
            Path(str(self.db.path) + "-shm").resolve(),
            Path(str(self.db.path) + "-journal").resolve(),
        }:
            raise ValueError("Choose an export file outside the active database files.")
        if target.resolve().is_relative_to(self.db.path.parent.resolve()):
            raise ValueError("Export outside the NEXIS database directory.")
        if target.suffix.lower() != ".json":
            raise ValueError("Choose a .json export filename.")
        self.require(
            Preview(
                "Export personal data",
                str(target),
                "Includes snippet text, names and private paths. Store privately.",
                Risk.HIGH,
            )
        )
        target.write_text(json.dumps(self.db.export(), indent=2), encoding="utf-8")

    def delete_all(self):
        self.require(
            Preview(
                "Delete all NEXIS data",
                "Local NEXIS database",
                "Erase snippets, workflows, shortcuts, history and settings; "
                "disable Windows startup. This cannot be undone.",
                Risk.HIGH,
            )
        )
        self.platform.set_startup(False)
        self.db.reset()
