from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any


class Risk(IntEnum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    PROTECTED = 4


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


@dataclass
class Result:
    ok: bool
    message: str
    data: dict[str, Any] = field(default_factory=dict)
