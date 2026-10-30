# Milestone 2 — implementation checkpoint

27 October 2026. **Incomplete. Full-feature NEXIS V1: NOT READY.**
This is an honest checkpoint, not completion of Core AI and Voice or permission
to publish. The original feature inventory in NEXIS_V1_PLAN.md remains the baseline;
the additions and current limits below supersede the relevant baseline entries.

## Implemented additions

### Explicit Ollama provider configuration

Ollama is a selectable compatible adapter at `http://127.0.0.1:11434/v1` with
explicit unauthenticated local-server defaults, model refresh/manual model choice,
the existing inference test, timeout and streaming controls. Existing encrypted
profiles remain readable. Changing a provider clears visible credential fields.
No server/model is silently installed, started, downloaded or substituted.

Source-returning model discovery and chat were tested against a real loopback HTTP
fixture service. This verifies actual HTTP routing and UTF-8 responses, not an
installed Ollama model. An Ollama server can route certain models to cloud
services; loopback alone is not evidence of offline inference. A real local
server/model and offline-disconnected inference qualification are still required.

### Configurable Windows global command launcher

The launcher uses RegisterHotKey and Qt native-event dispatch, not a keyboard hook
or input injection. Default: Ctrl+Space. Alternatives: Ctrl+Alt+Space,
Ctrl+Shift+Space and Ctrl+Alt+K. General Settings provides enable/disable and status.
Windows registration failure reports a conflict/unavailability; a failed rebind
retains the previous working shortcut and discloses it. Ctrl+K remains available
inside NEXIS. Disabling/shutdown drops queued activations and unregisters the key.
Activation brings up the local command UI; it never records or executes a command.

A native Windows probe registered Ctrl+Alt+K, observed competing-thread registration
failure, posted a test WM_HOTKEY to its own thread, observed exactly one native Qt
callback, and unregistered successfully. No physical keypress was injected or
certified. Registration detects conflicts reported by Windows; it cannot inventory
every application-specific shortcut or input-method behavior.

### Explicit persistent, searchable conversations

Chat stays in memory until Save conversation is chosen and a title is reviewed.
Saved chats can be searched by title/content, previewed, explicitly opened as the
current conversation, updated by saving again, exported with personal data and
deleted with fresh execution-layer authorization. New conversation preserves saved
chats and clears the current draft/context. Opening a saved chat alone makes no
network request. Active work must finish/cancel before switching saved contexts.

Storage is private plaintext in the current per-user database. The UI discloses
this. Obvious credentials are rejected; this is not a complete sensitive-data
detector. Bounds: 100 saved chats, 200 completed messages/chat, 64,000 total text
characters/chat. SQL values are bound. Saved messages permit user/assistant roles
only; stored content cannot become a system instruction or tool permission.
Saved-chat deletion requires fresh confirmation in the storage execution layer.
External exports/backups are not erased by local deletion.

Schema 5 adds a table/index without replacing existing settings/resources/memories.
Reset includes saved chats, and personal-data export now includes them. Older
NEXIS versions that reject schemas newer than 4 cannot open the upgraded database;
do not attempt to downgrade a real profile. All development checks use isolated
profiles. No owner database was opened or migrated by these tests.

## Verification evidence

- Initial focused launcher/provider/foundation checks: **29 passed**, 57.30 seconds.
- Saved-chat, migration, management, provider/UI checks: **56 passed**, 27.08 seconds.
- Follow-up UI/privacy/cursor/launcher checks: **19 passed**, 41.01 seconds.
- First broad M2 run: **591 passed, 1 skipped, 3 failed**, 318.41 seconds. All three
  failures were retained assertions for schema 4; the migration now intentionally
  produces schema 5. Their persistence/resource assertions remain in place.
- A subsequent collection attempt caught an indentation mistake in a changed
  migration test; it was corrected. Ruff then passed across src/tests/new scripts.
- Fresh full-suite result: **594 passed, 1 skipped; 322.19 seconds** using
  `scripts/dev.py test -q --basetemp=.verification-v1-m2-qualified --tb=short`.
  The incomplete milestone is regression-qualified within the documented test
  scope; the missing features and physical/live acceptance gates remain open.
- Native hotkey probe: registration, conflict, own-thread dispatch and cleanup
  checks passed. Physical keyboard activation and IME conflicts remain unverified.
- Native frame probe: actual Win32 title NEXIS, standard frame/control style,
  icon handle, maximize, minimize and restore all passed. No console/installer/
  taskbar-grouping claim is inferred from a source-window probe.
- **47 actual native Qt renders** captured welcome/chat/voice/manual/settings/saved
  chats at requested small/large sizes, onboarding pages, six themes and all four
  actual appearance preview tabs in each theme. Captures record pixel dimensions
  and device-pixel ratio; Windows can constrain requested sizes to its display.
- Original approved logo bytes unchanged. No cursor override, cursor resource,
  system-cursor setting or mouse movement was introduced by these capabilities.

Private evidence directories/files:

```text
.verification-v1-m2-first/
.verification-v1-m2-third/
.verification-v1-m2-privacy-final/
.verification-v1-m2-regression.txt
.verification-v1-m2-final.txt
.verification-v1-m2-qualified.txt
.verification-v1-m2-native-launcher/native-launcher.json
.verification-v1-m2-native-renders/render-results.json
```

The initial saved-chat test collection filename collision was resolved by giving
the UI test a distinct basename. Old logs/results remain preserved. Fixture output
never counts as actual speech recognition, audible TTS or external account access.

## Standalone native performance on the reference laptop

Hardware discovery: Intel Core i3-6100U (2 cores / 4 logical processors), Windows
visible RAM 8,274,336 KB, Intel HD Graphics 520, Windows 10 Home Single Language
build 19045. This matches the requested reference class. No competing regression
process ran during this native measurement; no AI/STT model was loaded.

Construction through first event, excluding imports and QApplication/font setup:
**2.791 seconds**. This is not packaged cold-start time.

| State | One-core process CPU | Working set | Paint events / ~3 seconds | Mean paint wall time |
|---|---:|---:|---:|---:|
| Idle | 15.62% | 126.20 MB | 22 | 13.08 ms |
| Active render stimulus | 65.41% | 126.19 MB | 91 | 14.37 ms |
| Reduced motion | 0.00% | 126.19 MB | 0 | 0 ms |
| Minimized | 0.00% | 126.26 MB | 0 | 0 ms |

CPU is measured in one-core units, not whole-machine percentage. Both reactor and
system-sampling timers stopped when minimized. Active achieved about 30 FPS.
These are UI-only measurements, not simultaneous voice/provider/model performance,
long-running reliability, or certification of the complete performance brief.
The active state was an explicit rendering stimulus; no command completion was
fabricated. Windows 11 and fresh packaged environments remain untested.

## Outstanding Milestone 2 work

- **Wake word: not implemented.** Need a functional efficient local detector,
  licensed/checksummed Hey NEXIS assets, opt-in lifecycle, false-positive handling,
  mute/revocation/device-loss tests and measured standby cost. Ordinary Vosk
  transcription or an attractive standby orb is not a trained detector.
- **Dictation: not implemented.** First supported target should have a verifiable
  editing API. Require explicit target selection, fresh process/window/focused
  control validation at every insertion, password/read-only exclusion, a dedicated
  revocable grant, local-only transcript handling, stop phrase, focus-loss stop,
  hard mute and cancellation tests. Do not inject into terminals, password fields
  or a window selected only from its title. A clipboard action is not dictation.
- **Automatic barge-in: incomplete.** Existing explicit interruption/cancellation
  remains; simultaneous listening/echo handling must be implemented and physically
  qualified before claiming automatic interruption.
- Existing streaming chat, local STT and Windows SAPI need real owner-selected
  provider/model, microphone, speaker, unplug/reconnect and three-mode voice cycles.
  Unperformed physical/live tests remain unverified.
- Saved-chat automatic retention policies, larger archives, optional automatic
  history and per-message editing are not implemented. Explicit snapshot saving,
  bounded search, reopen, deletion and export are the supported scope here.
- The earlier model-activation access-denial still needs real provisioning/recovery
  qualification. No continuous wake processing or additional heavy model starts
  on launch. Advanced language/notification/integration settings remain future work.

## Release status and next work

Finish the missing M2 capabilities and qualify physical voice/local inference
before claiming this milestone complete. Then follow the Desktop Intelligence,
Productivity/Clusters, Ecosystem and Release milestones in NEXIS_V1_PLAN.md.
Calendar/reminders, email/messaging, citation-returning search, documents, focus,
clusters, external plugins, IoT and cross-device sync have not been implemented by
this checkpoint. Their baseline statuses have not been silently promoted.

The proprietary EULA remains a draft for review; dependency redistribution,
contracting-party details, clean install/upgrade/uninstall, secret/dependency audit,
full workload performance and Windows 11 qualification remain release gates.
The USB archives and original distributions remain untouched. No GitHub push,
publication or new installer/portable binary occurred. `Release Nexis` artifacts
must be generated only after the full required implementation and verification;
there are no placeholder executables, release archives or fabricated logs.

Primary implementation references: [Ollama compatibility](https://docs.ollama.com/api/openai-compatibility),
[Windows RegisterHotKey](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-registerhotkey),
[Qt native event filtering](https://doc.qt.io/qtforpython-6/PySide6/QtCore/QAbstractNativeEventFilter.html).
