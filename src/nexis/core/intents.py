"""Narrow, single-operation local intents. Compound requests stay with the planner."""
import re
from pathlib import Path


def local_command(text):
    value = re.sub(r"^(?:hey\s+nex[ui]s[,!]?\s+)?(?:please\s+)?", "", text.strip(), flags=re.I)
    normal = re.sub(r"\s+", " ", value.casefold().rstrip(".!?"))
    radio = re.fullmatch(r"(?:(?:turn|switch) )?(wi[ -]?fi|bluetooth) (on|off)", normal)
    if radio:
        return "radio " + ("wifi" if radio[1] != "bluetooth" else "bluetooth") + " " + radio[2]
    if normal in {"show system information", "system information", "show device information"}:
        return "system_information"
    if normal in {"show pc health", "pc health", "open pc health"}:
        return "pc_health"
    if normal in {"open settings", "open windows settings"}:
        return "settings settings"
    if normal.startswith("open "):
        target = normal[5:]
        aliases = {"file explorer": "explorer", "task manager": "task_manager",
                   "calculator": "calculator", "notepad": "notepad", "paint": "paint"}
        if target in aliases:
            return "open " + aliases[target]
        if target in {"downloads", "documents", "desktop"}:
            return target
        # Preserve the spelling and punctuation of paths, never treat a path as code.
        raw = value[5:].strip().strip('"')
        if Path(raw).is_absolute():
            return "document " + raw
    return None


def command_tool(request):
    if request.action in {"system_information", "pc_health"}:
        return {"tool": request.action, "arguments": {}}
    if request.action == "settings":
        return {"tool": "settings_open", "arguments": {"page": request.argument}}
    if request.action == "document":
        return {"tool": "folder_open" if Path(request.argument).is_dir() else "file_open",
                "arguments": {"path": request.argument}}
    if request.action == "radio":
        pieces = request.argument.split()
        if len(pieces) != 2:
            raise ValueError("Usage: radio wifi|bluetooth on|off")
        return {"tool": "radio_set", "arguments": {"kind": pieces[0], "state": pieces[1]}}
    return None
