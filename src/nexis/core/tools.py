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
        "Granted category; validated target; shared operation authorization policy"
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
    "Open a curated website, bare domain or explicit HTTP(S) URL. Optional browser is an installed registered name (Chrome, Edge, Firefox, Brave, Opera, etc.). Omit for the Windows default. Never silently substitute a browser; page loading is not verified.",
    schema({"site": string(8192), "browser": string(100)}, ["site"]),
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
    "Find filenames within approved folders (maximum 100 results). Optional size bounds are bytes and modified bounds are Unix UTC seconds. Use * for all filenames with filters; never search outside approved folders.",
    schema({"query": string(255), "extension": string(20),
            **{key: {"type": "integer", "minimum": 0, "maximum": 1099511627776}
               for key in ("min_bytes", "max_bytes", "modified_after", "modified_before")}}, ["query"]),
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
register("pc_health", "Read local PC Health metadata without changing settings.", schema(), "system_settings")
register("radio_set", "Set the explicitly requested Wi-Fi/Bluetooth state using Windows APIs and verify readback.",
         schema({"kind": string(enum=["wifi", "bluetooth"]), "state": string(enum=["on", "off"])}),
         "system_settings", timeout=30)
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


def prepare_step(db, data_dir, step):
    """Resolve validation and risk before requesting approval; repeat at the effect boundary."""
    validate_steps([step])
    tool, args = TOOLS[step["tool"]], step["arguments"]
    risk, target = tool.risk, json.dumps(args, ensure_ascii=False, indent=2)
    reason = "This operation affects private information or makes a meaningful change."
    reversible = "Review the resource and effect before approving."
    if tool.name == "website_open":
        target, _ = resolve_website(args["site"])
        if not target:
            raise ValueError("Use a validated HTTP(S) website or domain name.")
        from nexis.platform.website_launcher import browser_name
        browser_name(args.get("browser", "default"))
    if tool.name == "browser_open_tabs":
        if not all(resolve_website(value)[0] for value in args["sites"]):
            raise ValueError("Every tab needs a validated HTTP(S) website.")
    if tool.name in {"folder_open", "file_open", "file_properties", "file_open_location", "file_preview"}:
        path = operator_files.safe_path(args["path"], db.setting("search_roots"), data_dir=data_dir)
        target = str(path)
        if tool.name == "folder_open" and not path.is_dir():
            raise ValueError("Choose an existing approved folder.")
        if tool.name == "file_open" and (not path.is_file() or path.suffix.casefold() not in operator_files.OPEN_SUFFIXES):
            raise ValueError("Only supported ordinary documents/media may be opened; scripts and executables are blocked.")
    if tool.name == "settings_open" and args["page"] in windows.PROTECTED_PAGES:
        risk = Risk.HIGH
        reason = "This opens a sensitive Windows account, authentication or security interface. Only you can complete changes in Windows."
        reversible = "Opening the page changes nothing. Any later Windows changes have their own consequences."
    if tool.name == "utility_open" and args["utility"] == "task_manager":
        risk = Risk.LOW
    if tool.name == "file_preview":
        risk = Risk.MEDIUM
        reason = "Document contents will be read and may enter the active AI conversation."
        reversible = "A provider transmission cannot be recalled. Deny to keep contents local."
    if tool.name == "file_recycle":
        reason = "The selected file will be removed from its current location."
        reversible = "Windows Recycle Bin recovery may be possible; it is not guaranteed."
    return Preview(tool.name, target, tool.description, risk, tool.category, reason, reversible)


class DeadlineCancel:
    def __init__(self, parent, seconds):
        self.parent, self.deadline = parent, monotonic() + seconds

    def is_set(self):
        return self.parent.is_set() or monotonic() >= self.deadline

    def wait(self, seconds):
        return self.parent.wait(max(0, min(seconds, self.deadline - monotonic()))) or self.is_set()


class ToolExecutor:
    def __init__(self, db, data_dir, platform, confirm, clipboard=None, progress=lambda text: None, request_text="", allow_radio=True):
        self.db, self.data_dir, self.platform = db, Path(data_dir), platform
        self.confirm, self.clipboard, self.progress = confirm, clipboard, progress
        self.request_id = uuid4().hex
        self.engine = Engine(db, platform, Permissions(confirm), allow_radio=allow_radio)
        self.request_text = request_text
        self.allow_radio = allow_radio

    def run(self, step, cancel):
        preview = prepare_step(self.db, self.data_dir, step)
        tool, args = TOOLS[step["tool"]], step["arguments"]
        require_access(self.db, tool.category)
        if tool.category == "file_modifications":
            require_access(self.db, "approved_folder_access")
        risk = preview.risk
        if risk >= Risk.HIGH:
            require_access(self.db, "sensitive_operations")
        if tool.name == "radio_set":
            if not self.allow_radio:
                raise ValueError("Review and send the voice transcript before changing a radio.")
            from nexis.core.intents import local_command
            expected = "radio " + args["kind"] + " " + args["state"]
            if self.request_text != expected and local_command(self.request_text) != expected:
                raise ValueError("Radio changes require a single explicit user request for that radio and state. Model-generated or indirect radio changes are not authorized.")
        status = "failed"
        try:
            if cancel.is_set():
                raise ValueError("Operation cancelled before execution.")
            # These wrappers use the same Engine risk check and confirmation once.
            delegated = tool.name in {"app_open", "downloads_open", "workflow_run"}
            if not delegated and not Permissions(self.confirm, self.db.setting("confirm_low_risk")).authorise(preview):
                raise ValueError("Permission denied or cancelled. This step was not executed.")
            self.progress("EXECUTING " + tool.name)
            require_access(
                self.db, tool.category
            )  # Revocation while a preview was open takes effect immediately.
            if tool.category == "file_modifications":
                require_access(self.db, "approved_folder_access")
            if risk >= Risk.HIGH:
                require_access(self.db, "sensitive_operations")
            deadline = DeadlineCancel(cancel, tool.timeout)
            if deadline.is_set():
                raise ValueError("Operation cancelled or expired before dispatch; no action was submitted.")
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
        if cancel.is_set():
            raise ValueError("Operation cancelled or expired before dispatch; no action was submitted.")
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
            browser = args.get("browser", "default")
            from nexis.platform.website_launcher import browser_name

            browser = browser_name(browser)
            if browser == "default":
                evidence = self.platform.website(target)
            else:
                evidence = self.platform.website(target, browser=browser, cancel=cancel)
            return {**(evidence or {}), "request_accepted": True, "url": target,
                    "loaded_page_verified": False}
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
        if name == "pc_health":
            from nexis.platform.health import health_snapshot
            return health_snapshot(self.data_dir, cancel)
        if name == "radio_set":
            from nexis.platform.radios import set_state
            return set_state(args["kind"], args["state"], cancel)
        if name in {"volume_get", "volume_set", "mute_set"}:
            return windows.audio_volume(args.get("percent"), args.get("muted"))
        if name == "clipboard_copy":
            if not self.clipboard:
                raise ValueError("Clipboard delivery is unavailable.")
            self.clipboard(args["text"])
            return {"request_accepted": True}
        if name == "workflow_run":
            def deliver(index, step_result):
                if cancel.is_set():
                    raise ValueError("Workflow cancelled before result delivery.")
                if step_result.ok and "clipboard" in step_result.data:
                    require_access(self.db, "clipboard_access")
                    if not self.clipboard:
                        raise ValueError("Clipboard delivery is unavailable; the workflow did not complete.")
                    self.clipboard(step_result.data["clipboard"])

            result = self.engine.execute("run " + args["name"], cancel, on_step=deliver)
            if not result.ok:
                raise ValueError(result.message)
            return {"request_accepted": True, "message": result.message}
        raise ValueError("Unsupported tool.")
