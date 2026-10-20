"""Draft and dry-run only. Execution remains in the existing validated engine."""

import json

from nexis.core.access import require_access
from nexis.core.identity import identity_system
from nexis.core.privacy import sanitize_request
from nexis.core.provider_manager import generate
from nexis.core.parser import parse
from nexis.core.router import Engine
from nexis.storage.repository import validate_workflow


def parse_draft(text):
    if not isinstance(text, str) or len(text) > 30000:
        raise ValueError("The workflow draft exceeded its text limit.")
    text = text.strip()
    if text.startswith("```json") and text.endswith("```"):
        text = text[7:-3].strip()
    try:
        data = json.loads(text)
    except ValueError:
        raise ValueError("The provider did not return a valid workflow JSON draft. No step was saved or executed.") from None
    if not isinstance(data, dict) or set(data) != {"steps"}:
        raise ValueError("A workflow draft must contain only a steps array.")
    return validate_workflow(data["steps"])


def draft_workflow(db, profile, prompt, cancel):
    require_access(db, "network_actions")
    if not isinstance(prompt, str) or not 1 <= len(prompt.strip()) <= 1000:
        raise ValueError("Describe the routine in 1–1,000 characters.")
    if cancel.is_set():
        raise ValueError("Workflow drafting cancelled.")
    result = generate(profile, [
        {"role": "system", "content": identity_system(profile) + '\nDraft only. No tools or execution. Return JSON exactly {"steps":["open application-or-approved-website-name", "folder absolute-approved-path", "copy saved-snippet-name"]}. Use only these three manual command kinds, 1–30 steps. Do not invent paths, names or unsupported steps; if essential details are missing, return {"steps":[]} so the owner can edit manually. Never use scripts, shell, nested workflows or extra instructions.'},
        {"role": "user", "content": sanitize_request(prompt)},
    ], cancel)
    require_access(db, "network_actions")
    if cancel.is_set():
        raise ValueError("Workflow drafting cancelled.")
    if result["calls"]:
        raise ValueError("The provider returned tool calls instead of a draft. Nothing was executed.")
    return parse_draft(result["text"])


def dry_run(db, text, platform=None):
    commands = validate_workflow([line.strip() for line in text.splitlines() if line.strip()])
    engine = Engine(db, platform)
    previews = []
    for command in commands:
        request = parse(command)
        try:
            preview, _ = engine.prepare(request)
        except OSError:
            raise ValueError("A draft target is missing or inaccessible. Correct the step and use an approved existing target; nothing was executed.") from None
        previews.append({"command": command, "target": preview.target, "risk": preview.risk.name,
                         "effect": preview.effect})
    return previews
