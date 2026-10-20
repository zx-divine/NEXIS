# NEXIS security and privacy boundaries

NEXIS runs as the current Windows user and does not request elevation. It is not a sandbox against same-user malware. Windows UAC, microphone privacy, SmartScreen and antivirus remain authoritative; no bypass is implemented.

## Commands and authentication

Tool arguments are untrusted and pass fixed schemas, target validation, revocable capability grants, folder containment and risk-based review. Explicit normal installed-app and trusted-site requests may be low risk. Downloads, unfamiliar executable paths, sensitive settings and destructive actions retain review; arbitrary shell execution is unsupported. Protected password/PIN changes only hand off to Windows interfaces: Windows performs identity verification. NEXIS never collects or changes those credentials itself. Review dialogs and queued actions are cancelled when the session is stopped or Hard Mute is applied; already completed external effects are not undone.

## Audio

The microphone is off until an explicit Talk, test or calibration action. Experimental hands-free follow-ups require opt-in and an initial Talk action, remain on the visible Voice Chat page, and stop on cancellation, navigation, hiding, minimizing, timeout or Hard Mute. Wake clears the mute latch but never opens a stream by itself. There is no default ambient wake-word listener. Optional manual interruption stops TTS before another capture; no acoustic echo-cancellation or always-listening barge-in claim is made.

Vosk performs local recognition using the bundled model or a trusted user-selected compatible model. WebRTC VAD informs bounded gain and endpoint timing; it never discards initial PCM. Calibration and audio processing stay local. Core capture audio stays in bounded memory and is not saved or uploaded. Settings previews are not sent to AI. The optional standalone QA utility saves test transcripts/measurements only after its explicit user-driven test flow; inspect those local files before sharing them.

Selected-provider cloud chat and voice-chat transcripts are sent only through the configured provider after the corresponding user action. No automatic provider fallback occurs. Sanitization is a safeguard, not a guarantee that arbitrary user text contains no personal information. Review what you request before transmitting it.

## Storage and networking

Provider credentials are protected with Windows current-user DPAPI. Other SQLite data, command history, preferences and approved resources are plaintext under per-user AppLocalData with inherited Windows permissions. Keep backups private. SQL values are bound parameters; internal SQL identifiers are fixed/validated. Diagnostic exports omit private contents and credentials. Logs use fixed messages and error categories, not raw provider responses or secrets.

Local Memory is opt-in per save/import and is never automatically sent to an AI provider. Memory commands only draft or search; deletion needs review. Obvious secret patterns are rejected, but this is not a complete data-loss-prevention system. Exports are private plaintext files. Optional document indexing separately requires visible consent and stores bounded supported text locally in SQLite; indexed content is untrusted data, never instructions or automatic AI context. Stale and unapproved paths are excluded from searches. Delete controls perform ordinary logical deletion, not forensic secure erasure; backups may retain previous text.

Provider addresses require validated HTTPS except approved loopback HTTP local servers. Redirects are rejected, response sizes and IO timeouts are bounded, and cancellation is checked before executing actions. User-configured gateways remain a trust decision. Tool output, filenames and document contents are untrusted data and cannot grant permissions.

Experimental Screen Awareness needs a separately granted capture capability, a direct capture action, preview and fresh destination confirmation before sending an image. It never captures continuously or writes screenshot files. The owner must hide private/credential content before capturing; no claim of automatic visual secret detection is made. Cancel/discard before sending prevents transmission. Once transmission is approved and starts, bytes already sent cannot be recalled. Vision responses are plain explanation text, isolated from tools, memory and conversation history. Protected/secure desktop capture is not bypassed.

Workflow Studio generates editable drafts only. A draft cannot authorize execution, bypass grants or introduce shell commands. Existing saved routines require manual Run and retain execution-time permission/target checks. Pause takes effect at step boundaries; cancellation does not reverse completed external actions. Cooperative deadlines do not forcibly interrupt an operating-system call already in progress.

## Release qualification

Automated fixtures do not establish hardware recognition, audible output, clean-machine compatibility or penetration-test coverage. Review the current engineering handoff for actual checks and outstanding gates. A source/credential heuristic scan does not prove absence of all vulnerabilities. Dependency advisory review, appropriate owner licensing, code signing and clean Windows/hardware testing remain release considerations. No installer publication or GitHub Release is automatic or authorized by a source push.

Report security issues privately to the owner with sanitized reproduction steps. Never include keys, private databases, recordings, screenshots or chat exports in public issues.
