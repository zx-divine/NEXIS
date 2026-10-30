# NEXIS approved branding — development build 1.3.7

Owner: ASH. Verification date: 2026-10-25 (client date). Branch: `codex/project-ascension`.
Status: **development candidate verified for this branding scope; NOT READY — RELEASE BLOCKED**.
Source fingerprint: `162141b2f898c8c5592d0273c80efb9efa2566ce5822765b1cf333e377df40a5`. No push, publication or public release was performed.

## Implemented branding

The supplied `assets/branding/NEXIS LOGO.png` is preserved byte-for-byte, SHA-256
`cee617446391da8bf0f3d348f96e0f629e11aa8c9dc9e30356c577d721794b4c`.
The runtime full logo is an identical copy. The metallic futuristic N, blood-red glow,
gold edges, black background and wordmark retain their original colors in every theme.
Full artwork appears in splash, onboarding, About and documentation. The main header
and floating orb display a small approved N badge alongside existing labels.

Small Windows icons use an N-only crop, never a reduced full wordmark. The ICO has
16/20/24/32/40/48/64/96/128/256 px frames. Eleven scaled symbol PNGs and four full-logo
PNGs support future release assets. The installer uses a full-artwork sidebar and
N-only header; executable, tray, taskbar/window, shortcuts and uninstaller share the
same icon identity. The stable Windows AppUserModelID remains `NEXIS.Desktop`.

Qt logo rendering uses the display pixel ratio and refreshes on a scale-change event.
No animation, timer, background service or runtime dependency was added. Changes are
limited to branding display/resources, packaging/verification, version metadata and
documentation. Command, risk, authorization, provider, voice and storage logic is unchanged.

## Asset generation and preservation

`scripts/prepare_branding.py` pins the approved source hash, validates its dimensions,
crops source coordinates `(265,155)-(995,855)`, preserves aspect ratio on black, and
generates deterministic derivatives with Pillow. Pillow remains build-only. The asset
manifest records hashes, roles, dimensions and crop bounds. Runtime assets match source
assets byte-for-byte. Invalid/unapproved source input is rejected before generation.
The source fingerprint now covers every source and packaged branding asset.

3300 protected paths were compared with the before snapshot; all are
unchanged. They include the original supplied PNG, verified 1.3.4/1.3.5/1.3.6 distributions,
owner database and protected credential files, and preserved launch-folder files.
The USB archive was not modified. The previous installed 1.3.6 payload was retained in
private verification recovery storage before the current-host development upgrade.
Owner data/credential hashes were unchanged during upgrade and startup verification.

## Tests and verification

Targeted branding/version tests: **21 passed**. Static analysis and Git whitespace checks
passed. Sixteen new regression cases cover exact approved identity, manifest integrity,
all ICO frames, N-only derivation, deterministic generation, original preservation,
rejection of changed input, 100/150/200/300% pixmap sizes, display-scale refresh and
restricted runtime asset resolution. Existing branding expectations now validate the
approved ten-frame icon against actual generated and compiled resources.

Five independent serial runs used fresh temporary state and the same final fingerprint:

| Run | Passed | Skipped | Seconds |
| --- | ---: | ---: | ---: |
| 1 | 554 | 1 | 151.09 |
| 2 | 554 | 1 | 146.52 |
| 3 | 554 | 1 | 149.48 |
| 4 | 554 | 1 | 147.12 |
| 5 | 554 | 1 | 147.52 |

The one skip in every run is the existing Windows symlink regression requiring
Developer Mode or elevated symlink privilege (`tests/security/test_policy.py:96`).
Permission and security regressions pass in the suite; their behavior was not changed.
The staged-source privacy scan checked 289 files / 9,195,623
bytes and reported no findings (four reviewed dummy URL fixtures remain non-secret).
An additional final scan including this report checked 290 staged files and returned
no findings; see `staged-audit-final.json` in the evidence directory.

Initial evidence is retained: a preliminary 554-pass run was superseded when review
found the legacy packaging checker still expected seven icon sizes and targeted the
old distribution by default. That checker now requires an explicit candidate and new
output directory, validates the manifest and checks all three packaged assets. The
five final runs started again after this correction. A simulated-DPR test assertion
and private rendering probes were corrected for QLabel's native-DPR getter, valid
theme IDs and the offscreen plugin's lack of a tray. These were harness issues; initial
failures and interrupted preliminary results were retained and are not final passes.

## Windows, packaging and DPI results

The new PyInstaller executable, Inno installer and portable ZIP built successfully in
`dist/branding-1.3.7`. New native PE icon groups in both EXE and installer contain all
ten approved ICO frame blobs byte-for-byte. All three runtime assets match. Windows
Shell small/large icons were extracted from executable, installer and private shortcut.
The installed development executable and desktop shortcut were checked after upgrade.
Native Shell captures also show Windows shortcut arrows and NTFS compression overlays:
the payload and installed executables have the `Compressed` filesystem
attribute. These OS overlays are not part of the approved ICO; filesystem compression
and taskbar pins were not changed to remove them.

Current-host native payload, extracted portable and installed offline startup checks
passed with isolated temporary databases and zero attempted network connections.
Windows native window icons and AppUserModelID were verified; complete model, theme,
provider fixture and cancellation startup diagnostics passed. ZIP CRC, manifest hashes,
native dependency audit, installer version metadata and the updated package checker
passed. The preceding installed payload was preserved; no owner's running NEXIS
process was force-closed. This is current-host upgrade evidence, not a clean-OS test.
The installer was exercised silently; its interactive wizard was not visually inspected.
The static native audit checked 1,004 PE imports, with zero missing dependencies,
missing required modules or private files, and all 14 bundled model files present.

Native Qt Windows captures at the actual display ratio of 1.5 verified Dashboard,
About, onboarding, splash, orb and tray branding, including OG Blood Red and Arctic
White at requested 820x600 and 1366x768 layouts. Actual window dimensions are
recorded in the raw results rather than assumed to equal requested sizes. Separate
offscreen captures at 100% and 200% verified logo sizing
and layout; unit tests also cover 300%. Full approved artwork retains its black
background in Arctic White. The approved colors are not theme-tinted.

Physical multi-monitor movement and physical 100%/200% screens were not qualified.
Offscreen rendering can use different OS-symbol font fallback; native 150% capture
shows the actual Windows glyphs. Existing taskbar pins were not recreated and Explorer
was not restarted or its icon caches deleted; existing pins may await Windows refresh.

## Footprint and startup observations

The three runtime branding assets total 2,065,710 bytes,
compared with 2,244,926 bytes previously
(-179,216 bytes difference). No new animation loops or idle
timers were introduced. One native source UI construction sample was
1667.48 ms. This is UI construction only, excludes import/process
startup, and is not a matched performance comparison. Voice and AI workloads were not
benchmarked in this branding task. No CPU/RAM improvement is claimed from these data.

The separate packaged startup probes recorded these UI construction times (excluding
process/import startup). These stages ran at different times under host load and are
not an equivalent-conditions comparison with build 1.3.6:

| Startup scope | UI construction ms |
| --- | ---: |
| built payload | 8611.6 |
| extracted portable | 7368.6 |
| installed development | 5045.4 |

## Development artifacts

| File under dist/branding-1.3.7 | Bytes | SHA-256 |
| --- | ---: | --- |
| `payload/NEXIS/NEXIS.exe` | 10,191,566 | `a11d83c948fe45c6ac1e7c64db0dc52859c28e2161e8e975978913d1217619f2` |
| `NEXIS-Desktop-1.3.7.0-Setup.exe` | 99,767,191 | `0e9bd07ae37f880d7c25d6ac7635bc73d21edb9742bac5527aea11cf2578e2b6` |
| `NEXIS-Desktop-1.3.7-Windows-x64-Portable.zip` | 130,143,044 | `2ae2fd8f0a7cf7749903e12458b98360ea2362737590531a3e90c0cf9f6a5fbf` |

Executable and installer remain unsigned development artifacts. The portable archive
must be extracted completely; keep its adjacent `_internal` folder.

## Remaining limitations and release blockers

No confirmed new branding defect remains in the final checks. This task does not
qualify microphone capture, audible speaker playback, live provider credentials,
radio-off/on hardware behavior, licensing, or clean Windows installations.
Existing release gates remain: owner licensing/third-party compliance review; physical
microphone and speaker checks; live provider reliability (earlier authentication
failure remains unqualified); clean Windows 10/11 install/upgrade/uninstall; broader
peripheral/remote-session and accessibility/multi-monitor qualification; and distribution
signing/review. No public readiness or publication approval is claimed. ASH alone
decides whether and when NEXIS is published.

## Files changed

The following is the complete source/documentation/asset change list for this task.
Generated private QA captures, logs and recovery payloads remain ignored. Build outputs
are new files under `dist/branding-1.3.7`; no previous candidate directory was reused.

- `NEXIS.spec`
- `README.md`
- `assets/branding/NEXIS LOGO.png`
- `assets/branding/NEXIS.ico`
- `assets/branding/NEXIS_logo.png`
- `assets/branding/NEXIS_symbol.png`
- `assets/branding/installer-sidebar.png`
- `assets/branding/manifest.json`
- `assets/branding/scaled/NEXIS-logo-1024.png`
- `assets/branding/scaled/NEXIS-logo-128.png`
- `assets/branding/scaled/NEXIS-logo-256.png`
- `assets/branding/scaled/NEXIS-logo-512.png`
- `assets/branding/scaled/NEXIS-symbol-128.png`
- `assets/branding/scaled/NEXIS-symbol-16.png`
- `assets/branding/scaled/NEXIS-symbol-20.png`
- `assets/branding/scaled/NEXIS-symbol-24.png`
- `assets/branding/scaled/NEXIS-symbol-256.png`
- `assets/branding/scaled/NEXIS-symbol-32.png`
- `assets/branding/scaled/NEXIS-symbol-40.png`
- `assets/branding/scaled/NEXIS-symbol-48.png`
- `assets/branding/scaled/NEXIS-symbol-512.png`
- `assets/branding/scaled/NEXIS-symbol-64.png`
- `assets/branding/scaled/NEXIS-symbol-96.png`
- `docs/ASCENSION_BRANDING_RESULTS.md`
- `docs/BRANDING.md`
- `installer/NEXIS.iss`
- `pyproject.toml`
- `scripts/candidate_evidence.py`
- `scripts/check_package.py`
- `scripts/prepare_branding.py`
- `scripts/version.txt`
- `src/nexis/__init__.py`
- `src/nexis/assets/branding/NEXIS.ico`
- `src/nexis/assets/branding/NEXIS_logo.png`
- `src/nexis/assets/branding/NEXIS_symbol.png`
- `src/nexis/branding.py`
- `src/nexis/ui/branding.py`
- `src/nexis/ui/main_window.py`
- `src/nexis/ui/orb.py`
- `tests/ui/test_approved_branding.py`
- `tests/ui/test_branding.py`

## Evidence locations

- `.verification-branding-20261025/five-frozen-v2/results.json` and five raw logs.
- `dist/branding-1.3.7/BUILD-REPORT.json`, `RELEASE-MANIFEST.json`, `SHA256SUMS.txt`.
- `.verification-branding-20261025/distribution/results.json` and native bundle audit.
- `.verification-branding-20261025/native-icons/results.json` and Shell icon captures.
- `.verification-branding-20261025/package-check/package-verification.json`.
- `.verification-branding-20261025/ui-windows-native-v2` and offscreen capture directories.
- `.verification-branding-20261025/preservation-before.json`, `preservation-after.json`.
- `.verification-branding-20261025/staged-audit-v2.json`, `asset-footprint.json`.
