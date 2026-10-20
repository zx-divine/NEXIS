import json
import logging
import sqlite3
from pathlib import Path
from threading import Event
from time import monotonic

from nexis.actions.files import scoped
from nexis.core.commands import REGISTRY
from nexis.core.parser import parse
from nexis.core.permissions import Permissions
from nexis.core.launch_policy import launch_risk
from nexis.core.results import Preview, Result, Risk
from nexis.platform.windows import BUILTINS, Windows
from nexis.storage.repository import validate_workflow
from nexis.utils.validation import executable, name, url
from nexis.core.catalog import Catalog
from nexis.core.websites import resolve_website
from nexis.core.access import require_access
from nexis.platform.discovery import (
    verified_exe,
    valid_app_id,
    launch_registered,
    current_app_ids,
    known_folder,
)


class Engine:
    def __init__(self, db, platform=None, permissions=None):
        self.db = db
        self.platform = platform or Windows()
        self.permissions = permissions or Permissions()

    def prepare(self, request):
        if request.action not in REGISTRY:
            raise ValueError("Unknown command. Try help for supported commands.")
        spec = REGISTRY[request.action]
        if bool(spec.argument) != bool(request.argument):
            raise ValueError("Usage: " + spec.identifier.replace("_", " ") + " " + spec.argument)
        arg = request.argument
        target = arg
        risk = spec.risk
        payload = None
        if request.action == "open":
            direct_id = arg[4:] if arg.startswith("app:") else ""
            if direct_id and (
                len(direct_id) != 24 or any(c not in "0123456789abcdef" for c in direct_id)
            ):
                raise ValueError("Invalid catalog selection.")
            saved = (
                self.db.rows("SELECT * FROM shortcuts WHERE name=?", (arg.strip().lower(),))
                if not direct_id
                else []
            )
            catalog_matches = Catalog(self.db).matches(arg) if not direct_id else []
            website, unfamiliar = (
                (None, False) if saved or direct_id or catalog_matches else resolve_website(arg)
            )
            if website:
                return Preview(
                    "open",
                    website,
                    "Open this website in your default browser",
                    Risk.MEDIUM if unfamiliar else spec.risk,
                ), ("website", website)
            arg = arg.strip().casefold() if catalog_matches else name(arg) if not direct_id else arg
            if arg in BUILTINS:
                payload = ("builtin", arg)
            else:
                rows = self.db.rows("SELECT * FROM shortcuts WHERE name=?", (arg,))
                if not rows:
                    apps = (
                        [
                            r
                            for r in Catalog(self.db).rows()
                            if r["id"] == direct_id and r["available"]
                        ]
                        if direct_id
                        else catalog_matches
                    )
                    if len(apps) > 1:
                        raise ValueError(
                            "Multiple applications match. Select the intended entry on Applications → Discovered applications, or assign a unique alias."
                        )
                    if not apps:
                        raise ValueError(
                            "Application not found. Check the name or rescan Applications. For an unfamiliar website, use its full HTTPS address."
                        )
                    app = apps[0]
                    if app["kind"] == "exe":
                        target = verified_exe(app["target"])
                    elif app["kind"] == "appx" and valid_app_id(app["target"]):
                        target = app["target"]
                        if target not in current_app_ids():
                            raise ValueError(
                                "Application is no longer installed. Rescan Applications."
                            )
                    else:
                        raise ValueError("Invalid application registration.")
                    return Preview(
                        "open",
                        app["name"] + "\n" + target,
                        "Launch installed application using its verified target",
                        launch_risk(target, appx=app["kind"] == "appx"),
                    ), (app["kind"], target)
                row = rows[0]
                if row["kind"] == "website":
                    target = url(row["target"])
                elif row["kind"] == "application":
                    target = str(executable(row["target"]))
                    risk = launch_risk(target)
                else:
                    raise ValueError("Unsupported shortcut type.")
                payload = (row["kind"], target)
        elif request.action == "folder":
            target = scoped(Path(arg), self.db.setting("search_roots"))
            if not target.is_dir():
                raise ValueError("Choose an approved folder.")
            payload = target
        elif request.action == "downloads":
            target = known_folder("374DE290-123F-4565-9164-39C4925E467B")
            if not target.is_dir():
                raise ValueError("Windows Downloads folder is unavailable.")
            payload = target
        elif request.action == "copy":
            rows = self.db.rows("SELECT text FROM snippets WHERE name=?", (name(arg),))
            if not rows:
                raise ValueError("Snippet not found. Add it on the Snippets page.")
            payload = rows[0]["text"]
        elif request.action == "find":
            if not self.db.setting("search_roots"):
                raise ValueError("Approve search folders in Settings first.")
            if any(c in arg for c in "/\\") or len(arg) > 255:
                raise ValueError("Use a filename without path separators.")
        elif request.action == "run":
            rows = self.db.rows("SELECT steps FROM workflows WHERE name=?", (name(arg),))
            if not rows:
                raise ValueError("Workflow not found.")
            payload = validate_workflow(json.loads(rows[0]["steps"]))
            # Validate every step before offering to run; repeat at execution time.
            for step in payload:
                self.prepare(parse(step))
            target = "\n".join(payload)
        return Preview(request.action, str(target), spec.description, risk), payload

    def execute(
        self, text, cancel=None, on_step=lambda index, result: None, on_phase=lambda phase: None,
        pause=None,
    ):
        cancel = cancel or Event()
        action = "unknown"
        on_phase("PROCESSING")
        try:
            request = parse(text)
            action = request.action
            preview, payload = self.prepare(request)
            category = {
                "folder": "approved_folder_access",
                "downloads": "approved_folder_access",
                "find": "approved_folder_access",
                "copy": "clipboard_access",
                "run": "workflow_execution",
                "clear_history": "sensitive_operations",
            }.get(request.action)
            if request.action == "open":
                category = (
                    "browser_control" if payload[0] in {"website"} else "application_launching"
                )
            if category:
                require_access(self.db, category)
            if preview.risk >= Risk.HIGH:
                require_access(self.db, "sensitive_operations")
            self.permissions.confirm_low = self.db.setting("confirm_low_risk")
            if not self.permissions.authorise(preview):
                result = Result(False, "Cancelled: permission was not granted.")
            elif cancel.is_set():
                result = Result(False, "Cancelled before execution.")
            else:
                if category:
                    require_access(self.db, category)
                if preview.risk >= Risk.HIGH:
                    require_access(self.db, "sensitive_operations")
                on_phase("EXECUTING")
                result = self.dispatch(request, payload, cancel, on_step, pause, on_phase)
        except (ValueError, OSError, sqlite3.Error, TypeError, KeyError) as exc:
            logging.getLogger("nexis").warning("Action failed (%s)", type(exc).__name__)
            result = Result(
                False,
                str(exc)
                if isinstance(exc, ValueError)
                else "Action failed. Check target availability, access and local storage.",
            )
        try:
            self.db.record(action, result.ok)
        except sqlite3.Error:
            result.message += "\nHistory could not be saved; check local storage."
        return result

    def dispatch(self, request, payload, cancel, on_step, pause=None, on_phase=lambda phase: None):
        action, arg = REGISTRY[request.action].handler, request.argument
        if action == "open":
            kind, target = payload
            if kind == "builtin":
                self.platform.launch(target, builtin=True)
            elif kind in {"application", "exe"}:
                if kind in {"application", "exe"}:
                    # Revalidate at the effect boundary after any confirmation dialog.
                    target = str(executable(target))
                    if kind == "exe":
                        target = verified_exe(target)
                self.platform.launch(target)
            elif kind == "appx":
                launch_registered(target)
            else:
                self.platform.website(target)
            return Result(True, "Launch request accepted: " + arg)
        if action in {"folder", "downloads"}:
            self.platform.folder(payload)
            return Result(True, "Explorer launch request accepted.")
        if action == "copy":
            return Result(True, "Snippet ready for clipboard: " + arg, {"clipboard": payload})
        if action == "find":
            return Result(True, "Opening file search.", {"search": arg})
        if action == "help":
            return Result(
                True,
                "\n".join(
                    c.identifier.replace("_", " ") + " " + c.argument + " — " + c.description
                    for c in REGISTRY.values()
                ),
            )
        if action == "history":
            rows = self.db.rows(
                "SELECT timestamp,command,status FROM history ORDER BY id DESC LIMIT 50"
            )
            return Result(
                True,
                "\n".join(f"{r['timestamp']}  {r['command']}  {r['status']}" for r in rows)
                or "No history yet.",
            )
        if action == "clear_history":
            self.db.execute("DELETE FROM history")
            return Result(True, "Command history cleared.")
        if action == "run":
            messages = []
            deadline = monotonic() + 120
            for index, step in enumerate(payload, 1):
                reported_pause = False
                while pause and pause.is_set() and not cancel.is_set():
                    require_access(self.db, "workflow_execution")
                    if monotonic() >= deadline:
                        return Result(False, "Workflow reached its two-minute deadline while paused. Completed steps are retained.\n" + "\n".join(messages))
                    if not reported_pause:
                        on_phase("PAUSED")
                        reported_pause = True
                    cancel.wait(0.05)
                if cancel.is_set():
                    return Result(
                        False, "Workflow stopped before the next step.\n" + "\n".join(messages)
                    )
                require_access(self.db, "workflow_execution")
                if monotonic() >= deadline:
                    return Result(False, "Workflow reached its two-minute deadline. Completed steps are retained.\n" + "\n".join(messages))
                if reported_pause:
                    on_phase("EXECUTING")
                result = self.execute(step, cancel)
                on_step(index, result)
                messages.append(f"{index}. {result.message}")
                if not result.ok:
                    return Result(False, "Workflow stopped at failed step.\n" + "\n".join(messages))
            return Result(True, "Workflow completed.\n" + "\n".join(messages))
        raise ValueError("Unsupported action.")
