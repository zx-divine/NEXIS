# NEXIS engineering handoff — 20 October 2026

Creator: **ASH**. Target: **10 November 2026**, earlier only if all mandatory gates pass. Existing application/version history is retained. Website work is outside scope.

## Baseline and safeguards

Baseline source/remote: b2a0cac595c48ee3e448660db7c5f4d4d5b458c8. The fresh baseline, architectural inventory and measured CPU/RAM are in LAUNCH_UPGRADE_FINDINGS.md. Do not repeat the full audit without a material architectural change. A local source archive and all original evidence are preserved under ignored .verification-launch-v1. No microphone or speaker was activated by automated checks.

## Inventory with verification boundaries

| Area | Current status | Evidence / unfinished scope |
|---|---|---|
| Entry, HUD, storage, command safety | WORKING in automated tests | Baseline 249 passed; native installer/startup previously verified on current host. Real clean Windows remains NOT TESTED |
| Default offline model packaging | WORKING in prior build | Exact verified English Vosk model included; new VAD runtime inclusion requires a new release build in F |
| Real microphone / audible voice | NOT TESTED | Owner hardware actions required; synthetic PCM/SAPI is not proof |
| Voice Studio and session controls | PARTIALLY WORKING | A component checks passed below; physical device changes and natural speech still pending |
| Multi-provider chat/context/streaming | PARTIALLY WORKING | Existing mocks/SDK transport fixtures pass; live provider availability is not claimed |
| Risk-based launch permissions | WORKING in regression tests | Validated normal installed apps avoid duplicate approvals; sensitive operations remain reviewed |
| Identity engine | WORKING in automated tests | NEXIS / ASH facts resolved locally; validated selected model is identified as configuration, not proof of live availability |
| PC Health | WORKING on current host | Explicit read-only snapshot: CPU/RAM/available physical memory/disk/battery/Windows connection report/uptime/top accessible RAM processes; no temperature backend, no internet reachability claim |
| Smart local memory | WORKING in automated tests | Explicit local saves, categories, search/edit/delete/export/import, additive schema 4; secret detection is best effort, no automatic provider context |
| File Finder | WORKING within documented bounds | Metadata filtering/ranking, approved-root cancellation, opt-in UTF-8 txt/md index (200 documents, 32 KB each); PDF/Office content parsing unsupported |
| Natural-language automation | WORKING in automated tests | Experimental draft-only provider adapter, editable existing commands, no-effect dry-run, explicit save/run, bounded pause/cancel/revocation; live drafting remains unverified |
| Hindi/Hinglish | NOT TESTED | Default model is English. Do not advertise multilingual STT without validated compatible packs/audio |
| Screen Awareness | PARTIALLY WORKING | Explicit grant + opt-in + preview + destination consent; adapters tested with generated pixels/mock transports only. Real capture and live image inference not performed |
| Floating orb / tray | PARTIALLY WORKING | Optional/off by default; explicit Talk opens visible Voice Chat; drag/position/visibility policy tested. Physical multi-monitor/tray/fullscreen behavior pending |
| Update discovery | WORKING within documented bounds | Official release metadata only; real no-release response verified; local SHA-256 comparison, no installer execution. No public release exists |

## Milestone A — Voice Core source checkpoint

- Added WebRTC VAD (webrtcvad-wheels 2.0.14, pinned Windows wheel), conservative per-frame speech gain capped at 4× with peak headroom, dBFS metering, device-bound noise calibration and adjustable speech sensitivity/pause duration. Original input PCM is never discarded by VAD; initial syllables remain available. No claim is made that gain improves signal-to-noise ratio or repairs clipped input.
- Kept unrestricted Vosk decoding. A second short greeting grammar is considered only for exact assistant greetings supported by both decoders; “hi mate” and general Nexus mentions are never replaced. Raw output remains in local in-memory diagnostics. Static/custom models without grammar support retain unrestricted recognition.
- Stop on independent conversational hangover rather than the first Vosk sentence endpoint. One in-process microphone owner, bounded queues and callback abort on cancellation prevent overlapping or continued capture. Model caching remains shared.
- Voice Studio uses the same worker, with explicit microphone tests/calibration, previews that are not sent to AI, clipping feedback, input and SAPI output selection, and restore defaults that preserve Hard Mute.
- Added persistent Hard Mute/sleep, explicit Wake without recording, cancellation of pending tool approvals and old callbacks. Navigation/hiding/minimizing stops diagnostics and voice capture. Explicit manual interruption stops TTS before Talk.
- Experimental hands-free follow-ups are OFF by default. Checking the option alone does nothing; an initial Talk arms it. Follow-ups wait for TTS completion and remain limited to visible Voice Chat. Cancellation/errors/mute/navigation prevent unintended continuation. This is not a background wake-word listener or acoustically verified barge-in.
- Prevented ordinary transcript text from entering persisted measurement metadata; only the short, constrained adapted greeting can be included. Corrected obsolete security/privacy disclosures. No OS protection was changed, and no unrestricted permission was added.

**Actual checks:** complete source suite **278 passed, 1 skipped**, 56.77 seconds; Ruff PASS. The skip requires Windows symlink privilege. New audio unit checks passed; UI control-flow tests use injected backends and are not hardware evidence. Native SAPI-to-file → shared Vosk/conditioning checks: **13 passed, 0 failed**, two Windows voices, normal and 0.1 amplitude scales, brand/negative/control sentences and seeded noise. Generated files were temporary; no speaker playback or microphone recording. No Hindi/Hinglish quality claim.

Evidence is local: milestone-a-tests.txt, milestone-a-result.json, controlled-speech.json, native fixture baseline and dependency install report under .verification-launch-v1. Source publication must be credential-scanned and verified, with SHA recorded in the local continuation report. The 1.3.2 installer remains the previous verified build until F produces a new candidate.

## Dependent implementation plan

### Milestone B — Agent foundation source checkpoint

Milestone A was pushed and verified at **81b5c6f5b2e2247c6826abd085c71dce221aa9c4**. The owner deferred real hardware testing; keep those gates pending and continue independent work.

- Added a small identity module: application NEXIS, creator ASH, desktop-assistance purpose. Whole identity questions are answered locally without requiring credentials, network access or tool permissions. Compound requests remain in the ordinary validated operator path.
- Runtime identification reads the active encrypted profile without changing it. It reports the configured adapter/model honestly; unknown, invalid, excessively long, control-character or credential-bearing model labels are not claimed. No gateway upstream attribution or model availability is invented.
- Operator system instructions separate immutable application facts from provider configuration and untrusted content. This does not grant permissions. The Chat page and header refresh their selected-provider labels after explicit selection, editing or removal; running requests retain their existing provider snapshot.
- Compatible model-list GETs retry at most once after HTTP 429/502/503/504. Retry-After must fit the short cancellation-aware bound; longer waits remain manual. Generation POSTs, partial streams, ambiguous connection failures, authentication failures and configuration failures are never automatically replayed. No provider fallback was added.

**Actual checks:** 33 new targeted tests passed; complete source regression **311 passed, 1 skipped**, 64.47 seconds. Ruff and whitespace checks passed. Tests use disposable encrypted profiles, injected transports and Qt controls; they do not establish live Gemini/OmniRoute inference or physical audio. Milestone B was pushed and verified at **61fa61c7601a4c87790be72303b6eaaa2dfd4967**.

### Milestone C — Local productivity source checkpoint

- PC Health refreshes only on request, outside the GUI thread. It uses read-only Windows counters and bounded process enumeration without elevation, settings changes, process termination or external connectivity probes. A real non-elevated run returned CPU, RAM, physical available memory, data-volume disk space, battery/charging, uptime and ten accessible process memory entries. Connection state is explicitly not proof of internet/provider reachability. Temperature remains unavailable.
- Local Memory supports preferences, favorite-app notes, approved project context, approved memories and manually approved conversation summaries. Explicit Save persists; remember-this commands only create a draft, and forget-this commands only show candidates for confirmed deletion. Spoken memory navigation does not start hidden playback or another conversation turn. Memory is never exposed as an AI mutation tool or automatically inserted into provider requests.
- Memory has Unicode search, editing, individual/delete-all confirmation, private plaintext export and validated transactional import with duplicate suppression/cancellation. Obvious credential patterns are rejected, but detection cannot guarantee arbitrary prose is non-secret. Do not save sensitive data. Existing user records are preserved through additive schema 4. Failed future-version opens now close their database handle.
- File Finder adds date/size filters, local safe metadata and bounded ranking. Natural-language provider search uses validated optional numeric filters. UI searches recheck folder/capability revocation during enumeration. Scans are capped at 50,000 inspected files/30 seconds; results are bounded and incomplete coverage is disclosed.
- Optional text indexing requires a separate visible confirmation, runs in the background, and never executes or transmits contents. It supports UTF-8 txt/md files only, at most 32 KB each and 200 documents from a bounded 5,000-candidate scan. Obvious credential content, binary/oversized files, protected application paths, links and changed/unapproved files are excluded. Cancelled builds preserve the previous cache. Cache deletion preserves originals; ordinary SQLite deletion is not forensic erasure, and private backups may retain copies.

**Actual checks:** initial targeted regression **63 passed, 1 skipped**; final complete source suite **335 passed, 1 skipped**, 110.24 seconds. Ruff, compileall and whitespace checks passed. The privilege-dependent symlink skip remains documented; no skip was counted as a pass. Real read-only health counters were checked without administrator access. Six isolated offscreen Qt layouts rendered at 820×600 and 1366×768; Files/Memory were visually inspected with registered Windows fonts and scrolling. This is not clean-machine or accessibility certification. Evidence remains under ignored .verification-launch-v1. The previous 1.3.2 installer predates A–C; D–F remain incomplete.

### Milestone D — Advanced intelligence source checkpoint

Milestone C was pushed and verified at **429e7c94df9207e4671a116e02fb8709838dac2c**.

- Existing workflows remain the execution engine. The optional/off-by-default Workflow Studio asks the selected provider for a strict draft only, with no tools, private resource catalog or execution. The owner can edit, dry-run through existing target validation, explicitly save and then manually run the routine. Only supported open/folder/copy steps are accepted. Unknown targets fail rather than becoming invented execution paths.
- Added pause/resume at step boundaries, cancellation and grant rechecks between steps/while paused. Manual workflow requests have a cooperative two-minute budget including approval waits; ordinary manual approval waits are capped at three minutes. External Windows calls already submitted cannot be undone or forcibly interrupted. Existing per-step safety checks, failure stopping and private action/status history remain intact.
- Screen Awareness is experimental/off by default and adds a separate default-denied screen-capture capability; old permission profiles do not gain it. A direct Capture preview click captures only the selected screen or NEXIS window. There is no AI capture tool, continuous capture, screenshot file or automatic transmission. Images are bounded to 1,280 pixels per side/4 MB and kept in memory.
- Sending needs a separate preview/destination/provider/model disclosure and explicit confirmation. Preview generations prevent stale consent from applying to a recapture, including identical pixels. Discard/navigation/hide/minimize/Hard Mute cancels queued work and drops the preview. Cancelling before Send prevents transmission; cancellation cannot retract bytes already sent after approval. This limit is explicitly disclosed.
- Dedicated OpenAI-compatible and official Google SDK vision requests are explanation-only: no tools or shared conversation history, no provider/model fallback, no automatic memory or file actions. Unsupported image models return actual provider errors. Natural screen questions only navigate to the preview page; they never trigger capture.
- Voice Studio now states the verified English US default and that Hindi/Hinglish speech packs/quality are not validated. Unicode text input does not establish multilingual recognition quality.

**Actual checks:** first workflow group 26 passed/1 failed (missing-target dry-run surfaced an OS error); corrected to a friendly safe error, then 27 passed. Screen harness initially had two Windows test-ID setup errors and an SDK wire-field assertion failure; those were corrected with bounded parameter IDs and the installed SDK's supported MIME/base64 representation. Corrected combined workflow/screen group: **25 passed**. Final complete source suite: **362 passed, 1 skipped**, 114.84 seconds. Ruff/compile checks passed. Official Google SDK image serialization was exercised over a mock HTTP transport; compatible vision used injected HTTP. Generated test pixels are not real desktop captures or live vision evidence. Four isolated layouts rendered at 820×600/1366×768; the screen page was visually inspected. No microphone, actual screen capture or cloud inference was performed. New A–D source is not yet in the previous 1.3.2 binaries. E–F remain incomplete.

| Milestone | Next work / affected areas | Acceptance and risks |
|---|---|---|
| B — Agent foundation | Small identity module, operator system identity, runtime provider/model UI, bounded safe retry/backoff, permission regression | Identity cannot change permissions; no fabricated model availability; no retry after partial stream or ambiguous network failure |
| C — Local productivity | Read-only Health panel, user-approved local memory, approved-root Finder metadata/index controls, additive SQLite migration | No automatic process termination; no secret memory; imports validated before writes; no filesystem escapes or broad scanning |
| D — Advanced intelligence | Editable workflow drafts/dry-run/pause, honest language-pack state, explicit screen preview/consent and dedicated vision request | No arbitrary LLM shell; no screenshot transmission before consent; cancel blocks sending; content never changes identity/policy |
| E — Desktop experience | Optional orb/tray, official update discovery, measured reactor optimization and accessibility | OFF-by-default experimental features; no visibility-triggered mic; safe official URLs; no auto execution; compare actual CPU/RAM |
| F — Installer and gate | Freeze candidate, audit dependencies/history/secrets, build installer/ZIP, five independent full regression runs and five distinct verification passes | New test state per process; restart five-round sequence after a code failure/fix; clean Windows/real audio cannot be replaced by mocks |

Review, meaningful targeted checks, source-only commit/push and an updated handoff are required after each milestone. Do not proceed past an unresolved code failure. Hardware checks can remain explicit external verification blockers while independent engineering continues.

## Mandatory outstanding verification

### Milestone E — Desktop experience checkpoint

Milestone D was pushed and verified at **3226ca827a08eee3f634830bcd0e49df21844235**.

- Optional floating reactor/tray controls are OFF by default. Showing, dragging or restoring never starts recording. Explicit Talk restores visible Voice Chat and uses its existing gates. Logical positions are clamped to available monitors and react to display removal/scaling. Manual hide stops rendering and the eligibility timer. A lightweight two-second Windows eligibility check hides the orb during reported fullscreen/presentation/locked/quiet/unknown states. Collapse is disabled without a recoverable tray path. Shutdown closes the companion.
- Update discovery uses only the official repository's latest stable-release API with no account/token, bounded data/time, cancellation and strict official URL validation. Optional daily startup checks are OFF by default and require the network capability. Download/page opening requires explicit review and browser/network grants. Local SHA-256 verification compares an explicitly selected file against supplied metadata; this does not independently authenticate a publisher. Installers are never executed.
- Manual actions and AI execution are serialized so a second UI route cannot start overlapping OS actions. Reset now clears new memory/index tables and private UI drafts, disables experimental features and refreshes selected-provider state. Settings export explicitly excludes indexed contents and points to the separate memory export.
- Measured and rejected a bitmap-ring rendering candidate: active paint 21.928 ms and excessive CPU. Retained cached vector paths preserving the reactor's geometry, colors, timing and audio semantics. Same-viewport current-host measurements: active paint **11.703 ms** versus baseline **14.002 ms**; idle **10.661 ms** versus **12.568 ms**. Total active process CPU stayed approximately unchanged (56.23% versus 55.79% of one core), so no total CPU improvement is claimed. Current UI-only working set about 107 MB; first window event 2.913 s versus earlier 1.495 s, under different host load. This is not low-end hardware certification. Reduced/minimized modes performed no reactor paints; minimized sensors stopped. Three isolated before/after images differed by at most 0.123 mean channel levels out of 255; the retained vector rendering was visually inspected.

**Actual checks:** initial experience group 42 passed; privacy/integration review group 47 passed; complete source suite **381 passed, 1 skipped**, 125.96 seconds. Ruff passed. A real unauthenticated official-release request completed with no stable release/assets; downloads stayed disabled. The native Windows notification-eligibility API returned a busy state. Orb policy tests use injected eligibility and simulated geometry; physical tray/multi-monitor/fullscreen testing remains pending. Source A–E is not yet in the old 1.3.2 binaries. F packaging/five final regressions remain outstanding.

Real normal-volume speech, representative “Hi NEXIS,” selected-provider inference, audible output, physical hot-plug, low-end hardware behavior and clean Windows 10 build 19045+/Windows 11 install/uninstall are **NOT VERIFIED**. The owner has been given one Voice Studio test instruction. Existing three standalone and five integrated real conversation cycles remain pending. No owner interaction has been simulated.

At the milestone E checkpoint, final packaging and five regressions were still outstanding. See the completed F engineering checkpoint below; mandatory real-world gates remain pending. No release, installer upload or deployment is authorized.


### Milestone F — 1.3.3 local candidate, 21 October 2026

Milestone E was pushed and verified at **e227a7490fcd2c2bd16286499fbc5ab6ad5df416**. Continued the existing candidate; preserved the previous 1.3.2 distribution and owner data. The final 1.3.3 executable, per-user installer and portable archive have been built and verified locally.

- Corrected the PyInstaller webrtcvad hook to collect maintained webrtcvad-wheels metadata and compiled _webrtcvad. The initial legacy-metadata failure was preserved, then corrected and rebuilt.
- Excluded local memory/screen-navigation requests and local acknowledgements from later cloud conversation history.
- Corrected AI workflow clipboard callback delivery with cancellation/current-grant checks; unavailable delivery fails and accepted requests are not misreported as verified OS effects. Final frozen fixture passes without changing the real clipboard.
- Aligned app/PE/installer version 1.3.3, schema 4 and Windows 10 build 19045+ minimum. Package verification checks all new pages/dependencies, model hashes and workflow fixture.

**Final regression:** five independent serial full-suite processes, fresh UUID temporary state, cache disabled, unchanged source fingerprint **6b64ec65e9d948b2a1ced9c9f9e09e55c327faaa62b692b961b0626587a92678**. Each: **386 passed, 1 skipped**. Process elapsed seconds: 121.56, 81.03, 78.7, 72.3, 77.27. The skip requires Windows symlink privilege. Earlier concurrent-build execution had a three-second paused-worker wait failure (385 passed/1 skipped/1 failed); evidence is retained. It did not recur in these five runs. No test was removed or timeout relaxed. Resource contention is an inference, not an established root cause. Earlier five-run results predating final fixes were not counted.

**Five packaging stages:** frozen startup, native audit, installer compilation, installed smoke and portable smoke all exited 0. Static audit checked **1,004 PE imports** (not Python modules), with no missing required modules/dependencies/private artifacts; this is not exhaustive clean-OS coverage. Isolated offline startup blocked network sockets and observed zero connection attempts. Installed verification confirmed the exact executable, shortcut/AppUserModelID references and unchanged existing database/encrypted provider profiles. Portable ZIP CRC and a fresh extracted native launch passed with Python removed from PATH and bundled model loaded; cleanup completed. This is not a clean Windows machine without Python.

Artifacts: dist/NEXIS/NEXIS.exe (keep _internal adjacent), dist/installer/NEXIS-Desktop-1.3.3.0-Setup.exe (101,502,448 bytes), dist/NEXIS-Desktop-1.3.3-Windows-x64-Portable.zip (130,315,945 bytes). Original 1.3.2 remains preserved. Both executable and installer are unsigned; no SmartScreen bypass.

**Provider/security evidence:** saved selected Gemini constant diagnostic first returned SERVER_ERROR; a later explicit diagnostic retry succeeded. No provider switch or credential change. This establishes one source inference, not live-provider reliability or packaged voice. OmniRoute recovered to HTTP 200 health; no legacy saved OmniRoute inference profile was available, so inference remains NOT VERIFIED. Packaged SDK tests use mocked transport. OSV returned no findings for 53 public package/version pairs; reachable-history heuristic review (7 commits/226 blobs) found none. These are bounded checks, not security certification. Final source is reviewed separately before publication.

**Release verdict: NO-GO; voice NOT FULLY VERIFIED.** Three standalone fresh-microphone and five complete NEXIS voice cycles are still PENDING USER VERIFICATION. Normal-volume human speech, audible speaker output, Hindi/Hinglish, physical device changes, live-provider reliability, physical taskbar/tray/multi-monitor operation, target i3 performance and clean Windows 10/11 install/uninstall remain pending. No owner confirmation has been invented. Local detailed report and hashes are saved in the ignored verification directory and Desktop/NEXIS-Voice-Engine/test-results. No binary publication, GitHub Release or website deployment.
