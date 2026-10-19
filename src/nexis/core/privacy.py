"""Avoid retaining or forwarding protected credential values entered into conversation."""

import re

PATTERNS = (
    re.compile(r"(?i)\b((?:pin|passcode)(?:\s+code)?\s*(?:(?:is|to|=|:)\s*)?)[0-9]{4,12}\b"),
    re.compile(r"(?i)\b((?:password|recovery\s+code)\s*(?:is|to|=|:)\s*)[^\s,;]{4,200}"),
)


def sanitize_request(text):
    for pattern in PATTERNS:
        text = pattern.sub(
            lambda match: match.group(1) + "[credential redacted; enter it only in Windows]", text
        )
    return re.sub(r"\bsk-[A-Za-z0-9_-]{12,}\b", "[API key redacted; use AI Providers]", text)
