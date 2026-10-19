"""Revocable categories shared by manual commands, voice and AI tools."""

CATEGORIES = {
    "application_launching": "Application launching",
    "browser_control": "Browser control",
    "window_management": "Window management",
    "clipboard_access": "Clipboard access",
    "approved_folder_access": "Approved-folder access",
    "file_modifications": "File modifications",
    "system_settings": "System settings",
    "terminal_commands": "Terminal commands (not supported; no arbitrary shell execution)",
    "workflow_execution": "Workflow execution",
    "microphone_access": "Microphone access (only after pressing Talk or Record)",
    "network_actions": "Network-dependent actions",
    "sensitive_operations": "Sensitive operations (fresh confirmation; protected steps stay in Windows)",
}
DEFAULT_GRANTS = {key: False for key in CATEGORIES}
DISCLOSURE = """NEXIS is an AI-powered desktop assistant that can interact with applications, browser windows, files, and supported Windows settings on your behalf.

Depending on the permissions you enable, NEXIS may launch programs, automate desktop actions, read approved files, modify selected data, and change supported device settings.

Some actions may affect important information or system configuration.

NEXIS requests additional confirmation before sensitive operations.

You can review and revoke permissions at any time.

NEXIS cannot bypass Windows authentication, administrator approval, or operating-system security protections."""


def require_access(db, category):
    if category not in CATEGORIES:
        raise ValueError("Unknown permission category.")
    if not db.setting("system_access_acknowledged"):
        raise ValueError(
            "Review NEXIS — SYSTEM ACCESS & CONTROL in Settings before using this capability."
        )
    if category == "terminal_commands":
        raise ValueError(
            "Terminal execution is not supported. Model text is never passed to a shell."
        )
    if not db.setting("access_permissions").get(category, False):
        raise ValueError(
            "Permission denied: "
            + CATEGORIES[category]
            + ". Review or enable it in Settings → System access."
        )
