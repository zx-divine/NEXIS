# NEXIS V1 — application source

Latest development-candidate application source: **1.3.9**. The intended public
V1 target is 1.0.0; the full product is **NOT READY** for a final public release.

This repository contains application code, tests, required approved branding,
dependency declarations and license notices. Windows installers, portable ZIPs,
launcher/bootstrap files, packaging scripts, old release folders, private profiles,
API credentials and local verification recordings are excluded.

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
Packaging-only tests were excluded with the removed packaging project files;
application, permission, branding and wake lifecycle tests remain.

## Limits and privacy

See [SECURITY.md](SECURITY.md) and [current feature limits](docs/KNOWN-LIMITATIONS.md).
Live AI accounts, human microphone/audibility, real-room wake false activations,
long sessions, device recovery and clean Windows lifecycle require further testing.
One uninterrupted wake-plus-command sentence and automatic speech barge-in are not
implemented. Many original V1 productivity/ecosystem requirements remain incomplete.

## License

Copyright © 2026 NEXIS. All Rights Reserved. Original code is proprietary; public
visibility does not grant an open-source license. Third-party components retain
their own terms. The [EULA draft](docs/NEXIS_V1_EULA_DRAFT.md) awaits owner review.
No company identity or registered trademark is asserted.
