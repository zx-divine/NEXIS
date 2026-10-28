import json

from nexis.core.commands import REGISTRY
from nexis.core.parser import parse
from nexis.platform.windows import BUILTINS
from nexis.utils.validation import executable, name
from nexis.core.websites import website_url


class Repository:
    def __init__(self, db):
        self.db = db

    def save_snippet(self, title, category, text):
        title = name(title)
        if not text or len(text) > 100000 or len(category) > 100:
            raise ValueError("Enter snippet text (up to 100,000 characters) and a short category.")
        self.db.execute("INSERT OR REPLACE INTO snippets VALUES (?,?,?)", (title, category, text))

    def save_shortcut(self, title, kind, target):
        title = name(title)
        if title in BUILTINS:
            raise ValueError("This name is reserved for a built-in application.")
        if kind == "application":
            target = str(executable(target))
        elif kind == "website":
            target = website_url(target.strip())
        else:
            raise ValueError("Unknown shortcut type.")
        self.db.execute("INSERT OR REPLACE INTO shortcuts VALUES (?,?,?)", (title, kind, target))

    def save_workflow(self, title, commands):
        title = name(title)
        steps = validate_workflow(commands)
        self.db.execute("INSERT OR REPLACE INTO workflows VALUES (?,?)", (title, json.dumps(steps)))

    def delete(self, table, title):
        if table not in {"snippets", "shortcuts", "workflows"}:
            raise ValueError("Unknown resource.")
        self.db.execute("DELETE FROM " + table + " WHERE name=?", (title,))


def validate_workflow(commands):
    if not isinstance(commands, list) or not 1 <= len(commands) <= 30:
        raise ValueError("Workflows need 1–30 steps.")
    for command in commands:
        request = parse(command)
        if (
            request.action not in REGISTRY
            or request.action not in {"open", "folder", "copy", "downloads", "documents", "desktop",
                                      "document", "system_information", "pc_health", "settings", "radio"}
            or bool(request.argument) != bool(REGISTRY[request.action].argument)
        ):
            raise ValueError("Workflow steps must be supported bounded commands with valid arguments. Nested workflows and arbitrary scripts are not supported.")
    return commands
