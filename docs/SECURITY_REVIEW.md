# Scoped security review — 2026-10-15

This is a source review with safe local automated tests, not a penetration test.
The labels below apply to the reviewed execution paths, not every possible host condition.

| Area | Classification | Evidence or remaining limit |
| --- | --- | --- |
| Arbitrary command execution | Verified secure within command interface | Unknown verbs rejected; no eval/exec or user shell strings |
| Command injection | Verified secure within registered actions | Hostile command tests, name validation and argument arrays |
| Subprocess calls | Verified secure within reviewed calls | Explicit arrays and shell=False; built-ins use Windows system paths |
| Path traversal | Verified secure for tested stable paths | Resolved containment checks and rejected path-shaped search queries |
| Junction/symlink escapes | Partially secure | Search skips all reparse entries and resolves paths; real symlink test may skip without privilege; concurrent substitutions remain outside boundary |
| URL schemes | Verified secure within shortcut interface | HTTPS-only, no credentials, scheme rejection tests; browser is a separate application |
| Executable trust | Partially secure | Absolute local .exe, known host denylist, trust preview and launch approval; renamed interpreters and malicious binaries cannot be identified |
| Configuration storage | Partially secure | Per-user SQLite, schema version and type checks; plaintext, no encryption |
| SQL injection | Verified secure within repository inputs | Parameter binding; internal table identifiers fixed/allowlisted; SQL payload test |
| Sensitive logging | Verified secure within reviewed events | Fixed messages and exception types; no input, paths or snippet payloads; caplog test |
| File permissions | Unable to verify fully | Inherits Windows per-user directory ACLs; no custom ACL hardening or account isolation audit |
| Dependency vulnerabilities | Partially secure | Official Qt advisory review led to Qt 6.12 minimum; no full transitive advisory/SBOM scan |
| Temporary files | Verified secure within supplied checks | Standard tempfile directories; no application-generated temporary scripts |
| Untrusted workflows | Verified secure within registered engine | JSON only, bounded steps, narrow verb allowlist, validation and per-step authorisation |
| Privilege escalation | Partially secure | No elevation requests/admin manifest; approved apps retain ordinary user privileges; no OS-wide escalation testing |
| Updates | Verified secure for implemented scope | No updater or download-and-execute mechanism |
| Accidental network activity | Partially secure | No application HTTP clients or telemetry; websites invoke browser deliberately; packet capture not performed |
| Deserialisation | Verified secure within reviewed inputs | JSON only, structural and per-step validation; no pickle |
| Packaging | Partially secure | One-folder build and frozen smoke passed, explicit theme, no UPX/admin, WebEngine absent; signing and clean-account verification pending |
| Secrets in source/Git | Verified secure for authored source | No credentials configured or embedded; no Git repository, commits or remote operations |

## Findings addressed

- Added execution-time confirmation for custom applications and repeated workflow step validation.
- Added core management permission checks for startup registration, folder approval, full export and full deletion. Core methods deny without an approval provider.
- Prevented exports from overwriting the active database directory.
- Added confirmation when an editor would overwrite a different existing saved item.
- Fixed a verified packaging DLL collision by excluding the development runtime ICU libraries, allowing Qt to use the Windows ICU API. The rebuilt frozen executable passed startup checks.
- Removed sensitive arguments and handler messages from history; exception logs record types only.
- Enabled SQLite secure_delete before row deletion. External backups/exports and forensic SSD erasure are outside scope.
- Upgraded the Qt minimum from 6.10 to 6.12 after checking current upstream advisories. Only PySide6-Essentials is needed by the application; Chromium/WebEngine and QML are excluded from the release.

[Qt's security advisory register](https://wiki.qt.io/List_of_known_vulnerabilities_in_Qt_products)
lists fixes relevant to the upgrade. [PySide6-Essentials](https://pypi.org/project/PySide6-Essentials/)
provides the PySide6 QtCore/QtGui/QtWidgets modules without requiring a Chromium runtime.

## Remaining release gates

Review full dependency advisories and redistribution licences, sign a release if possible,
exercise a clean no-Python Windows account, verify native accessibility/DPI, inspect ACLs,
and confirm idle network behavior with an OS network monitor. None is implied by passing unit tests.
