# Always Active, wake listening and first-run identity/API — build 1.3.9

Implemented at ASH's request, with local development-candidate branding preserved.
The intended public release remains 1.0.0; full V1 is NOT READY.

## Implemented

- Always Active is directly accessible in the header, retaining the original
  optional floating orb, tray controls, restore/collapse, mute and explicit exit.
- Separately opted-in local Vosk Hey NEXIS phrase spotting, configurable minimum
  confidence, bounded input queue, single shared local model, command capture after
  activation, twenty-second command timeout and explicit failure recovery.
- Execution-layer microphone permissions and hard mute are checked during capture.
  Windows non-notification/locked/fullscreen states pause listening. No background
  listener starts without both opt-ins and a visible main window/tray indicator.
- Capture pauses for other audio, AI and desktop command tasks. Queued commands
  are discarded after mute/revocation/cancellation. The normal tool permissions and
  sensitive-action approvals remain in force; radio changes still require review.
- Name entry is required on first run, saved locally and editable in General.
  The configured AI receives the name as explicitly delimited data. Local name
  recall works without an API. No key or personal profile is included in builds.
- API onboarding now requires saving/selecting a provider/model or explicitly
  choosing Manual / Offline and setting it up later. Network connection tests stay
  explicit, and credentials retain Windows DPAPI protection.
- Onboarding offers Always Active and wake choices, but selecting them never
  records inside the wizard. Runtime controls reload those saved choices after
  completion. Windows sign-in startup remains a separate opt-in.
- The previous Setup maintenance revision 2 is retained: Install / Repair and
  confirmed registered uninstall, with the separate personal profile preserved.

## Actual evidence obtained before release packaging

- Initial targeted source run: 37 passed. Additional final probes are recorded in
  the packaging verification report; earlier results are not counted as current
  exact-source release regressions.
- Eight real Vosk decoder cases from two Windows SAPI file voices: both Hey NEXIS
  cases detected, six negative cases rejected. No physical audio opened.
- File-fed actual wake worker: positive wake-to-open-notepad transcription,
  non-wake rejection and permission revocation passed with input stream closure.
  An earlier accelerated fixture overflowed; the final fixture uses real-time
  pacing and the production handoff avoids replaying standby audio.
- 51 actual Qt widget captures at two sizes and six themes, including Always
  Active and API onboarding. Windows verified title NEXIS, icon, native frame,
  maximize, minimize and restore. Construction-to-first-event was 1.789 seconds
  excluding imports on this host; this is not whole-application startup profiling.
- The broader in-progress full regression completed 608 passed, 1 skipped.
  Source subsequently changed, so final exact-source regression evidence is
  required independently before packaging.

## Limitations and remaining acceptance

Say Hey NEXIS, pause for the indicator, then speak the command. One uninterrupted
wake-plus-command sentence, a custom trained neural wake model and automatic
speech barge-in are not implemented. Standby decoding is English and local; the
activated command may reach only the configured provider under existing grants.

Real human speech, room noise/false activation rates, extended microphone use,
device unplug/resume, live AI services and clean Windows 10/11 lifecycle tests
remain partially verified or blocked. Do not count synthesized fixtures as human
speech qualification. No publication, cursor changes or USB backup operations are
authorized or performed by this work.

Vosk's documented grammar recognizer is used:
https://github.com/alphacep/vosk-api/blob/master/python/example/test_words.py
Windows notification eligibility values follow Microsoft's enum:
https://learn.microsoft.com/en-us/windows/win32/api/shellapi/ne-shellapi-query_user_notification_state

## Completed packaging and delivery — 28 October 2026

After correcting the tray unmute label and welcome-screen hard-mute visibility,
the final source fingerprint was
`b1752f82f7251104c6017798ee37fef6e1b0a44b473a5866352d295916304089`.
Five fresh serial regression processes each passed 603 tests and skipped one
privilege-dependent symlink test. Earlier source revisions were preserved as
superseded evidence and were not counted for this build.

The fresh PyInstaller x64 GUI build, frozen offline startup, Inno compilation,
package checks, native imports, private-file/literal scan, shell branding,
capability startup, safe ZIP extraction and extracted portable startup passed.
The isolated Inno fixture also passed actual install/uninstall and preservation
of an untracked synthetic personal file; no production installation was used
for this 1.3.9 lifecycle test.

The Desktop `RELEASE NEXIS` folder was updated with the exact requested layout:

- Setup: 99,820,554 bytes; SHA-256
  `ba22e91ca7d645dbf981fd392763447bb3327a400470f6a985adc33be238a9a8`.
- Portable: 130,181,531 bytes; SHA-256
  `a1d5880a564090384982d4be375334e5b902ec046174ec84671a2cc97b38131b`.
- All 73 listed deliverable hashes verified. Previous Desktop contents were
  preserved privately before replacement; no unrelated files were deleted.
- Seventeen recorded owner-profile files and the legacy executable were checked
  unchanged across this packaging run. No USB modification, push or publication.
- Runtime advisory lookup: 36 packages, zero advisories returned; this remains
  a limited known-advisory check, not a complete security certification.
- Real-time synthetic standby processing: 18.109 seconds, 1.578 process CPU seconds,
  8.71% of one logical core and 167.52 MB standalone working set. No activation,
  command or error occurred. Physical input, UI overhead and long sessions were
  excluded from that measurement.

The candidate remains unsigned and NOT READY for the full public V1 specification.
Next required work: human microphone/false-activation and audible TTS tests,
authorized live-provider personalization/reliability, clean Windows 10/11
installation/upgrade/uninstall, long-session/device recovery, final EULA and
third-party compliance, and the outstanding mandatory features recorded in
the delivered KNOWN-LIMITATIONS.md.
