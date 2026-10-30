# Nexis v1 — NEXIS v1.4.1 development candidate (1.4.1)

29 October 2026. Prepared from the newest working tree for ASH's personal testing.
Public target 1.0.0 remains unfinalized; this is not a stable public release.

## Consent navigation hotfix

- Required I understand consent enables Next when checked and blocks it when unchecked, including saved capability selections.
- The requirement stays visible above the scrollable permissions.
- Version 1.4.1 uses the normal installer identity to update the existing registered program and shortcuts; historical 1.4.0 side-by-side test builds remain separate.

## Included rebuild work

- Always Active header entry and optional orb/tray standby, with a separately
  opted-in local Vosk Hey NEXIS phrase listener and confidence control.
- Wake-to-command handoff through existing permissions, hard mute, visible status,
  Windows busy/lock gating, speech/task pause and explicit failure recovery.
- Required name entry and explicit saved API configuration or Manual / Offline
  choice during first run; conversational personalization and local name recall.
- Setup maintenance choices: Install / Repair and confirmed registered uninstall.

- Exact NEXIS native window title; approved artwork/icons preserved; normal frame.
- Personalized welcome with three mode choices and persistent mode/Settings access.
- Expanded name/permission/UAC/screen/microphone/speaker/provider/theme onboarding.
- Eight-section Settings hub, persistent name/default mode and six live themes.
- Real state-driven orb feedback for permission review, mute and connection failure.
- Smaller-window chat controls; existing telemetry, workflows and desktop tools.
- Explicit saved searchable conversations, export/deletion policy and schema 5.
- Explicit Ollama configuration without automatic installation/provider fallback.
- Configurable global command launcher, conflict reporting and shutdown cleanup.
- Shutdown/cancellation protections; no custom cursor override or system cursor edit.
- Proprietary All Rights Reserved notices and a proposed EULA for owner review.

## Version naming

This build is NEXIS v1.4; Windows stores 1.4.1. Significant feature changes
advance the middle number (1.4 to 1.5); smaller fixes advance the final number
(1.4 to 1.4.1). Public product/package naming stays Nexis v1. This naming does
not certify public readiness. The latest rebuilt reactor and floating orb are
compiled from current source; the old 1.3.x application is not repackaged.

## Packaging changes

- Engineering metadata advanced to 1.4.1 to distinguish this source from earlier
  candidates; no final 1.0.0 version was falsely assigned.
- Fresh source build with bundled Python/Qt/audio runtimes and verified 14-file
  English Vosk model; no prior NEXIS executable is used as an application input.
- Packaged self-check updated for required onboarding identity and schema 5, with
  actual rebuilt-mode/settings/chat/permission checks.
- User documentation replaces internal engineering handoffs in the distribution.
- Installer and ZIP hashes/evidence are generated from actual completed artifacts.

Wake reliability limits, dictation, automatic barge-in and other missing features are listed in
KNOWN-LIMITATIONS.md. Full public readiness, signing, final EULA, real voice/live
services and clean Windows 10/11 qualification remain separate gates.
# Living Core recovery rebuild

This separate 1.4.1 test candidate includes consent-page recovery, setup checkpoints,
atomic completion and the 340-dot Fibonacci particle sphere. Read
`LIVING-CORE-CANDIDATE.md` and the matching engineering report for verification
scope, SAPI activity fallback and remaining release gates. Historical candidates
remain separate.

