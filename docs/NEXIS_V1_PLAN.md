# NEXIS V1 implementation and acceptance plan

Inspection: 27 October 2026. Source baseline: `b465088` on `codex/project-ascension`.
Public target: NEXIS V1 / 1.0.0. Existing engineering version 1.3.7 is retained
until the Windows upgrade/version strategy is validated. Status: **NOT READY**.

Current continuation: [foundation report](NEXIS_V1_M1_REPORT.md) and
[partial Milestone 2 report](NEXIS_V1_M2_REPORT.md). The owner selected a proprietary
All Rights Reserved license; [the EULA draft](NEXIS_V1_EULA_DRAFT.md) is prepared for
review. Cursor overrides were removed at the owner's direction. The inventory
below records the initial inspection; the milestone reports identify implemented
changes and exact acceptance limits without promoting unimplemented features.

## Preservation and backup findings

The development checkout and removable backup storage are physically separate.
Machine-specific paths and the backup inventory remain in private local records.
The inspected migration report does not authorize deleting the originals. Its
integrity and representative restore checks are historical evidence, not a fresh
full restore. Backup separation and report status were inspected read-only.
No archive was written, moved, deleted, extracted, or declared fully verified.
All originals, private data, approved artwork and previous distributions are kept.

No AGENTS.md was found in the checkout or its inspected ancestor directories.
Initial Git status was clean. No push, publication or installation is part of
foundation work. Existing distributions are not evidence for changed source.

## Existing feature inventory

These are inspection statuses. "Implemented but partially verified" means source
exists, but the entire requested capability has NOT passed V1 acceptance.

| # | Requested capability | Inspection status | Existing implementation / remaining work |
|---|---|---|---|
| 1 | Hey NEXIS wake word | Not implemented | Explicit local Vosk capture exists; trained detector, standby lifecycle and false-positive qualification absent. |
| 2 | Natural voice | Implemented but partially verified | Vosk/VAD, Windows SAPI, conversational turns, follow-up mode and explicit interruption; physical audio and automatic barge-in unqualified. |
| 3 | Chat / command launcher | Incomplete | Streaming, copy, retry, session context and Ctrl+K; persistent searchable conversations and global configurable Ctrl+Space absent. |
| 4 | Long-term memory | Implemented but partially verified | Explicit notes, edit/delete/export, opt-out; automatic personalization and approved context selection incomplete. |
| 5 | Context awareness | Incomplete | Visible-window discovery/Windows tools; task context and approved document retrieval need integration. No inference of file contents from titles. |
| 6 | System control | Incomplete | Apps, URLs, windows, volume, settings navigation and native radio bridge; brightness/power/elevation coverage incomplete. |
| 7 | Files | Implemented but partially verified | Approved-root search, metadata, copy/move/rename, Recycle Bin with review; broad document summaries absent. |
| 8 | Screen understanding | Implemented but partially verified | Explicit preview, permission, destination consent, compatible/Gemini vision; real vision model qualification required. |
| 9 | Calendar / reminders / alarms | Not implemented | Durable local scheduler and calendar adapter absent. |
| 10 | Email / messaging | Not implemented | No authenticated mailbox/message adapters or outgoing review pipeline. |
| 11 | Web search | Incomplete | Browser search opening only; no source-returning search provider, citations or freshness pipeline. |
| 12 | Smart home | Not implemented | No paired Home Assistant adapter. |
| 13 | Automation | Incomplete | Validated bounded workflows, draft editor, dry-run, pause/cancel and step logs; scheduling and briefing actions absent. |
| 14 | Code assistant | Incomplete | Provider can explain/generate text; project inspection and isolated explicitly approved execution absent. Arbitrary shell is denied. |
| 15 | Notifications digest | Not implemented | Live weather/news/calendar/notification sources and configurable digest absent. |
| 16 | Multilingual | Incomplete | Provider text may support languages; default recognizer is English. Hindi/Hinglish model provisioning and qualification absent. |
| 17 | Documents | Incomplete | Bounded UTF-8 txt/md index; PDF/DOCX read/write/search absent. |
| 18 | Media | Incomplete | Volume controls; playback transport/browser/compatible player coverage incomplete. |
| 19 | Focus | Not implemented | No durable session tracking, break timers or restrictions. |
| 20 | HUD | Implemented but partially verified | Cached QPainter reactor, measured CPU/RAM, real operation states, six themes, motion controls; welcome structure and missing states need work. |
| 21 | Privacy | Implemented but partially verified | Hard mute, capture consent, local memory, DPAPI credentials, export/deletion; full data inventory and new feature controls required. |
| 22 | Plugins / skills | Not implemented | Typed internal tool registry exists; external plugin manifests, trust/versioning and isolation absent. |
| 23 | Cross-device sync | Not implemented | Requires separately implemented companion/service, authenticated pairing, encryption, conflicts and revocation. |
| 24 | Smart permissions | Implemented but partially verified | Execution-layer category grants, path validation, risk review, cancellation and revocation; new tools require equivalent checks. |
| 25 | Offline | Incomplete | Local manual actions, files, SAPI and available Vosk work; no explicit offline home, reminders or functional local AI onboarding. |
| + | Dictation | Not implemented | Requires selected-target UI Automation checks, password exclusion, foreground revalidation and immediate stop. |
| + | Clusters | Not implemented | Sequential command workflows exist; specialized task orchestration/results/boundaries absent. |
| + | NEXIS Doctor | Implemented but partially verified | Explicit categorized local tests and redacted export; extend for new subsystems and distinguish hardware/live service tests. |
| + | Background operation | Implemented but partially verified | Optional tray/companion, Talk, mute, wake, settings and exit; actual background/lock/suspend/hardware qualification pending. |

## Technical architecture assessment

The existing native Python/PySide6 architecture is suitable for this hardware
target and already freezes Python and resources with PyInstaller/Inno Setup.
Do not replace it with a web runtime or discard tested command implementations.

The execution path is UI -> structured parser/tool schema -> target validation ->
revocable capability/risk authorization -> platform adapter -> typed result.
Keep that boundary for every new command and cluster step. Provider text and
screen/document data never grant permissions. Existing SQLite schema is version 4,
with bound SQL values, integrity checking, serialized access and additive defaults.
Encrypted provider profiles use current-user Windows DPAPI. Existing Qt workers
keep capture, provider IO, file scanning and diagnostics off the GUI thread.

MainWindow currently combines lifecycle, navigation and orchestration and is too
large. Extract new welcome/onboarding/profile/session/scheduler/integration modules
without breaking its existing signal contracts. Existing theme and reactor modules
can be extended. Settings currently has overlapping categories, and onboarding
does not ask a name, show theme previews or actually test spoken input. The native
window title includes development branding. Chat messages are intentionally only
in memory. The docs contain historical architecture statements that predate current
code; inspect implementation and fresh tests before relying on them.

Target module boundaries: desktop shell and modes; onboarding/profile; settings;
themes/reactor; voice and wake lifecycle; provider manager; conversations; memory;
context; Windows adapters; policy; capture/vision; files/documents; durable scheduler;
automation/cluster orchestration; authenticated integrations; plugin host; storage;
redacted logging; diagnostics; updates; isolated release tooling.

## Proposed UI

Use the approved logo unchanged beside NEXIS and the normal Windows frame/title.
A slim persistent header contains Home, Voice, Chat, Manual, mute and the Settings
gear. The welcome page has the personalized greeting, central idle reactor and
exactly three primary mode choices. Secondary tools belong in a deliberate tool
navigation control, not unrelated buttons across the welcome screen. The existing
telemetry HUD becomes the Manual workspace. Mode navigation retains the same chat,
voice transcript and command page instances, and stops microphone capture when
leaving Voice.

Settings sections: General, AI Providers, Voice, Appearance, Permissions, Memory
and Privacy, Integrations, Advanced. Existing controls are reused. Unsupported
integrations have explicit status text and no success toggles. Onboarding gathers
name, capability choices, screen consent, an explicit local microphone phrase test,
working Windows speech, provider configuration and live appearance previews for
welcome/orb/chat/voice. Its gear remains available on every page. Preferences can
be changed after completion without repeating first-run setup.

## Controlled implementation sequence

1. Foundation: preserve baseline; record backup limitations; add validated local
   profile/default mode, personalized welcome, persistent switcher, exact title,
   reorganized settings and onboarding/theme previews; extend actual reactor states.
   Run regression and inspect real rendered widgets at small/large sizes and DPI.
2. AI/voice: qualify existing streaming/timeout/cancel; add explicit Ollama support,
   persistent conversations, conflict-aware global launcher, local wake lifecycle
   and safe target-bound dictation. Test microphone failure/mute/device changes.
3. Desktop intelligence: extend typed Windows/file/context tools, approved memory
   context, screenshot routing and Doctor. Test path escape, destructive review,
   revocation, cancel races, unavailable hardware and privileged-operation handoff.
4. Productivity: durable reminders/alarms, calendar/email adapters and outgoing
   confirmation, citation-returning search, documents, restricted code tools,
   media/focus/digests, scheduled workflows and real cluster task state/results.
5. Ecosystem: versioned permission manifests, trusted plugin installation/isolated
   host, paired Home Assistant; separate sync server/companion and pairing protocol;
   extend privacy/language/offline controls and tests before claiming capability.
6. Release: resolve licence and runtime obligations, dependency/secret audits,
   real audio/live service tests, reference-hardware profiling, Windows 10/11
   fresh-install/upgrade/uninstall/recovery and portable tests. Only qualified
   artifacts go into `Release Nexis`. No dummy executables, logs or release claims.

Each milestone ends in a separate report with exact changes, test commands/results,
evidence paths, remaining issues and next work. Fixture results never certify
hardware, external accounts or clean operating systems.

## Dependencies and external requirements

Current runtime: Python 3.11-3.13 (bundled for end users), PySide6 Essentials,
Vosk, sounddevice/PortAudio, WebRTC VAD, pywin32, google-genai, Send2Trash,
websocket-client, certifi and transitive SDK packages. Existing pinned English
Vosk model is about 41.2 MB; Windows supplies SAPI voices and device drivers.
Build: PyInstaller, Inno Setup, patched setuptools, pytest/pytest-qt, Ruff, Pillow.

OpenAI-compatible/OpenRouter/OmniRoute/Gemini require the user's authorized endpoint,
account, model and credentials. Ollama requires an installed reachable server and
chosen downloaded model. Search/weather/news need configured services or supported
public data APIs. Email/calendar require registered OAuth clients and user consent;
messaging requires a supported platform API. IoT requires paired hardware/Home
Assistant and a protected token. Sync requires companion/service implementation,
TLS and deployment, and is not delivered merely by an architecture document.
Wake detection may need trained redistributable assets; multilingual recognition
needs language resources. Brightness depends on monitor/driver APIs. Distribution
requires the owner-selected NEXIS licence, complete dependency notices/source offer
where applicable, and optional code-signing credentials. Credentials are never
hardcoded, printed or copied from private profiles into builds.

## Performance and security risks

Keep heavy models lazy and one-at-a-time; bounded queues, deadlines/cancellation,
bounded scans and retained history; stop hidden/minimized rendering and avoid GPU
blur. Measure startup, idle/active CPU/RAM, wake cost, capture/TTS latency and
long-session behavior on the specified i3/8 GB/HD 520 machine. This host does not
automatically certify that hardware or Windows 10/11. Per-monitor DPI, keyboard and
screen-reader behavior require actual qualification beyond offscreen rendering.

Highest risks: prompt injection through remote/file/screen data; path/reparse races;
wrong-window dictation; plugin/script execution; secrets in logs or packages;
scheduled actions after revocation; duplicate reminders after resume; OAuth token
storage; sync replay/conflicts/revocation; GUI worker cancellation/shutdown races.
Enforce policy at execution, use typed schemas/target revalidation, fresh outgoing
and destructive review, DPAPI/TLS, no privileged whole-app session, isolated plugin
processes and clean-profile staging. No Windows security bypass is permitted.

## Milestone 1 acceptance criteria

- Native window title is exactly NEXIS; approved logo/icon hashes preserved.
- Fresh onboarding asks a validated preferred name, explains permissions/UAC,
  offers screen control, explicit microphone phrase test and Windows TTS test,
  six theme previews and persistent Settings access. Completion persists; no audio
  or network work starts merely from opening setup.
- Normal launch shows the personalized three-mode welcome unless the user selects
  another default. Voice, Chat and Manual switch without restarting or clearing
  conversation/transcripts. Leaving Voice stops capture.
- Dedicated eight-section Settings hub edits existing persistent preferences,
  identity and default mode; unsupported capabilities show their true status.
- Orb states include real idle/listening/thinking/speaking/executing/permission/
  muted/offline/error signals; previews are visibly identified as previews.
- Six themes render actual welcome, orb, chat and voice previews; custom contrast
  validation, reduced motion and hidden-page timer suspension remain functional.
- Appropriate regression tests pass using isolated new data; real widget renders
  are inspected at 820x600 and 1366x768 and multiple scale factors. Any remaining
  visual/hardware/accessibility limitation is explicitly reported.

## Initial test observation

The unmodified full suite first produced 282 passes and 273 setup errors because
Windows denied the shared `%TEMP%\pytest-of-kingb` directory. This is not a passing
baseline or a product defect diagnosis. Rerun uses a new project-local --basetemp
without deleting or changing the existing shared folder. Results belong in the
milestone report after completion.
