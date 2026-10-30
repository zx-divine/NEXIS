# Project Ascension engineering handoff — 24 October 2026

ASH remains final approver. Engineering **1.3.5**, public identity **v1.0 Development Candidate**, channel **development**. Branch: `codex/project-ascension`. Original source baseline: `ae27bf8650548077e83e6fd5722df88c18aac135`. The original 1.3.4 launch candidate, launch directory, USB archive and development environment remain preserved. No website work, source push, binary publication or public release occurred.

## Completed source work

- NEXIS Doctor: explicit background local checks for application/database/config/dependencies/storage, available voice components, unverified physical audio, provider configuration, system aggregates and privacy state. Separate confirmed fixed-sentence provider inference. Statuses never claim unperformed physical tests. Exports omit private content, raw profiles, device names, paths and logs.
- Settings Hub: gear and Ctrl+,; General, Voice, AI & Models, Automation, Permissions & Privacy, Desktop & Appearance, Diagnostics and About. Existing voice/provider/permissions controls are reused, settings persist, and moving away from Voice stops diagnostic capture/output.
- Website opener: controlled names, bare domains, IDNA, explicit HTTP(S), preserved paths/queries, optional browser choice, safe Windows registrations and installed/elevation policy. Default requests use Windows' current URL association. Missing browser never falls back silently. Single natural requests route locally through normal capabilities/approvals. Results distinguish submission/process start from unverified page loading.
- Providers: Groq and NVIDIA compatible presets retain existing adapters/profiles. No guessed model IDs, shared keys, protocol conflation or automatic paid-provider fallback.
- Presence: existing companion is labeled Always Active standby/PTT, not wake-word detection. Minimize-to-tray and sign-in startup remain separate opt-ins. Explicit tray Wake/Settings, muted orb label and privacy-safe capture stop on unavailable/locked notification state.
- Memory: on/off blocks saves/imports, preserves review/export/delete; natural remember/forget drafts and saved-memory review stay local and excluded from future cloud history. Existing schema and records are preserved.
- Reliability: early SAPI initialization cancellation checks, queued clipboard/payload guards and no late voice playback after cancellation/Hard Mute. Existing safety and model/runtime components retained.
- Release tooling: unique evidence directories, shared source fingerprint and isolated candidate build refusing old-output overwrite. Installer supports an explicitly chosen payload directory. See ASCENSION_DEVELOPMENT.md for reproduction and recovery.

## Verification checkpoint

Fresh initial baseline: **395 passed, 1 skipped, 1 shutdown timeout** (195.85 s). First expanded regression after engineering: **451 passed, 1 skipped** (156.09 s). Ruff passed. Later source additions require the final unchanged-source sequence; the private final reports contain authoritative final counts/fingerprint, package hashes and native results. Failed/intermediate evidence is retained and is not counted as current.

The symlink skip requires Windows privilege; no security setting was changed to remove it. One intermediate model fixture activation under OneDrive hit WinError 5. Final rounds use fresh system temporary directories rather than treating this workspace filesystem condition as a production model accuracy result. Physical microphone and audible output were not activated by automated checks.

A minimal live request to the saved selected provider returned **AUTHENTICATION** failure. Credentials were not printed, changed or switched. Mock adapter tests and model-list success cannot resolve this owner-account issue. Current provider availability is not claimed.

Native Qt layout captures use isolated data. Record actual requested/achieved size and device-pixel ratio; OS scaling can constrain native window size. Offscreen/forced scaling is labeled simulation. Performance measurements apply only to their recorded mode/process and concurrent host load, not a guarantee. This host reports the target Intel Core i3-6100U; representative active-listening/chat resource use remains owner-test dependent.

## Security and privacy scope

New tests cover unsafe URL schemes, credentials/control characters, malformed and IDNA domains, browser argument arrays, missing-browser/no-fallback behavior, Windows association use independent of BROWSER, unfamiliar-site review, cancellation before native delivery, diagnostic export privacy, memory on/off/history isolation, Settings routing and late clipboard/voice results. Existing permission/path/workflow/screen/provider suites remain required. Dependency advisory and bundled-native import checks supplement review; they cannot prove absence of every bug, delay-loaded dependency or vulnerability.

No raw logs are exported by Doctor. No sensitive self-repair, shell execution, hidden recording/capture, provider fallback or wider folder grant was added. A native call already submitted cannot be recalled. A blocking native COM call cannot safely be forcibly interrupted by a QThread cancellation event; early checks prevent subsequent work and shutdown waits for safe release.

The current OSV query of 53 installed development/runtime distributions identified historical setuptools 84.0.0 ([GHSA-xmj3-9gf7-h52w](https://github.com/pypa/setuptools/security/advisories/GHSA-xmj3-9gf7-h52w)). New build/development requirements require 84.1.0+; a separate patched workspace build-tool copy preserves the historical environment. Setuptools is excluded from the frozen application. No other finding was returned in that query; this does not cover every native/OS component or prove absence of vulnerabilities.

## Voice and remaining work

An initial frozen 1.3.5 attempt failed its Gemini SDK fixture despite source and prior 1.3.4 fixtures passing. The managed Python 3.12.14 SSL module required an omitted public `codex-rejected-cas.pem` sidecar. An isolated trace confirmed the exact SSLContext failure and passed after copying the original policy resource unchanged. Packaging now validates/bundles the resource conditionally, fingerprints it and retains TLS verification/distrust. The failed payload is preserved. The earlier five 454-pass runs predate this packaging correction; only a new final five-round sequence qualifies the corrected fingerprint.

Default English Vosk weights, VAD, PortAudio and decoder runtimes remain app-owned bundled resources verified by packaging. Windows SAPI engine/voice data and drivers remain external system prerequisites. No trained wake detector is included. English normal-volume physical accuracy, actual speaker audibility/device recovery, Hindi/Hinglish, clean Windows and live account reliability are not certified.

Scheduling, trained wake detection, advanced conversational automation, deeper accessibility qualification and broader file-format indexing remain roadmap items. Existing bounded txt/md indexing, editable workflows, explicit screen assistance and read-only PC Health are retained. Do not imply all requested P1/P2 work is finished.

## Release verdict

**NOT READY — RELEASE BLOCKED**

Application licence/third-party compliance remains unresolved, the saved live provider authentication fails, and mandatory physical audio/clean Windows evidence is incomplete. The development candidate is for local engineering review. Follow ASCENSION_OWNER_CHECKLIST.md, resolve real failures and licensing, rebuild/reverify after code changes, and obtain ASH's separate publication approval.


Project Freedom continues this checkpoint as engineering build 1.3.6. See ASCENSION_FREEDOM_GUIDE.md for the new theme and authorization policy, and ASCENSION_FREEDOM_RESULTS.md for its separate verification evidence. The 1.3.5 artifacts and results remain historical; their passing checks do not qualify 1.3.6. All unresolved owner release gates still apply.
