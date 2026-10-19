from dataclasses import dataclass
from nexis.core.results import Risk


@dataclass(frozen=True)
class Command:
    identifier: str
    description: str
    argument: str
    risk: Risk
    handler: str
    validator: str = "Engine.prepare"
    permission: str = "Current user, approved targets only"
    confirmation: str = "Required for medium/high risk; optional for low risk"


REGISTRY = {
    c.identifier: c
    for c in [
        Command(
            "open",
            "Launch an approved application or HTTPS website",
            "shortcut name",
            Risk.LOW,
            "open",
        ),
        Command(
            "folder",
            "Open an approved folder in Explorer",
            "absolute approved path",
            Risk.LOW,
            "folder",
        ),
        Command(
            "find", "Search approved folders by partial filename", "filename", Risk.LOW, "find"
        ),
        Command("copy", "Copy a saved snippet", "snippet name", Risk.LOW, "copy"),
        Command("run", "Preview and run a workflow", "workflow name", Risk.MEDIUM, "run"),
        Command("help", "Show command reference", "", Risk.LOW, "help"),
        Command("downloads", "Open your Windows Downloads folder", "", Risk.LOW, "downloads"),
        Command("history", "Show recent command history", "", Risk.LOW, "history"),
        Command("clear_history", "Delete command history", "", Risk.HIGH, "clear_history"),
    ]
}
