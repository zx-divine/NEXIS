# Operation NEXIS Launch — 22 October 2026

Creator: ASH. This source prepares **v1.0 Launch Candidate**, engineering build **1.3.4**. It is not a public stable release.

## Version transition

Engineering 1.3.2 and 1.3.3 remain historical candidates, preserved locally. Their binaries are never renamed into v1.0. Monotonic engineering/Windows numeric version 1.3.4.0 preserves upgrade ordering and the existing AppId/data location. Application/About/PE ProductVersion/installer explicitly say v1.0 Launch Candidate. Canonical intended first stable tag is v1.0.0; public branding will be NEXIS v1.0 Stable only after the release gate. The updater compares the public version and can offer the first Stable to its candidate, rather than treating internal 1.3.x as newer than public 1.0.0.

Producing Stable requires a new engineering build, actual version/channel/metadata/About/installer changes, new packages, affected verification and all five serial regressions. Renaming a candidate EXE or ZIP cannot satisfy that gate.

## Focused changes

- Fixed dispatch-boundary cancellation for structured AI tools and manual commands. Deterministic disposable tests reproduced clipboard callback delivery and launch submission after cancellation; final checks now reject cancellation/expiry before dispatch, and capability rechecks occur after progress notification. This cannot recall Windows calls already submitted before cancellation. No approval bypass was added.
- Updated certifi from 2026.7.22 to 2026.10.19 for [GHSA-6q48-6c7w-9gw2](https://github.com/certifi/python-certifi/security/advisories/GHSA-6q48-6c7w-9gw2). Source requirements are pinned; frozen checks verify version and actual bundled certificate data. The old candidate remains preserved historical evidence, not an approved launch package.
- Bundled the actual unresolved application LICENSE and channel notice, upstream Qt licence texts and practical library-replacement/source guidance. The missing Qt open-source texts were a verified packaging gap. [Qt’s obligations](https://www.qt.io/development/open-source-lgpl-obligations) still require ASH's corresponding-source/redistribution review. Texts alone do not certify compliance or grant a NEXIS licence.
- Preserved the HUD/brand, existing features, user data, capabilities, per-user installer identity and offline default model. No unrelated features or website changes.

## Local handoff

The Windows Known Folder API resolves the actual Desktop. NEXIS LAUNCH contains review-only candidate packages when successfully built, plain-English user guides, a manifest/hash list, evidence summaries, a manual checklist and unpublished GitHub drafts. Private logs, databases, profiles, credentials, recordings and build caches are excluded. Candidate filenames include Candidate-build-1.3.4; the requested Stable names are reserved until truthful qualification.

The final local reports record actual final test counts, package results and hashes. Original evidence, the advisory finding, interrupted build/package checks and pre-fix failure logs remain private for audit; passes predating runtime changes do not qualify the final candidate.

## Remaining mandatory gates

Application licence choice and corresponding-source/third-party compliance; three standalone and five complete real voice cycles; actual normal-volume English brand recognition/audible output; physical audio/hot-plug/Hard Mute; relevant live-provider reliability; clean Windows 10 build 19045+/Windows 11 without Python, upgrade/uninstall; target hardware and physical display/tray behaviour. Hindi/Hinglish is not qualified.

Current disposition: **NOT READY — RELEASE BLOCKED** pending licensing and required human evidence. ASH owns final approval. Source-only normal commits/pushes do not authorize binary upload, public Release, website availability or deployment.

The final build entry also collects installed runtime licence notices offline: 36-package default requirement closure, 51 notices (including tagged upstream Vosk COPYING for its wheel omission), no development extras. Full notices and a deterministic inventory live under assets/licenses/runtime and ship under _internal/licenses. This improves notice completeness; it does not certify legal compliance. Final package verification follows this notice completion.

## Final local verification checkpoint

Five independent serial final regressions: **396 passed, 1 skipped each**, elapsed process seconds 70.11, 93.25, 74.64, 81.72, 83.36. Frozen source fingerprint: 52d96e878c9351cef68c1fcc6e3b447fed33795e8bc69227c0bb509cc7cd04f8; final recomputation matched. The one skip requires Windows symlink privilege. Interrupted/pre-fix attempts were preserved but not counted.

Current-host frozen offline startup, native audit (1,004 PE imports), final installer/PE metadata/installed data preservation and fresh extracted portable launch passed. The ZIP, inner EXE and installed EXE identities match. Mission-wide user-data hashes remained unchanged. Package privacy scan: 1,055 files, 72 NEXIS modules/896 code objects, no findings within its stated scope. Both binaries are unsigned. Temporary portable cleanup retained one test EXE; automatic approval review blocked recursive removal, so cleanup is pending and no bypass was attempted.

The actual setup PE had a blank textual file version/generic description before final correction. It now derives numeric/text/product/description fields explicitly from the application metadata; installed verification asserts them before running. The runner writes RUNNING before its first round to prevent stale PASS evidence.

The local NEXIS LAUNCH handoff contains candidate installer/ZIP, user/privacy/system/limitation/licence guides, SHA-256 manifest, seven verification documents and unpublished GitHub drafts. No public Stable artifact was created. **NOT READY — RELEASE BLOCKED** remains the verdict for licensing and mandatory human qualification.
