import json
import logging
import sqlite3
from threading import Event
from time import monotonic

from nexis.core.commands import REGISTRY
from nexis.core.parser import parse
from nexis.core.permissions import Permissions
from nexis.core.launch_policy import launch_risk
from nexis.core.results import Preview, Result, Risk
from nexis.platform.windows import BUILTINS, Windows
from nexis.storage.repository import validate_workflow
from nexis.utils.validation import executable, name
from nexis.core.catalog import Catalog
from nexis.core.websites import resolve_website, split_browser, website_url
from nexis.core.access import require_access
from nexis.platform.discovery import (
    verified_exe,
    valid_app_id,
    launch_registered,
    current_app_ids,
    known_folder,
)


class Engine:
    def __init__(self, db, platform=None, permissions=None, allow_radio=True):
        self.db = db
        self.platform = platform or Windows()
        self.permissions = permissions or Permissions()
        self.allow_radio = allow_radio

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
        from nexis.core.intents import command_tool
        step = command_tool(request)
        if step:
            if step["tool"] == "radio_set" and not self.allow_radio:
                raise ValueError("Review the recognized transcript and click Retry / send transcript before changing a radio. Voice recognition alone cannot authorize this change.")
            from nexis.core.tools import prepare_step
            return prepare_step(self.db, self.db.path.parent, step), ("tool", step)
        if request.action == "open":
            arg, browser = split_browser(arg)
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
                    "Submit this website to " + ("your Windows default browser" if browser == "default" else browser),
                    Risk.LOW,
                ), ("website", website, browser)
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
                    if browser != "default":
                        raise ValueError("An explicit browser can only be used with a website destination.")
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
                        "application_launching",
                        "Executable identity, signature, purpose or requested privilege needs review. Opening this target runs code with your Windows permissions.",
                        "A running program may change data; those changes may not be reversible.",
                    ), (app["kind"], target)
                row = rows[0]
                if row["kind"] == "website":
                    target = website_url(row["target"])
                elif row["kind"] == "application":
                    target = str(executable(row["target"]))
                    risk = launch_risk(target)
                else:
                    raise ValueError("Unsupported shortcut type.")
                payload = (row["kind"], target, browser) if row["kind"] == "website" else (row["kind"], target)
            if browser != "default" and payload[0] != "website":
                raise ValueError("An explicit browser can only be used with a website destination.")
        elif request.action == "folder":
            from nexis.actions.operator_files import safe_path
            target = safe_path(arg, self.db.setting("search_roots"), data_dir=self.db.path.parent)
            if not target.is_dir():
                raise ValueError("Choose an approved folder.")
            payload = target
        elif request.action in {"downloads", "documents", "desktop"}:
            identifier = {"downloads": "374DE290-123F-4565-9164-39C4925E467B",
                          "documents": "FDD39AD0-238F-46AF-ADB4-6C85480369C7",
                          "desktop": "B4BFCC3A-DB2C-424C-B029-7FE99A87C641"}[request.action]
            target = known_folder(identifier)
            if not target.is_dir():
                raise ValueError("Windows Downloads folder is unavailable.")
            from nexis.actions.operator_files import safe_path
            target = safe_path(str(target), [str(target)])
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
        if request.action == "open" and risk >= Risk.HIGH:
            return Preview(request.action, str(target), spec.description, risk, "application_launching",
                           "This executable has not qualified as an ordinary trusted application. Opening it runs code with your Windows permissions.",
                           "A running program may change data; those changes may not be reversible."), payload
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
                "documents": "approved_folder_access",
                "desktop": "approved_folder_access",
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
            delegated = isinstance(payload, tuple) and payload[0] == "tool"
            if not delegated and not self.permissions.authorise(preview):
                result = Result(False, "Cancelled: permission was not granted.")
            elif cancel.is_set():
                result = Result(False, "Cancelled before execution.")
            else:
                on_phase("EXECUTING")
                if category:
                    require_access(self.db, category)
                if preview.risk >= Risk.HIGH:
                    require_access(self.db, "sensitive_operations")
                fresh_preview, fresh_payload = self.prepare(request)
                if fresh_preview != preview or fresh_payload != payload:
                    raise ValueError("The resolved target changed during authorization. Retry and review the current target.")
                result = self.dispatch(request, fresh_payload, cancel, on_step, pause, on_phase)
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
        if cancel.is_set():
            return Result(False, "Cancelled or expired before dispatch; no action was submitted.")
        action, arg = REGISTRY[request.action].handler, request.argument
        if action == "tool":
            from nexis.core.tools import ToolExecutor
            intent = request.action + " " + request.argument
            if request.action == "radio":
                intent = "radio " + payload[1]["arguments"]["kind"] + " " + payload[1]["arguments"]["state"]
            executor = ToolExecutor(self.db, self.db.path.parent, self.platform, self.permissions.confirm,
                                    request_text=intent, allow_radio=self.allow_radio)
            data = executor.run(payload[1], cancel)
            if request.action in {"system_information", "pc_health"}:
                message = request.action.replace("_", " ").title() + ":\n" + json.dumps(data, ensure_ascii=False, indent=2)
            elif request.action == "settings":
                message = "Windows settings launch request accepted. No setting was changed by NEXIS."
            else:
                message = data.get("message", "Launch request accepted; completion has not been independently verified.")
            return Result(True, message, data)
        if action == "open":
            kind, target = payload[:2]
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
                browser = payload[2] if len(payload) > 2 else "default"
                if browser == "default":
                    self.platform.website(target)
                else:
                    self.platform.website(target, browser=browser, cancel=cancel)
                return Result(True, "Browser launch request submitted: " + arg + ". Page load has not been independently verified.")
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
