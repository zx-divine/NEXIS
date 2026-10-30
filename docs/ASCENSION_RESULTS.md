# Ascension 1.3.5 verification results — 24 October 2026

**NOT READY — RELEASE BLOCKED**

Engineering/packaging commit: `db30fb842d03c3fee2b193153ae254d694b81a6f`, branch `codex/project-ascension`. Core feature commit: `3ac5ec9819fab2911248e8a6e3e394082633009d`.
Frozen source SHA-256: `57e5dd822d98d3fb10f0f09aa58761ae3458c0a58753c9487d5593814367de9d`.

## Automated and native evidence

- Five independent serial regressions of unchanged corrected source: **459 passed, 1 skipped in each**. Process seconds: 76.59, 68.42, 64.67, 70.62, 82.59. Skip: Windows symlink privilege. No security setting was changed to remove it.
- Ruff and whitespace checks passed. Staged-source privacy/credential heuristic scan passed for the reviewed source; it does not prove every possible secret/bug is absent.
- Initial baseline: 395 passed / 1 skipped / 1 shutdown timeout. First expanded suite: 451 passed / 1 skipped. One earlier final attempt failed the three-second workflow-resume join (453 passed / 1 skipped / 1 failed); its isolated workflow suite passed 11 tests, including 0.11-second resume. No test timeout was weakened. The failed run is preserved and excluded from the five current passes; its cause is not conclusively established.
- Controlled SAPI-to-file / Vosk checks: **13 passed, 0 failed**, synthetic audio and seeded noise only. No microphone capture or speaker playback. Physical normal-volume recognition/audibility and Hindi/Hinglish remain unverified.
- Native Windows default-browser request submitted; Edge process creation observed; absent browser rejected without fallback; cancellation prevented launch. Page loads were not verified. Eligible Edge/Firefox/Brave registrations were discovered on this host; other browsers require their installed registrations and separate checks.
- Native Qt layouts and isolated simulated 100%/150% captures were examined at requested 820×600 / 1366×768. Native 150% OS scaling constrained the larger logical window to available screen geometry. Initial offscreen font discovery lacked glyphs; registering Windows fonts fixed the probe's text rendering. Forced scaling is not physical display/accessibility certification.
- Minimal live selected-provider request: **FAIL / AUTHENTICATION**. No credential change, provider switch or private-context transmission. Account repair is required.
- Current-host frozen offline executable, extracted portable CRC/identity/offline launch, native import/private-file audit, numeric/text installer metadata, actual per-user installer upgrade and installed offline startup passed. The complete installed payload matched the newly built payload. Python network attempts in offline smoke tests: zero. Real clean Windows 10/11 and uninstall remain owner tests.
- The first package failed the bundled Gemini SDK fixture in SSLContext creation. Python 3.12.14's managed SSL module required a public certificate-distrust sidecar omitted by PyInstaller. An isolated trace passed after adding that original resource unchanged. The spec now validates/bundles it conditionally and fingerprints its bytes; TLS verification/distrust was preserved. The failed payload remains under `dist/ascension-1.3.5-failed-ssl`. Earlier five 454-pass runs were invalidated by the packaging correction and are not the final evidence.
- Default English STT: all 14 model files/hash pins and real packaged decoder initialization checked. Windows SAPI voice/driver data remain external prerequisites. No trained wake detector is bundled.
- Original user data, encrypted profiles, 1.3.4 candidate packages and NEXIS LAUNCH handoff: **32 tracked hashes unchanged**. Previous installed payload was copied to private verification storage before upgrade. USB was only read; originals were not removed.

## Performance boundary

Final measurements use the current i3-6100U / Windows 10 build 19045 / 8 GB host, native Qt, isolated database, and concurrent Codex/browser/Windows background work. CPU numbers are percent of one logical core. Source first-window event excludes imports and is not a cold-boot guarantee. Full per-mode metrics are in the private JSON report. No physical listening or live chat resource result is claimed.

| Mode | CPU % one core | Working set MB |
|---|---:|---:|
| idle | 14.58 | 122.64 |
| active | 49.37 | 122.66 |
| reduced | 0.52 | 122.68 |
| minimized | 0.0 | 122.73 |
| orb_standby | 2.07 | 124.96 |
| orb_reduced | 0.52 | 125.23 |

Default-model initialization: 2.273 s; working set with model loaded and no capture: 240.42 MB. Shutdown with no background services: 37.97 ms. See the owner checklist for actual listening, chat, sleep/hot-plug and display testing.

## Security and packaging limits

OSV queried 53 installed runtime/development distributions and identified historical development setuptools 84.0.0 ([GHSA-xmj3-9gf7-h52w](https://github.com/pypa/setuptools/security/advisories/GHSA-xmj3-9gf7-h52w)). New requirements use 84.1.0+ and the workspace build uses a separate patched copy. Historical environment retained; setuptools excluded from the frozen application. No other finding returned by that query; native/OS components and advisory coverage remain limits.

New diagnostic exports omit logs, paths, credentials, device names, memories and chat. URL validation, explicit browsers, cancellation/delivery boundaries, memory/history isolation and existing security suites passed. This is scoped evidence, not a claim that all bugs are found. A Windows/remote request already submitted cannot be recalled; cancellation cannot forcibly interrupt a native COM call already in progress.

The installer and application are unsigned development artifacts. Model/runtime notices and documentation are included, but application licensing and Qt corresponding-source/compliance decisions remain unresolved. No source push, binary upload, GitHub Release or website change/deployment occurred.

## Outputs and continuation

Local output directory: `dist/ascension-1.3.5`. Installer: `NEXIS-Desktop-1.3.5.0-Setup.exe`; portable: `NEXIS-Desktop-1.3.5-Windows-x64-Portable.zip`; hashes: `SHA256SUMS.txt`; machine-readable identity: `RELEASE-MANIFEST.json`. Evidence/logs remain local under `.verification-ascension-20261024`; no private logs or user data are included in the installer/ZIP/source archive.

Read ASCENSION_DEVELOPMENT.md for setup/build/recovery, ASCENSION_OWNER_CHECKLIST.md for real tests, and ASCENSION_HANDOFF.md for retained functionality and roadmap. Scheduling, trained wake detection, Hindi/Hinglish STT, advanced conversational automation, a fuller session privacy dashboard and complete accessibility/clean-OS qualification remain incomplete. Physical lock/sleep recovery and audio interruption remain unqualified; notification eligibility checks alone are not a lock/suspend certification. The USB report still labels the historical migration INCOMPLETE; keep laptop originals.

ASH must resolve licensing, repair/verify provider access and complete physical audio/clean Windows tests before separate release approval. Do not call this Stable or publish it.
