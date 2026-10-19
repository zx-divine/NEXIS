from nexis.core.results import Request


def parse(text: str) -> Request:
    if not isinstance(text, str) or not text.strip() or len(text) > 1000:
        raise ValueError("Enter a command of 1–1000 characters. Try help.")
    text = text.strip()
    if any(ord(c) < 32 for c in text):
        raise ValueError("Control characters are not allowed.")
    if text.lower() == "clear history":
        return Request("clear_history")
    action, _, argument = text.partition(" ")
    return Request(action.lower(), argument.strip())
