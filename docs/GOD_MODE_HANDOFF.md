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
| PC Health | PARTIALLY WORKING | Existing CPU/RAM/uptime measured; advanced health fields/top processes still pending |
| Smart local memory | MISSING | Existing settings/snippets/history are not a complete user-controlled memory system |
| File Finder | PARTIALLY WORKING | Approved-root filename/extension search exists; metadata filters/index management pending |
| Natural-language automation | PARTIALLY WORKING | Safe stored workflows and AI structured actions exist; editable drafting/dry-run/pause pending |
| Hindi/Hinglish | NOT TESTED | Default model is English. Do not advertise multilingual STT without validated compatible packs/audio |
| Screen Awareness | MISSING | Explicit preview, provider disclosure, transmission consent and cancellation required |
| Floating orb / tray | MISSING | Reuse existing reactor; no microphone activation from visibility |
| Update discovery | MISSING | Official-repository metadata only; no automatic installer execution |

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

**Actual checks:** 33 new targeted tests passed; complete source regression **311 passed, 1 skipped**, 64.47 seconds. Ruff and whitespace checks passed. Tests use disposable encrypted profiles, injected transports and Qt controls; they do not establish live Gemini/OmniRoute inference or physical audio. The previous 1.3.2 installer still predates milestones A and B. Milestones C–F remain incomplete.

| Milestone | Next work / affected areas | Acceptance and risks |
|---|---|---|
| B — Agent foundation | Small identity module, operator system identity, runtime provider/model UI, bounded safe retry/backoff, permission regression | Identity cannot change permissions; no fabricated model availability; no retry after partial stream or ambiguous network failure |
| C — Local productivity | Read-only Health panel, user-approved local memory, approved-root Finder metadata/index controls, additive SQLite migration | No automatic process termination; no secret memory; imports validated before writes; no filesystem escapes or broad scanning |
| D — Advanced intelligence | Editable workflow drafts/dry-run/pause, honest language-pack state, explicit screen preview/consent and dedicated vision request | No arbitrary LLM shell; no screenshot transmission before consent; cancel blocks sending; content never changes identity/policy |
| E — Desktop experience | Optional orb/tray, official update discovery, measured reactor optimization and accessibility | OFF-by-default experimental features; no visibility-triggered mic; safe official URLs; no auto execution; compare actual CPU/RAM |
| F — Installer and gate | Freeze candidate, audit dependencies/history/secrets, build installer/ZIP, five independent full regression runs and five distinct verification passes | New test state per process; restart five-round sequence after a code failure/fix; clean Windows/real audio cannot be replaced by mocks |

Review, meaningful targeted checks, source-only commit/push and an updated handoff are required after each milestone. Do not proceed past an unresolved code failure. Hardware checks can remain explicit external verification blockers while independent engineering continues.

## Mandatory outstanding verification

Real normal-volume speech, representative “Hi NEXIS,” selected-provider inference, audible output, physical hot-plug, low-end hardware behavior and clean Windows 10 build 19045+/Windows 11 install/uninstall are **NOT VERIFIED**. The owner has been given one Voice Studio test instruction. Existing three standalone and five integrated real conversation cycles remain pending. No owner interaction has been simulated.

The final five full regression executions and five verification passes have **not yet been performed**; source is still changing. Current release verdict: **NO-GO**, because mandatory real-world gates and later milestones are incomplete. No release, installer upload or deployment is authorized.
