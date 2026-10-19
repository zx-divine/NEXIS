# Security policy

NEXIS operates as the current Windows user. It does not request elevation,
accept shell programs, include telemetry or provide automatic updates.

## Trust boundaries

- Commands are parsed into registered actions, with target validation and a central authorisation step.
- Sensitive actions are denied if a confirmation provider is absent or declines.
- Custom executables are a user trust decision, not sandboxed content. A known-interpreter filename denylist cannot detect renamed interpreters or hostile programs.
- Workflows are JSON lists of registered open/folder/copy commands; each step is validated at execution. Nested workflows and scripting are rejected.
- Search roots require explicit approval. Searches skip symlinks, junctions and other reparse entries, and check resolved containment.
- Same-user malware and concurrent filesystem substitutions are outside the security boundary. Do not use NEXIS to search attacker-controlled directories.
- SQLite statements bind user data as parameters. Internal table names are fixed or explicitly checked.
- Personal data is plaintext under the user's application-data directory, protected by inherited Windows ACLs, not application encryption.
- Logs contain fixed messages and exception classes. Exported diagnostics omit paths, payloads and logs.

## Reporting a problem

No remote security contact or public repository has been configured. Report an issue privately to the project owner with reproduction steps and sanitised diagnostic metadata. Do not include credentials, snippets or personal exports. Do not post sensitive details publicly before coordination.

## Release requirements

Review docs/SECURITY_REVIEW.md. A source-code review and automated tests are not a penetration test. Dependency advisory scanning, Authenticode signing and clean-machine verification must be completed before a public release. There is no automatic update channel.

## v1.1 interaction and audio boundary

Manual input, deterministic Chat and reviewed voice transcripts share CommandWorker and
the original core registry/permissions. Recognition does not auto-execute. The microphone
is not opened by navigation, startup or background polling. Only explicit activation
starts the optional local worker, with Stop, a 30-second capture cap and cancellation
on navigation/minimize/shutdown. Local model loading may take time to stop but is
checked for cancellation before capture. No audio files, transcript logs, model downloads
or generative providers are enabled. Chat remains session-only. Models and any optional
voice dependencies must come from trusted sources and need separate advisory review.
