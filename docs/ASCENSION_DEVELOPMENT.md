# NEXIS continuation guide

This guide supports development without Codex. Read ARCHITECTURE.md, SECURITY.md and the Ascension handoff first. Keep the original 1.3.4 candidate and private user data separate from new builds. Do not touch the separate website repository or USB archive.

## Environment

Use **Python 3.12 x64** on Windows 10 build 19045+ or Windows 11 x64. Project metadata permits Python 3.11–3.13, but this candidate is qualified only with its recorded 3.12 runtime. Install Git and Inno Setup 6 from official sources; do not bypass Windows security prompts. Do not reuse an unrelated global environment for release builds.

From the repository root in PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe scripts/entry.py
```

`requirements-verified.txt` records the historical dependency set. Its setuptools 84.0.0 is affected by [GHSA-xmj3-9gf7-h52w](https://github.com/pypa/setuptools/security/advisories/GHSA-xmj3-9gf7-h52w); retain it as evidence, not a current security recommendation. New environments require setuptools 84.1.0+ via requirements-dev.txt and the build-system floor. Setuptools is excluded from the frozen app. The workspace build helper can use an isolated patched copy under `.tool-deps/setuptools-secure` without deleting historical environments. Runtime notices and the model manifest are tracked; downloaded models, environments and private evidence are ignored. No developer key is provided. End-user packages include Python and Qt.

The existing `scripts/dev.py` helper also adds private `.dev-deps` and `.provider-deps` directories when present. This convenience does not create those directories on a new machine. Recreate a normal venv using the commands above. Never delete an existing development environment as a troubleshooting shortcut.

## Directory and execution map

| Location | Responsibility |
|---|---|
| `src/nexis/main.py`, `scripts/entry.py` | Application entry, platform gate, data lock, startup/error handling |
| `ui/main_window.py` | HUD, navigation, conversation dispatch, cancellation/delivery, lifecycle |
| `ui/settings_page.py`, `ui/doctor_page.py` | Settings Hub and explicit diagnostic UI |
| `core/doctor.py` | Local checks and fixed-sentence provider diagnostic; redacted output |
| `core/provider_manager.py`, `core/providers.py` | DPAPI profiles, adapter requests, discovery, streaming, safe errors |
| `core/operator.py`, `core/tools.py`, `core/router.py` | Untrusted model plans, allowed schemas, permissions and manual commands |
| `core/websites.py`, `platform/website_launcher.py` | URL normalization, narrow natural command grammar, registered browser discovery |
| `core/voice.py`, `core/audio.py`, `core/recognition.py` | Explicit PortAudio capture, conditioning/VAD, offline decoding |
| `platform/speech.py`, `ui/microphone.py` | SAPI thread, output selection, calibration and preview |
| `storage/database.py`, `storage/memory.py`, `storage/document_index.py` | SQLite, explicit notes and bounded local text index |
| `platform/health.py`, `ui/screen_page.py`, `ui/workflow_studio.py` | Read-only health, capture consent and draft-only authoring |
| `ui/desktop_page.py`, `ui/orb.py` | Optional standby/tray/orb, placement and display policy |
| `tests/` | Unit, integration, security and Qt fixtures; hardware is separate |
| `NEXIS.spec`, `installer/NEXIS.iss`, `scripts/` | Bundle, installer, integrity/release tooling |

The UI dispatches long-running operations through QThreads. Never invoke HTTP, STT/model initialization or folder scans on the Qt GUI thread. Qt widgets stay on their owning thread. Workers own cancellation events; check them after approval and immediately before side effects. A submitted Windows call cannot be recalled. Never forcibly terminate a QThread holding SQLite, audio or COM resources.

## Voice resources

The default model is `vosk-model-small-en-us-0.15` (English US). Its upstream ZIP SHA-256 and 14 expanded file hashes are in `assets/models/manifest.json`; Apache-2.0 notices are included. Source models live under `assets/models/<model-id>`. Frozen models live under `_internal/nexis/assets/models/<model-id>`. User-managed models live under the application data directory's `models/` folder.

```powershell
.\.venv\Scripts\python.exe scripts/prepare_model.py --download
.\.venv\Scripts\python.exe scripts/verify_speech_model.py
```

Read the scripts' usage before running environment-specific verification. Model setup is an explicit developer download; the installed app never silently downloads it. A dependency import does not prove weights exist. The spec stops on missing/altered default weights. Windows SAPI engines/voices, audio devices and drivers are OS prerequisites and are **not bundled voice data**. No trained wake detector is included. Hindi/Hinglish speech recognition remains unqualified; provider language ability is separate.

Voice Studio: select input/output, calibrate two seconds of silence, test ordinary speech, inspect local transcription/noise/clipping, adjust sensitivity, then test audible output. Calibration settings are device-bound and do not replace unrelated preferences. Hard Mute cancels capture, pending actions and output; Wake never records by itself. Synthetic SAPI-to-file tests are engineering evidence only.

## AI configuration and errors

Open Settings → AI & Models → Manage providers. Enter your own endpoint/key, select the implemented Gemini or compatible protocol, discover models or enter an authorized manual model ID, then explicitly save/select the profile. Test inference independently of model listing. Groq/NVIDIA presets use their documented roots; account permissions, supported parameters, quotas and charges still apply. MCP endpoints are not chat-completions endpoints.

Keys/custom credential headers use Windows DPAPI for the current Windows account. Do not copy or print decrypted values. Do not put keys into command-line arguments, Git, snippets, memory or diagnostic reports. Profile switching never silently falls back to another account. Requests retain their original profile snapshot. Interrupted streams and generation POSTs are not automatically replayed. Respect bounded timeouts and cancellation.

## Data and recovery

The standard per-user location is `%LOCALAPPDATA%\NEXIS\NEXIS Desktop`; use Windows/Qt known-folder APIs rather than assuming a redirected Desktop path. The SQLite `nexis.db` and DPAPI profile files must never be packaged. Close NEXIS and all background jobs before backup/restore. Include any SQLite WAL/SHM consistently, or use SQLite's backup API while the database is live. Never copy only the main file of an active WAL database and assume it is complete.

Schema version **4** contains settings, shortcuts, snippets, workflows, history, app catalog/preferences, minimal tool audit, local memories and document index. Migrations are additive. New settings (`memory_enabled`, `minimize_to_tray`) use typed defaults when missing; they do not require destructive migration or a schema bump. A newer unsupported database version fails with an explanation. Corrupt databases are preserved; the application never silently replaces them. Unknown/invalid stored setting types fall back safely and Doctor reports them.

To restore: keep the failed/current data in a separate dated directory, verify backup hashes and SQLite integrity in a temporary restored copy, then restore under the same Windows account with NEXIS closed. DPAPI portability to another account/machine is not guaranteed; reconnect providers rather than bypassing encryption. Test the restored copy before discarding any original. USB healthy status alone does not prove a complete backup. Local export/deletion is user-controlled; ordinary SQLite deletion is not forensic erasure, and external backups remain outside the application's control.

Memory is never automatically inserted into cloud context. `remember`/`forget` requests are local draft/review actions and excluded from future conversation history. Memory OFF blocks saves/imports, preserves review/export/delete, and does not erase old notes. Indexing supports bounded UTF-8 txt/md only, remains inside approved folders and excludes stale/unapproved results.

## Security boundaries

All model tool output is an untrusted proposal validated against fixed schemas. Capability grants do not bypass sensitive-action review. Approval expires and cancellation/revocation are rechecked at dispatch. No arbitrary shell, elevation, credential entry or security bypass is available. Website launching uses argument arrays or Windows URL association, never a command processor. Unknown browser names require an eligible registered executable; registry command arguments are discarded.

Screen help requires explicit capture permission, feature opt-in, preview and destination approval. No tool capability is attached to pure image explanation; screenshots are untrusted content. Cancellation before sending prevents transmission; an already submitted image cannot be recalled. Doctor's local check does not capture audio/screen or contact providers; its separate network test sends one fixed sentence after confirmation and capability validation. Exports contain fixed explanations and numeric aggregates, excluding private paths, logs, device names, keys, memory and chat.

## Testing and builds

```powershell
.\.venv\Scripts\python.exe scripts/dev.py lint check src tests scripts
.\.venv\Scripts\python.exe scripts/dev.py test -q --tb=short -rs -p no:cacheprovider
.\.venv\Scripts\python.exe scripts/verify_five_rounds.py --output .verification-candidate-final
.\.venv\Scripts\python.exe scripts/build_development_candidate.py --verification .verification-candidate-final/results.json --output dist/ascension-1.3.5 --iscc 'C:\Program Files (x86)\Inno Setup 6\ISCC.exe'
```

Choose new output directories. The build refuses to overwrite existing candidates, requires five successful serial regressions of the same fingerprint, validates the actual bundled model, builds a one-folder executable and Inno installer, performs current-host frozen offline startup, creates a ZIP and SHA-256 manifest, and verifies source did not change. The optional `--workspace-runtime` flag uses existing private dependency directories; omit it for a standard venv. Its logs/evidence are local and must not be blindly staged.

`scripts/prepare_runtime_notices.py` regenerates runtime notices from installed distributions; review changes and licence completeness **before** freezing source. The build's passing smoke/ZIP CRC does not establish an independent install or extracted portable launch. Perform those separately, including clean Windows without Python, upgrade/data preservation and uninstall. Inspect Authenticode status; these development binaries are unsigned unless independently signed and verified. Do not label them signed or Stable.

```powershell
Get-FileHash dist/ascension-1.3.5/NEXIS-Desktop-1.3.5.0-Setup.exe -Algorithm SHA256
.\.venv\Scripts\python.exe scripts/audit_native_bundle.py --folder dist/ascension-1.3.5/payload/NEXIS --output .verification-native/native-bundle.json
```

The fingerprint covers runtime code, tests, scripts, spec, requirements, metadata, artwork, default model manifest, licences and bundled documentation. If any covered file changes, do not count old rounds as current. Preserve failed/interrupted logs. Mocked callbacks and offscreen/scaled rendering are not native browser, physical audio or actual display-DPI evidence.

## Debugging and safe contribution

Managed Python runtimes may add an interpreter-owned public TLS distrust resource beside `ssl.py`. The release spec conditionally includes that exact file via `scripts/runtime_ssl.py`, validates it contains no private key, and fingerprints its bytes. New Python/OpenSSL versions can change required resources even when application code is unchanged. The initial 1.3.5 package's SDK fixture caught a missing `codex-rejected-cas.pem`; a trace reproduced the failure in SSLContext creation, and including the unchanged public distrust file made the fixture pass. Never remove the policy code, disable certificate verification or ignore that smoke failure. A standard unmodified CPython build needs no extra file. The manifest records Python/OpenSSL versions and any such resource hash.

- Startup failure: check supported Windows build, keep `_internal` adjacent, inspect local logs/Doctor, preserve corrupt data, retry using the verified installer. Never delete data to make startup pass.
- No chat: inspect the selected provider/model/protocol, run one explicit test, distinguish auth/rate-limit/model/timeout/TLS errors. Do not silently change provider.
- No speech: use Voice Studio level/noise/clipping/device checks, verify model hashes and SAPI prerequisites, confirm actual speaker output. A device enumeration PASS is not an audio PASS.
- Browser missing: rescan installed registrations or explicitly choose Windows default. Do not download a browser automatically or execute saved command arguments.
- Shutdown slow: cancel all work, identify the running worker, preserve diagnostics. Native COM/audio initialization can be delayed by Windows; early cancellation checks cannot interrupt a native call already in progress.
- Files missing: review approved roots and filters, symlink/junction restrictions and scan limits. Do not broaden permissions silently.

Use a dedicated `codex/` development branch, review Git status before edits, keep commits logical, scan staged blobs with `scripts/audit_staged_source.py`, and never force-push or rewrite historical commits. Follow owner authorization before pushing a new branch. No binary publication, GitHub Release or website deployment is authorized by an engineering build. Keep a checkpoint with commit hash, source fingerprint, actual tests, package hashes, limitations and next task. The owner checklist and handoff define what remains.


Project Freedom continues this checkpoint as engineering build 1.3.6. See ASCENSION_FREEDOM_GUIDE.md for the new theme and authorization policy, and ASCENSION_FREEDOM_RESULTS.md for its separate verification evidence. The 1.3.5 artifacts and results remain historical; their passing checks do not qualify 1.3.6. All unresolved owner release gates still apply.
