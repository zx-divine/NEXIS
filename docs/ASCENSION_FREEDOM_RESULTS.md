# Project Freedom — engineering verification, build 1.3.6

Status: development revision; NOT READY — RELEASE BLOCKED. Publication belongs exclusively to ASH. This report records the completed local engineering work and distinguishes automated fixtures, native observations and unresolved owner checks.

## 1. Implemented changes

Project Ascension was continued on its existing branch. Six themes, validated custom appearance, shared operation authorization, native radio controls, clearer approval dialogs and cancellation protections were added. No new Python dependency was introduced. The original 1.3.4 launch candidate, verified 1.3.5 distributions, credentials and owner settings were preserved. No push, publication, USB write, final archive or cleanup mission was performed.

Implementation source was frozen at commit `7f10144003e1267a3ab92cb43eacb4b33513b876`. Its candidate fingerprint is `f1154a18f08e7ecf635aaa6e902d92093510c8616f9498e599ac6fa8d0472c37`. The later report-only commit does not change that fingerprint. The previous verified checkpoint remains `3aeca41d67fc4fdb64471ff06847679ff9551088`.

## 2. Root cause of excessive prompts

The old Permissions class prompted for every MEDIUM-or-higher preview. Website resolution marked unfamiliar destinations medium even after valid HTTP(S) resolution; the AI tool executor repeated that escalation. Task Manager was caught by a sensitive executable-name pattern, and its utility wrapper was medium. Saved workflows and AI multi-step plans added enclosing approvals before child authorization. Delegated app/workflow wrappers also needed careful handling to avoid duplicate checks.

The fix changes execution policy, not just labels. The shared Permissions decision allows validated LOW operations and only named bounded MEDIUM operations automatically. Capability grants remain separate. Unknown-site metadata no longer decides approval. The enclosing AI-plan prompt was removed, while every consequential child still uses the shared executor. Saved workflow envelopes authorize no sensitive child on their own.

## 3. Exact permission policy

LOW: validated HTTP/HTTPS websites/domains; fixed ordinary Windows apps; verified ordinary installed apps; validated registered Store apps; approved documents/folders, searches and metadata; Windows Known Folder navigation; ordinary Settings pages, system information, PC Health and Task Manager; exact explicit radio requests. Existing category grants and first-run disclosure remain required. New installations do not silently grant capabilities or approve search roots.

MEDIUM: automatic only for the explicit bounded allowlist `run`, `workflow_run`, `volume_set`, `mute_set`, `browser_open_tabs`, `radio_set` (radio requests currently classify LOW). Creating/copying/moving/renaming data, clipboard writes through AI, content previews sent into AI, installation-directory access and consequential existing-tab operations retain review according to their resolved classification.

HIGH: sensitive Settings interfaces, single-file recycling, unknown/unverifiable executables and supported sensitive operations require fresh approval and the relevant categories. Password/account/security changes themselves are owner-completed in Windows or unsupported; opening a page never claims a change was made. CRITICAL decisions are blocked through the ordinary authorization callback. Formatting, bulk permanent deletion, disabling security and arbitrary script tools are not registered operations.

Executable trust checks include valid target/PE, fixed OS identity or approved installation location, original executable identity, native offline Windows signature trust and manifest risk. Location alone is insufficient. Known renamed script hosts/interpreters are rejected. Unknown or unsigned/unverifiable executables retain review. Code signing is not a malware guarantee or permission for an application's later privileged actions.

The existing optional “Also confirm low-risk actions” preference is preserved and still intentionally adds prompts; the dialog explains that choice. There is no new persistent trust or allow-all option. Authorization decisions, category requirements and Windows privilege/access results remain distinct. Windows may deny an operation independently; no elevation bypass was added.

All manual, local chat, voice, shortcut and saved-workflow actions resolve through Engine and/or ToolExecutor. AI plans validate tool schemas and every step; arbitrary shell text is not a tool. Nested saved workflows remain rejected. Category revocation is checked again at execution. Cancel/expiry checks precede dispatch and queued delivery; AI approval expiry now sets cancellation explicitly. Sensitive workflow denial stops following steps while retaining earlier completed effects.

Radio requests require a single explicit requested kind/state. Voice recognition alone cannot change a radio: the transcript must be reviewed/sent; unreviewed voice workflows cannot hide a radio step. Detected standard RDP radio-off requests are blocked with a disconnect explanation. The fixed WinRT bridge accepts only validated enums, checks a named cancellation event before submissions, respects Windows access and verifies readback. A Windows request already submitted before cancellation may have taken effect; NEXIS reports that limit honestly.

Approval dialogs show action, resolved resource, effect, risk, capability, reason, reversibility and decline consequences, with Approve/Deny and Deny as the default. Delegated wrappers ask once. See the [engineering guide](ASCENSION_FREEDOM_GUIDE.md) for the detailed policy matrix and API references.

## 4. Themes implemented

OG Blood Red remains the new-install default and preserves the red/black/gold HUD and reactor identity. Midnight Black uses neutral charcoal; Arctic White uses light surfaces and dark text; Cyber Blue uses electric blue/navy; Matrix Green uses green/dark surfaces; Custom provides primary, background, accent and text controls.

Semantic tokens now drive QSS, Qt palettes, painted HUD/navigation/charts/reactors, floating orb, menus and NEXIS dialogs. Custom colors use strict six-digit hexadecimal inputs and color pickers. Text contrast must reach 4.5:1 against derived surfaces; accent/status colors and button text are adjusted for readability. Focus, selected, warning, success and error cues remain visible. The custom picker is a themed Qt dialog. Original branding images remain intact.

Live previews do not persist until Save. Revert restores saved appearance; Reset previews OG for explicit Save. General preference saves retain an unsaved appearance preview. Reduced Motion stops existing animation timers; theme changes add no background loop. Static textures invalidate on actual palette changes, and semantic painter colors are cached. Palette changes temporarily clear the Qt stylesheet while repaints are suspended, avoiding recursive repolishing.

## 5. Persistence and migration

The existing SQLite settings system remains schema version 4. New defaults are additive; legacy `dark` maps to OG and `light` to Arctic without rewriting unrelated settings. Missing/corrupt custom values fall back safely. Theme and custom colors save atomically. Tests reopen databases, preserve legacy resources/preferences, reject invalid values and verify independent diagnostics reads without profile writes. Credentials remain in the existing DPAPI system. Independent voice diagnostics reads saved appearance at startup; a separate process does not receive unsaved live previews.

## 6. Files modified

The implementation commit modifies these 52 files. This engineering report is the additional report-only file.

- `CHANGELOG.md`
- `NEXIS.spec`
- `README.md`
- `assets/RELEASE_CHANNEL.txt`
- `docs/ASCENSION_DEVELOPMENT.md`
- `docs/ASCENSION_FREEDOM_GUIDE.md`
- `docs/ASCENSION_HANDOFF.md`
- `docs/ASCENSION_OWNER_CHECKLIST.md`
- `pyproject.toml`
- `scripts/build_development_candidate.py`
- `scripts/candidate_evidence.py`
- `scripts/version.txt`
- `src/nexis/__init__.py`
- `src/nexis/core/commands.py`
- `src/nexis/core/intents.py`
- `src/nexis/core/launch_policy.py`
- `src/nexis/core/operator.py`
- `src/nexis/core/parser.py`
- `src/nexis/core/permissions.py`
- `src/nexis/core/results.py`
- `src/nexis/core/router.py`
- `src/nexis/core/themes.py`
- `src/nexis/core/tools.py`
- `src/nexis/diagnostics.py`
- `src/nexis/platform/radios.py`
- `src/nexis/platform/trust.py`
- `src/nexis/platform/windows.py`
- `src/nexis/storage/database.py`
- `src/nexis/storage/repository.py`
- `src/nexis/ui/appearance.py`
- `src/nexis/ui/command_deck.py`
- `src/nexis/ui/conversation.py`
- `src/nexis/ui/dialogs.py`
- `src/nexis/ui/hud_widgets.py`
- `src/nexis/ui/main_window.py`
- `src/nexis/ui/orb.py`
- `src/nexis/ui/reactor.py`
- `src/nexis/ui/settings_page.py`
- `src/nexis/ui/setup_services.py`
- `src/nexis/ui/theme.qss`
- `src/nexis/ui/themes.py`
- `src/nexis/ui/voice_diagnostics.py`
- `src/nexis/ui/workers.py`
- `tests/integration/test_storage_router.py`
- `tests/security/test_freedom_policy.py`
- `tests/ui/test_freedom_appearance.py`
- `tests/ui/test_window.py`
- `tests/unit/test_freedom_themes.py`
- `tests/unit/test_installer_permissions.py`
- `tests/unit/test_public_setup.py`
- `tests/unit/test_radio_bridge.py`
- `tests/unit/test_website_launcher.py`

## 7. Tests added

Four new regression files cover themes/contrast/legacy settings/atomic saves, shared authorization and bypass attempts, the actual radio bridge's response/cancellation paths with a fake helper, and running appearance/HUD/orb switching. Parameterized cases add 79 tests over the verified 1.3.5 suite. Existing assertions were changed only where the new policy or six-choice appearance UI intentionally changes the contract; new independent checks verify valid URLs are automatic and dangerous schemes/scripts/paths stay blocked.

Coverage includes websites across Engine/tools/shortcuts/workflows, ordinary built-ins, system tools, sensitive account/password/security page approval, destructive/unsupported tools, renamed script hosts, exact radio intent, voice review, RDP denial, unsupported/denied/disabled/malformed radio results, cancellation while the helper waits, late approval expiry, approved files/folders and workflow denial. Existing regressions retain missing apps, browser failures/no fallback, invalid paths, shutdown, Hard Mute, worker results, provider fixtures and permission revocation.

## 8. Test results

| Run | Passed | Skipped | Process seconds |
| --- | ---: | ---: | ---: |
| 1 | 538 | 1 | 204.55 |
| 2 | 538 | 1 | 237.22 |
| 3 | 538 | 1 | 174.52 |
| 4 | 538 | 1 | 145.50 |
| 5 | 538 | 1 | 206.72 |

Each final run uses a new process and fresh temporary test state against the same fingerprint. The single skip is `tests/security/test_policy.py:96`: creating a Windows symlink requires developer mode or privilege. Junction/path-boundary regressions still run. No elevation or developer-mode change was made just to remove the skip.

Ruff static checks and Git whitespace checks passed. A staged-blob privacy scan reviewed 267 files / 5,855,049 bytes, found no private-file/credential findings and recognized four reviewed dummy URL fixtures. It is a heuristic supplement to review, not a proof of secret absence.

Earlier evidence is retained: the initial check observed 459 passed/1 skipped; an exploratory run was interrupted while investigating expensive global Qt repolishing; the diagnostic HUD run passed 17 tests in 112.92 seconds with a slow-call trace. An expanded full run produced 516 passed, 2 failed, 1 skipped in 193.08 seconds: both failures were legacy assertions requiring unknown-site approval. New safety/automatic-action tests established the intended behavior before those assertions were corrected. Later focused checks passed, including 159 tests in 47.23 seconds, 123 policy checks in 8.61 seconds and five radio bridge tests in 0.26 seconds. Only the final frozen sequence qualifies this candidate.

The exact frozen source passed PyInstaller (326.72 s), native frozen offline smoke (30.69 s), Inno Setup compilation (233.30 s), portable ZIP CRC/identity, clean-environment extracted portable startup (31.56 s), current-host per-user upgrade (55.25 s), and installed isolated offline startup (28.47 s). All 1,062 installed payload files matched the candidate. Native bundle audit checked 1,004 PE imports, with zero missing dependencies, missing required modules or private files, and 14 verified model files. Seven new/shared permission/theme/radio/trust modules were independently found in the executable's embedded archive.

Frozen, extracted and installed smoke checks exercised all six themes, isolated theme persistence, native signature/identity backends, model load and the official SDK fixture. Python socket attempts were zero. These fixtures do not establish live provider inference or microphone/speaker operation. The build host used OpenSSL 3.5.8; the actual frozen runtime reported OpenSSL 3.6.4. The interpreter's public TLS distrust-policy resource was preserved byte-for-byte; verification was not disabled. Both application and installer remain NotSigned.

## 9. Security checks

No universal grant, generic terminal tool, arbitrary script input, shell=True call, credential automation, disabled TLS validation or elevation bypass was added. URL normalization/scheme rejection, explicit browser identity and no-fallback behavior remain enforced. Launch reporting distinguishes accepted requests from loaded pages. File inspection/search stays within approved roots; ordinary document suffixes and path/reparse checks precede automatic opening. Protected data paths stay excluded. Unknown executable identity and original-name interpreter checks prevent common alias/rename bypasses.

The radio helper is fixed code, not model/user script execution; it receives only validated enum substitutions and a generated event name. Native cancellation and readback failures are tested. Windows access denial is not turned into success. Native signature verification forbids network certificate retrieval and follows local Windows trust policy. Provider credentials are never printed or included in reports. All 2,193 protected hashes matched the pre-change snapshot, including owner NEXIS database/DPAPI files, the desktop launch collection and original 1.3.4/verified 1.3.5 artifacts. The previous installed 1.3.5 payload was preserved before the 1.3.6 upgrade. No private credentials were copied into distributables or reports.

## 10. Native Windows verification

The existing Windows 10 build 19045 x64 / i3-6100U / 8 GB host was used, not a clean OS. Native Known Folder validation passed for Downloads, Documents and Desktop; actual system-information and PC Health metadata queries returned. Native WinVerifyTrust accepted Edge and Task Manager signature checks; fixed ordinary Windows targets retain LOW classification. Copied/catalog-signed or otherwise unverifiable third-party executables can conservatively retain review.

Both native Wi-Fi and Bluetooth APIs reported Allowed and read back on after requesting on while already on. No off/on cycle, reconnection or paired-device recovery was tested. Detected RDP blocking was tested with a simulated remote-state result, not a live RDP disconnect. Third-party remote-control detection is not comprehensive.

Native Qt Windows rendering produced 24 main-window images plus six orb and six permission-dialog images across all themes, at requested 820x600 and 1366x768 sizes. The physical host reported DPR 1.5; the larger native window was constrained to 1283x700 by available desktop space. Native images of the built-in palettes, floating orb and custom controls were inspected for legibility and scroll access. Offscreen Qt renders at scale 1.0 and 1.5 added 48 main-window and 24 orb/dialog images; these are emulated DPI checks, not physical 100%/150% monitor qualification. Actual Engine execution then launched a blank Notepad, observed its own new window, and closed only that blank instance. Explicit Edge launch of one public example.com tab was accepted with browser_process_started=true and loaded_page_verified=false. Native system readouts and both already-on radio requests also passed through the exact frozen-source Engine without an approval callback. That check used isolated NEXIS settings, not the owner's profile.

Windows-owned Settings/consent/native file dialogs follow Windows appearance. Browser process acceptance does not verify page loading. Physical microphone capture, audible speaker output, live provider inference and clean-install licensing checks remain separate and unqualified for this revision.

## 11. Performance impact

A serial matched comparison imported preserved 1.3.5 source and frozen 1.3.6 source in separate fresh native Qt processes. Both used the same runtime, 1283x700 logical window, DPR 1.5, requested animation settings, 1.5-second warmups and 5-second samples. Notification eligibility was held at accepts-notifications (5) to compare a visible orb. This is a controlled UI benchmark, not verification of fullscreen/lock notification policy. Codex, browser and Windows background work remained active.

| Mode | 1.3.5 CPU % of one logical core | 1.3.6 CPU % of one logical core | 1.3.5 / 1.3.6 working set MB |
| --- | ---: | ---: | ---: |
| Idle | 14.93 | 12.45 | 109.64 / 103.90 |
| Active animation | 53.44 | 53.46 | 109.88 / 103.96 |
| Reduced motion | 0.94 | 0.31 | 109.88 / 104.00 |
| Minimized | 0.31 | 0.00 | 103.91 / 104.54 |
| Visible orb standby | 2.82 | 3.13 | 106.39 / 107.95 |
| Visible orb reduced | 0.62 | 0.00 | 106.41 / 108.02 |

Active reactor paint rates were 30.20 / 30.21 events per second; idle was 7.56 / 7.37. Reduced main-reactor animation produced zero paint events; occasional reduced orb paints are state/status refreshes. This shows no meaningful active-animation CPU regression in this observation; it is not a statistically controlled performance guarantee. First event excluding imports measured 2.701 / 1.660 seconds; OS/cache/order variation prevents claiming a general startup improvement.

Earlier 3-second samples were noisy (including 14.05–19.76 idle and 53.09–54.19 active in 1.3.6). One early orb sample ended with the orb suppressed by OS notification eligibility; it was excluded from visible-orb comparisons. All raw reports are retained. Separate model-load/no-capture probes observed about 236–237 MB and 2.24–3.15-second initialization; those are not voice-enabled or AI-active workload benchmarks. Physical audio, provider latency and radio helper transient CPU/memory were not profiled. No radio helper runs at idle.

## 12. Remaining bugs

No confirmed new permission bypass or theme-persistence failure remains in the final passing suite. This does not establish absence of defects. The known real-world verification gaps below remain release blockers. Extremely long permission previews, assistive-technology behavior and multi-monitor scaling have not been qualified by physical tester sessions.

## 13. Known limitations

Only single explicit radio requests are accepted by the AI-facing radio operation; ambiguous/compound inferred radio changes fail closed. Unsupported/OS-denied hardware cannot be overridden. An already-submitted OS action cannot be recalled by cancelling later. Third-party remote sessions are not reliably detectable. Native radio off/on and peripheral recovery remain untested.

Unsigned/unverifiable applications, including some catalog-signed third-party targets, may still need fresh review. Nonstandard installations outside the configured trusted location list remain conservative; browser targets there can be refused instead of falling back. Opening an app does not let NEXIS automate that app's privileged actions. Outside applications and web content have their own security behavior; signature verification is not a malware scanner. Unsupported extensions and link/reparse paths stay rejected; file contents/search require approved roots.

Separate diagnostics does not live-sync an unsaved preview. Native OS dialogs use OS styling. Rendered DPI checks do not certify physical multi-monitor/device behavior. Real wake-word, Hindi/Hinglish, microphone/speaker and long-running voice/AI workloads have not been qualified here. The prior 1.3.5 live provider check returned AUTHENTICATION failure; no live paid/provider call was repeated for 1.3.6 and no claim of a working live provider is made. The historical USB archive was previously reported incomplete; this mission did not change or requalify it.

## 14. Development-candidate status

Engineering build 1.3.6 is built, locally installed and verified as a development candidate. The source stayed frozen throughout the five regressions, build and subsequent checks. Installer/portable outputs are in `dist/freedom-1.3.6`; evidence is retained locally under `.verification-freedom-20261024`. The candidate is unsigned and unpublished. The installed Start Menu application now points to 1.3.6; owner NEXIS profile hashes are unchanged.

| Local artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `payload/NEXIS/NEXIS.exe` | 10237909 | `b33e69e5b74747ae753e72f1d5c0d90df77888d638ed36c4b5b6ff71b5fababc` |
| `NEXIS-Desktop-1.3.6.0-Setup.exe` | 101582683 | `cae52419d9dd1ee86e81eca8f6b9a752c172e4fa5d76750969faedef2faf5eda` |
| `NEXIS-Desktop-1.3.6-Windows-x64-Portable.zip` | 130523666 | `6130a3488b10a7258fcb74eb1640465d3ba203ff45e3199fbc96a574530003b9` |

The original 1.3.4 and verified 1.3.5 artifacts remain preserved. The root legacy launcher still points to the preserved original distribution; use the newly verified installed application or the explicit 1.3.6 payload to test this revision. No public-release readiness is claimed.

## 15. Release blockers / owner gates

- Resolve application distribution licensing and complete third-party compliance review; only ASH decides publication.
- Complete real microphone capture, audible speaker playback and voice end-to-end reliability, including any advertised language/wake behavior.
- Resolve the prior live-provider authentication gate and perform authorized live provider/reliability checks; fixtures are insufficient.
- Qualify clean Windows 10/11 install, upgrade and uninstall without workspace dependencies; current-host upgrade is not a clean-OS test.
- Qualify radio off/on, reconnection, unsupported hardware, Bluetooth peripherals and real remote-session behavior on tester hardware.
- Complete physical keyboard/accessibility, multi-monitor/DPI and longer-running resource/reliability checks; unsigned artifact/SmartScreen distribution handling remains for ASH's review.

The source/build is a new development candidate requiring owner/tester review. It is not approved for public release.
