# Changelog

## 1.3.2 — local verification build (not publicly released)

- Bundle the exact verified English Vosk model and redistribution notices; fail incomplete release builds.
- Automatically detect the included model in setup and voice mode.
- Negotiate model-compatible input rates before recording; avoid feeding unsupported 8 kHz PCM to the default model.
- Remove repeated approvals for ordinary installed apps and duplicate wrapper confirmations; keep grants, revocation and sensitive reviews.
- Verify packaged model hashes/native decoder, offline startup, native dependencies and per-user installation.
- Real microphone/audio and clean Windows qualification remain pending.


## 1.3.0 — 2026-10-16 — Local usability milestone

- Added bounded Windows application discovery, a persistent Unicode catalog, deduplication, availability checks, aliases, hide/remove controls and rescans.
- Routed discovered targets through existing permission previews; unsafe shortcut arguments and interpreter targets remain blocked. Ambiguous app names require a choice.
- Added curated websites and explicit unfamiliar-domain confirmations without weakening URL validation.
- Added consent-driven, pinned and resumable offline model provisioning, safe extraction, engine validation and automatic activation.
- Bundled Vosk, PortAudio and Windows integration dependencies; added default-device capture, missing-device fallback and SAPI voice initialization/playback.
- Added simple saved-provider setup, compatible gateway/local-server detection, Windows DPAPI credential persistence and bounded background AI chat without OS execution tools.
- Added additive SQLite v2 migration, cancellation-aware shutdown, friendly setup failures and startup capability diagnostics.
- Preserved the Crimson HUD, official logo, existing commands, local resources, security protections and stable Windows application identity.
- Qualification and remaining release gates are recorded in docs/V13_RELEASE_VERIFICATION.md. This entry is not a public-release claim.

## Local branding integration — 2026-10-16

- Preserved the supplied NEXIS PNG and generated seven Windows ICO sizes (16–256 pixels).
- Applied the official logo to the executable, native window icon, splash, About and first-run local-preferences wizard.
- Bundled branding assets independently of the development directory, including wheel package data.
- Added a per-user Inno Setup installer with consistent NEXIS.Desktop shortcut/process identity and an optional desktop shortcut.
- Retained version 1.1.0: this branding update does not implement the separate v1.3 provider roadmap.

## 1.1.0 — 2026-10-16 — Crimson Command

- Replaced the card dashboard with an original black/crimson/gold Qt HUD and layered animated reactor.
- Added compact module navigation, bottom command deck, collapsible manual drawer, maximized launch and F11/Escape behavior.
- Added real Windows sensors, history graphs and labeled command-activity visualization.
- Added deterministic session chat and optional explicitly activated offline Vosk/sounddevice recognition.
- Added reduced motion and FPS controls; stop animations and polling when minimized.
- Preserved v1.0 resources, SQLite schema/data, command engine and permission enforcement.
- Added execution phase notifications and tests for all new modes and cancellation.
- See docs/V11_IMPLEMENTATION_REPORT.md for actual measurements, tests and qualification limits.

## 1.0.0 — 2026-10-15

Initial local implementation: native Qt desktop, registered command pipeline,
central permissions, approved app and HTTPS launchers, scoped asynchronous file
search, snippets, workflows, SQLite persistence, privacy-preserving history,
settings, diagnostics and Windows packaging configuration.

Release qualification and actual test results are recorded separately in
docs/VERIFICATION.md. This entry is not a claim of public release.
