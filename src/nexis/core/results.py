from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any


class Risk(IntEnum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4
    PROTECTED = CRITICAL  # Historical name; new sensitive page navigation uses HIGH.


@dataclass(frozen=True)
class Request:
    action: str
    argument: str = ""


@dataclass(frozen=True)
class Preview:
    action: str
    target: str
    effect: str
    risk: Risk
    permission: str = "Current Windows user; no elevation"
    reason: str = "This operation can affect private data or make a meaningful change."
    reversibility: str = "Depends on the affected resource; review before approving."


@dataclass
class Result:
    ok: bool
    message: str
    data: dict[str, Any] = field(default_factory=dict)
