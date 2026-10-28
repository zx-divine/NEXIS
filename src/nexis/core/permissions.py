from nexis.core.results import Risk
from dataclasses import dataclass, replace


@dataclass(frozen=True)
class AuthorizationDecision:
    requirement: str
    capability: str
    os_privilege: str
    reason: str


# Only validated, bounded wrappers/operations qualify. Their children retain fresh checks.
BOUNDED_REVERSIBLE = frozenset({"run", "workflow_run", "volume_set", "mute_set",
                               "radio_set", "browser_open_tabs"})


def decision(preview, confirm_low=False):
    if preview.risk >= Risk.CRITICAL:
        requirement = "blocked"
    elif preview.risk == Risk.LOW:
        requirement = "approval" if confirm_low else "automatic"
    elif preview.risk == Risk.MEDIUM and preview.action in BOUNDED_REVERSIBLE:
        requirement = "automatic"
    else:
        requirement = "approval"
    return AuthorizationDecision(requirement, preview.permission,
                                 "Windows permissions still apply; NEXIS never elevates automatically.",
                                 preview.reason)


class Permissions:
    def __init__(self, confirm=None, confirm_low=False):
        self.confirm = confirm or (lambda preview: False)
        self.confirm_low = confirm_low

    def authorise(self, preview):
        policy = decision(preview, self.confirm_low)
        if policy.requirement == "blocked":
            return False
        if policy.requirement == "approval":
            if preview.risk == Risk.LOW and self.confirm_low:
                preview = replace(preview, reason="You enabled 'Also confirm low-risk actions' in Settings. This validated operation normally runs automatically.")
            return bool(self.confirm(preview))
        return True
