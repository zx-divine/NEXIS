# NEXIS 1.1 — application source

Public update target: **1.1.0**. Current engineering build: **1.4.2** (development candidate). Engineering versions stay monotonic and are separate from public version names.

This repository contains the application source, tests, build/installer tooling, approved branding, dependency declarations and license notices. Installers, portable archives, voice model weights, private profiles, credentials, signing private keys and machine-specific verification recordings are excluded.

The Windows updater uses python-tuf with Ed25519-signed metadata and the existing per-user Inno Setup installer. Settings → General → Software Updates includes automatic checks/download preferences, manual checks and Restart & Install. Signed packages are verified before installation; active work blocks restart and a profile recovery snapshot is retained.

A signed 1.4.2 → 1.4.3 upgrade and restart was demonstrated with isolated test identities/keys and a loopback HTTPS fixture. The final source regression passed **667 tests, with 2 skipped**. Production GitHub feed delivery, Authenticode signing and clean Windows 10/11 qualification remain pending. Publishing this source does not publish a binary release or signed update feed. See the [update guide](assets/release/UPDATE-GUIDE.md) and [update release notes](assets/release/UPDATE-RELEASE-NOTES.md).

## Current functionality

- Approved NEXIS branding, personalized onboarding, six themes, animated state-driven
  orb, three modes, persistent Settings and context-preserving mode switching.
- Explicit API setup or an offline-for-now choice; provider profiles protected by
  Windows DPAPI. OpenAI-compatible, OpenRouter, OmniRoute, Gemini and Ollama adapters.
- Always Active tray/orb controls and separately opted-in local Hey NEXIS listening.
  Say the phrase, pause for the listening indicator, then speak. Hard mute, microphone
  permission, Windows eligibility and tool authorization are enforced.
- Local speech recognition, Windows speech synthesis, saved searchable conversations,
  optional local memory, global launcher, supported desktop/file tools and Doctor.

Source folders: `src/nexis/ui`, `core`, `platform`, `actions`, `storage` and `utils`.
`src/nexis/main.py` is the application entry point, not a separate packaged launcher.

## Source development

Use Windows 10 x64 build 19045+ or Windows 11 x64, preferably Python 3.12 in an
isolated environment. A source checkout requires Python and its dependencies;
this repository does not supply a Windows installer or bundled runtime.

```text
python -m pip install -r requirements.txt
python -m pip install -e .
python -m nexis.main
```

Provide your own authorized API configuration or choose Manual / Offline.
Voice model weights are intentionally absent from Git. The application offers
consent-based setup of the pinned English Vosk model; its source/license/hash
metadata are retained under `assets/models`. No microphone opens just because
the application was installed or onboarding checkboxes were selected.

```text
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m ruff check src tests
```

Tests use synthetic temporary profiles and mocked platform/provider boundaries.
Packaging and updater tests are included. Native upgrade qualification uses separate QA identities/profiles.

## Limits and privacy

See [SECURITY.md](SECURITY.md) and [current feature limits](assets/release/KNOWN-LIMITATIONS.md).
Live AI accounts, human microphone/audibility, real-room wake false activations,
long sessions, device recovery and clean Windows lifecycle require further testing.
One uninterrupted wake-plus-command sentence and automatic speech barge-in are not
implemented. Many original V1 productivity/ecosystem requirements remain incomplete.

## License

Copyright © 2026 NEXIS. All Rights Reserved. Original code is proprietary; public
visibility does not grant an open-source license. Third-party components retain
their own terms. The [EULA draft](docs/NEXIS_V1_EULA_DRAFT.md) awaits owner review.
No company identity or registered trademark is asserted.
