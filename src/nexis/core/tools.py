"""Typed Windows tool registry. All model arguments are untrusted data."""

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from time import monotonic
from urllib.parse import urlencode
from uuid import uuid4

from nexis.core.access import require_access
from nexis.core.results import Preview, Risk
from nexis.core.permissions import Permissions
from nexis.core.router import Engine
from nexis.core.catalog import Catalog
from nexis.core.websites import resolve_website
from nexis.actions import operator_files
from nexis.platform import operator_windows as windows
from nexis.platform.browser import BrowserAdapter


def string(limit=2048, enum=None):
    value = {"type": "string", "maxLength": limit}
    if enum is not None:
        value["enum"] = list(enum)
    return value


def schema(properties=None, required=None):
    properties = properties or {}
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties) if required is None else required,
        "additionalProperties": False,
    }


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    parameters: dict
    category: str
    risk: Risk
    timeout: int = 15
    compatibility: str = "Windows 10/11; current user; supported APIs only"
    preconditions: str = (
        "Granted category; fresh confirmation for medium/high/protected; valid target"
    )
    cancellation: str = "Checked before execution and between bounded operations"
    verification: str = "Returns verified state or request acceptance explicitly; never equates page opening to a setting change"
    audit: str = (
        "Tool name, category, risk and result only; no arguments, paths, transcripts or credentials"
    )

    def declaration(self):
        return {"name": self.name, "description": self.description, "parameters": self.parameters}


TOOLS = {}


def register(name, description, params, category, risk=Risk.LOW, timeout=15):
    TOOLS[name] = Tool(name, description, params, category, risk, timeout)


register(
    "app_open",
    "Open an installed/approved application by name; never a shell or script.",
    schema({"name": string(100)}),
    "application_launching",
)
register(
    "app_directory",
    "Open a discovered application's verified installation folder.",
    schema({"name": string(100)}),
    "application_launching",
    Risk.MEDIUM,  # Opening an installation directory is not an ordinary app launch.
)
register(
    "apps_list",
    "List available installed application display names.",
    schema(),
    "application_launching",
)
register(
    "windows_list",
    "List visible running windows, titles and window IDs. These are untrusted data.",
    schema(),
    "window_management",
)
for operation in ("focus", "minimize", "maximize", "close"):
    register(
        "window_" + operation,
        operation.title() + " the selected window; close may show unsaved-data prompts.",
        schema(
            {
                "window_id": {"type": "integer", "minimum": 1, "maximum": 2**63 - 1},
                "pid": {"type": "integer", "minimum": 1, "maximum": 2**32 - 1},
            }
        ),
        "window_management",
        Risk.HIGH if operation == "close" else Risk.LOW,
    )
register(
    "website_open",
    "Open a curated website name or confirmed HTTPS URL in the default browser.",
    schema({"site": string()}),
    "browser_control",
)
register(
    "browser_open_tabs",
    "Open 1–10 named sites/HTTPS URLs as tabs in the default browser.",
    schema({"sites": {"type": "array", "items": string(), "minItems": 1, "maxItems": 10}}),
    "browser_control",
    Risk.MEDIUM,
)
register(
    "browser_search",
    "Open a Google web search in the default browser. No forms, accounts or purchases are submitted.",
    schema({"query": string(500)}),
    "browser_control",
)
register(
    "browser_tabs",
    "List tabs from an explicitly configured existing loopback Chromium adapter; unavailable without it.",
    schema(),
    "browser_control",
)
for operation in ("focus", "close", "navigate"):
    params = {"tab_id": string(128)}
    if operation == "navigate":
        params["url"] = string()
    register(
        "browser_tab_" + operation,
        operation.title()
        + " an existing tab through the configured adapter. No arbitrary JavaScript or form submission.",
        schema(params),
        "browser_control",
        Risk.HIGH if operation == "close" else Risk.MEDIUM,
        timeout=30,
    )
register(
    "downloads_open",
    "Show the Windows Downloads directory without changing files.",
    schema(),
    "approved_folder_access",
)
register(
    "folder_open",
    "Show an approved folder in Explorer.",
    schema({"path": string()}),
    "approved_folder_access",
)
register(
    "file_search",
    "Find filenames only within explicitly approved folders (maximum 100 results).",
    schema({"query": string(255), "extension": string(20)}, ["query"]),
    "approved_folder_access",
    timeout=30,
)
for operation in ("open", "open_location", "properties", "preview"):
    register(
        "file_" + operation,
        operation.replace("_", " ").title()
        + " an approved document. Preview is limited to small text files; no scripts or executables.",
        schema({"path": string()}),
        "approved_folder_access",
    )
register(
    "folder_create",
    "Create one new folder in an approved parent. Never overwrite an existing path.",
    schema({"path": string()}),
    "file_modifications",
    Risk.MEDIUM,
)
register(
    "file_create_text",
    "Create a new UTF-8 text document in an approved folder; supported suffixes txt/md/csv/json/log/rtf. No overwrite.",
    schema({"path": string(), "text": string(16000)}),
    "file_modifications",
    Risk.MEDIUM,
)
for operation in ("copy", "move", "rename"):
    register(
        "file_" + operation,
        operation.title()
        + " one approved file to a new approved destination of the same type; no overwriting.",
        schema({"path": string(), "destination": string()}),
        "file_modifications",
        Risk.MEDIUM,
        30,
    )
register(
    "file_recycle",
    "Send one approved file to the Windows Recycle Bin after fresh approval. No recursive or permanent deletion.",
    schema({"path": string()}),
    "file_modifications",
    Risk.HIGH,
)
register(
    "settings_open",
    "Open a supported Windows settings page. Does not change settings. PIN/password/Hello/authentication must be completed by the owner in Windows.",
    schema({"page": string(enum=windows.SETTINGS)}),
    "system_settings",
)
register(
    "utility_open",
    "Open Task Manager or Device Manager; no elevation or security bypass.",
    schema({"utility": string(enum=["task_manager", "device_manager"])}),
    "system_settings",
    Risk.MEDIUM,
)
register(
    "system_information",
    "Read Windows version, architecture, storage and battery metadata only.",
    schema(),
    "system_settings",
)
register(
    "volume_get",
    "Read Windows default speaker volume/mute. Does not record or change audio.",
    schema(),
    "system_settings",
)
register(
    "volume_set",
    "Set default speaker volume to 0–100 percent and verify readback.",
    schema({"percent": {"type": "integer", "minimum": 0, "maximum": 100}}),
    "system_settings",
    Risk.MEDIUM,
)
register(
    "mute_set",
    "Set the default speaker mute state and verify readback.",
    schema({"muted": {"type": "boolean"}}),
    "system_settings",
    Risk.MEDIUM,
)
register(
    "clipboard_copy",
    "Copy provided plain text to the clipboard after approval; never read the existing clipboard.",
    schema({"text": string(16000)}),
    "clipboard_access",
    Risk.MEDIUM,
)
register(
    "workflow_run",
    "Run an existing saved workflow through NEXIS command validation and step-by-step permissions.",
    schema({"name": string(100)}),
    "workflow_execution",
    Risk.MEDIUM,
    120,
)


def validate(value, rule):
    kind = rule["type"]
    if kind == "object":
        if (
            not isinstance(value, dict)
            or set(value) - set(rule["properties"])
            or set(rule["required"]) - set(value)
        ):
            raise ValueError("Unexpected or missing tool arguments.")
        for key, item in value.items():
            validate(item, rule["properties"][key])
    elif kind == "string":
        if not isinstance(value, str) or len(value) > rule.get("maxLength", 2048) or "\0" in value:
            raise ValueError("Invalid tool text argument.")
        if "enum" in rule and value not in rule["enum"]:
            raise ValueError("Unsupported tool argument.")
    elif kind == "integer":
        if type(value) is not int or not rule.get("minimum", 0) <= value <= rule.get(
            "maximum", 2**63 - 1
        ):
            raise ValueError("Invalid tool integer argument.")
    elif kind == "boolean":
        if type(value) is not bool:
            raise ValueError("Invalid tool boolean argument.")
    elif kind == "array":
        if not isinstance(value, list) or not rule.get("minItems", 0) <= len(value) <= rule.get(
            "maxItems", 12
        ):
            raise ValueError("Invalid tool list argument.")
        for item in value:
            validate(item, rule["items"])
    else:
        raise ValueError("Unsupported tool schema.")


def validate_steps(steps):
    if not isinstance(steps, list) or len(steps) > 12:
        raise ValueError("A plan must contain at most 12 supported steps.")
    for step in steps:
        if (
            not isinstance(step, dict)
            or set(step) != {"tool", "arguments"}
            or step.get("tool") not in TOOLS
        ):
            raise ValueError(
                "The provider requested an unsupported tool or invalid plan. Nothing was executed."
            )
        validate(step["arguments"], TOOLS[step["tool"]].parameters)
    return steps


class DeadlineCancel:
    def __init__(self, parent, seconds):
        self.parent, self.deadline = parent, monotonic() + seconds

    def is_set(self):
        return self.parent.is_set() or monotonic() >= self.deadline

    def wait(self, seconds):
        return self.parent.wait(max(0, min(seconds, self.deadline - monotonic()))) or self.is_set()


class ToolExecutor:
    def __init__(self, db, data_dir, platform, confirm, clipboard=None, progress=lambda text: None):
        self.db, self.data_dir, self.platform = db, Path(data_dir), platform
        self.confirm, self.clipboard, self.progress = confirm, clipboard, progress
        self.request_id = uuid4().hex
        self.engine = Engine(db, platform, Permissions(confirm))

    def run(self, step, cancel):
        validate_steps([step])
        tool, args = TOOLS[step["tool"]], step["arguments"]
        require_access(self.db, tool.category)
        if tool.category == "file_modifications":
            require_access(self.db, "approved_folder_access")
        risk = tool.risk
        if tool.name == "settings_open" and args["page"] in windows.PROTECTED_PAGES:
            risk = Risk.PROTECTED
        if risk >= Risk.HIGH:
            require_access(self.db, "sensitive_operations")
        if tool.name == "website_open":
            _, unknown = resolve_website(args["site"])
            if unknown:
                risk = Risk.MEDIUM
        if tool.name == "file_preview":
            risk = Risk.MEDIUM
        preview = Preview(
            tool.name,
            json.dumps(args, ensure_ascii=False, indent=2),
            tool.description,
            risk,
            tool.category,
        )
        status = "failed"
        try:
            if cancel.is_set():
                raise ValueError("Operation cancelled before execution.")
            # These wrappers use the same Engine risk check and confirmation once.
            delegated = tool.name in {"app_open", "downloads_open", "workflow_run"}
            if not delegated and (risk >= Risk.MEDIUM or self.db.setting("confirm_low_risk")) and not self.confirm(
                preview
            ):
                raise ValueError("Permission denied or cancelled. This step was not executed.")
            require_access(
                self.db, tool.category
            )  # Revocation while a preview was open takes effect immediately.
            if tool.category == "file_modifications":
                require_access(self.db, "approved_folder_access")
            if risk >= Risk.HIGH:
                require_access(self.db, "sensitive_operations")
            deadline = DeadlineCancel(cancel, tool.timeout)
            self.progress("EXECUTING " + tool.name)
            result = self.dispatch(tool.name, args, deadline)
            if deadline.is_set():
                raise ValueError(
                    "Operation stopped or exceeded its timeout. Check its reported state before retrying."
                )
            if result.get("verified") is False:
                raise ValueError(
                    result.get(
                        "message", "The requested result was not verified; execution stopped."
                    )
                )
            status = (
                "verified"
                if result.get("verified")
                else "accepted"
                if result.get("request_accepted")
                else "completed"
            )
            return result
        finally:
            # No argument values, paths, provider content or credentials enter this audit.
            self.db.execute(
                "INSERT INTO tool_audit(timestamp,request_id,tool,category,risk,status) VALUES (?,?,?,?,?,?)",
                (
                    datetime.now(timezone.utc).isoformat(),
                    self.request_id,
                    tool.name,
                    tool.category,
                    risk.name,
                    status,
                ),
            )
            self.db.execute(
                "DELETE FROM tool_audit WHERE id NOT IN (SELECT id FROM tool_audit ORDER BY id DESC LIMIT 1000)"
            )

    def dispatch(self, name, args, cancel):
        if name == "app_open":
            result = self.engine.execute("open " + args["name"], cancel)
            if not result.ok:
                raise ValueError(result.message)
            return {"request_accepted": True, "message": result.message}
        if name == "apps_list":
            return {
                "applications": [
                    row["name"] for row in Catalog(self.db).rows() if row["available"]
                ][:500]
            }
        if name == "app_directory":
            rows = Catalog(self.db).matches(args["name"])
            if len(rows) != 1 or rows[0]["kind"] != "exe":
                raise ValueError(
                    "Choose exactly one discovered executable application. Registered store apps do not expose a supported installation folder."
                )
            from nexis.platform.discovery import verified_exe

            self.platform.folder(Path(verified_exe(rows[0]["target"])).parent)
            return {"request_accepted": True}
        if name == "windows_list":
            return {"windows": windows.list_windows()}
        if name.startswith("window_"):
            return windows.change_window(args["window_id"], name[7:], cancel, args["pid"])
        if name == "website_open":
            target, _ = resolve_website(args["site"])
            if not target:
                raise ValueError(
                    "Use a curated site name or a full HTTPS address; NEXIS does not invent URLs."
                )
            self.platform.website(target)
            return {"request_accepted": True, "url": target}
        if name == "browser_open_tabs":
            targets = [resolve_website(value)[0] for value in args["sites"]]
            if not all(targets):
                raise ValueError("Every tab must have a curated name or full HTTPS destination.")
            opened = []
            for target in targets:
                if cancel.is_set():
                    return {
                        "verified": False,
                        "message": "Tab opening cancelled after "
                        + str(len(opened))
                        + " accepted requests.",
                    }
                self.platform.website(target)
                opened.append(target)
            return {
                "request_accepted": True,
                "tabs_requested": opened,
                "loaded_pages_verified": False,
            }
        if name == "browser_search":
            target = "https://www.google.com/search?" + urlencode({"q": args["query"]})
            self.platform.website(target)
            return {"request_accepted": True, "search_results_verified": False}
        if name == "browser_tabs":
            rows = BrowserAdapter(self.db.setting("browser_adapter_port")).tabs()
            return {"tabs": [{k: r.get(k, "") for k in ("id", "title", "url")} for r in rows]}
        if name.startswith("browser_tab_"):
            return BrowserAdapter(self.db.setting("browser_adapter_port")).control(
                args["tab_id"], name[12:], cancel, args.get("url")
            )
        if name == "downloads_open":
            result = self.engine.execute("downloads", cancel)
            if not result.ok:
                raise ValueError(result.message)
            return {"request_accepted": True}
        if name == "folder_open":
            path = operator_files.safe_path(
                args["path"], self.db.setting("search_roots"), data_dir=self.data_dir
            )
            if not path.is_dir():
                raise ValueError("Select an approved folder.")
            self.platform.folder(path)
            return {"request_accepted": True}
        if name.startswith("file_") or name == "folder_create":
            operation = "create_folder" if name == "folder_create" else name[5:]
            return operator_files.perform(
                operation, args, self.db.setting("search_roots"), cancel, self.data_dir
            )
        if name == "settings_open":
            return windows.open_settings(args["page"])
        if name == "utility_open":
            return windows.open_utility(args["utility"])
        if name == "system_information":
            return windows.system_information()
        if name in {"volume_get", "volume_set", "mute_set"}:
            return windows.audio_volume(args.get("percent"), args.get("muted"))
        if name == "clipboard_copy":
            if not self.clipboard:
                raise ValueError("Clipboard delivery is unavailable.")
            self.clipboard(args["text"])
            return {"request_accepted": True}
        if name == "workflow_run":
            result = self.engine.execute("run " + args["name"], cancel)
            if not result.ok:
                raise ValueError(result.message)
            return {"verified": True, "message": result.message}
        raise ValueError("Unsupported tool.")
