# NEXIS Desktop 1.3.3 — Crimson Command

NEXIS combines online AI conversation, explicit microphone control and permission-controlled Windows tools in the existing Crimson Command HUD. This local build is under verification; it is not a qualified public release.

## Install and set up

1. Run the Windows installer from dist/installer, or extract the complete portable ZIP and open NEXIS.exe. Keep the adjacent _internal folder. End users do not need Python or a terminal.
2. Read **NEXIS — SYSTEM ACCESS & CONTROL** and choose capabilities. No capability is granted by default. For voice conversation, enable microphone access and network-dependent actions; approve other capabilities only when needed. Review/revoke these choices in Settings.
3. Open **AI Providers**. Existing Windows-protected credentials are loaded without revealing or requesting the key again. Add/edit a provider, refresh its available models, and test real inference. Use **Save & use as default** to select it explicitly.
4. The complete installer includes the verified English (US) Vosk model. Setup selects it automatically without a download or manual path. Settings retains consented one-click provisioning as a repair/source-checkout option.
5. Open **Voice Chat**, press **Talk**, wait for the visible listening indicator and speak. Stop and transcribe finishes the turn; cancellation discards pending capture. The transcript goes to the selected provider and its completed reply is spoken with Windows TTS. Retry retains the transcript without recording again.

No microphone recording starts on launch or because of an internet/provider check. Default Windows input/output devices are used; microphone and voice selectors are available in Settings. A missing provider or failed request does not disable recording, transcription or reading an available response aloud.

## Providers

- **OmniRoute**: supported root or /v1 base addresses. Open its dashboard from AI Providers when upstream accounts/models need configuration.
- **Google Gemini**: official google-genai SDK, runtime model discovery, manual model IDs, streaming and manually validated function calls. Supply your own API key. Availability does not mean free usage; quotas and pricing depend on the account/model.
- **OpenRouter**, **OpenAI-compatible**, **Custom API Gateway**, and compatible saved profiles: configurable base URL, API paths, authentication/header placement, timeout and streaming in Advanced options.

Only implemented protocols are accepted: native Gemini or OpenAI-compatible chat completions. NEXIS never silently changes providers, sends a retry to another account, or installs an AI server. Previously saved connections remain readable; local-LLM onboarding and automatic server discovery have been removed.

Authentication, DNS, TLS, timeout, connection, rate-limit, model/endpoint, server and empty-response errors are reported separately. Requests go directly to the selected provider; there is no ping gate or cached offline mode.

## Windows actions

The **PC Health** page provides an on-demand, read-only local snapshot without administrator access or internet probes. Unsupported temperatures and inaccessible process data are shown as unavailable. **Local Memory** stores only notes you approve; `remember this: ...` drafts a note for review, while `forget this: ...` searches for a note you can confirm deleting. Memory is not automatically added to AI requests. Keep notes and private plaintext exports free of secrets.

**Files** searches approved folders with optional extension, byte-size and UTC modification-date filters. Use `*` to filter all filenames. Optional local text indexing needs separate approval and supports bounded UTF-8 `.txt`/`.md` documents only; it does not parse PDF/Office files, execute contents or upload documents. Changed or unapproved files are excluded. Delete the index to remove cached text; private backups may retain older copies.

The online planner produces validated tool calls or structured plans. Application discovery, websites, visible-window management, approved-folder file operations, Windows settings navigation, volume/mute, clipboard writes and saved workflows use a typed tool registry. Multi-step requests are bounded and stop on failure or cancellation.

Manual commands remain available in the command drawer. They are explicit OS tools, not an offline AI interpreter or fallback. Chat and voice use the selected online provider.

Files must stay in approved locations. Existing destinations are never silently overwritten. File deletion uses the Recycle Bin after fresh approval; recursive/permanent deletion is not supported. Scripts, arbitrary terminal execution, security bypasses and elevation are unavailable. PIN/password/Hello/recovery operations hand off to Windows; NEXIS does not collect or enter protected credentials.

Ordinary websites open in the default browser. Advanced existing-tab focus/close/navigation requires an explicitly configured, already-running loopback Chromium adapter. NEXIS does not enable debugging or alter browser security. Purchases, messages, account changes and form submissions are not implemented as automatic tools.

## Verification and current blockers

**Desktop Companion** optionally enables the floating reactor and Windows tray controls. It is off by default, respects reduced motion and Windows' reported busy/fullscreen state, and never records merely by appearing. Talk opens visible Voice Chat. **Updates** checks only the official repository; optional automatic checks are daily and off by default. Downloads need explicit approval, and NEXIS never runs an installer. Compare a selected downloaded file's SHA-256 where metadata is supplied; this alone does not authenticate the publisher.

**Workflows → Workflow Studio** optionally drafts a routine from your description. Review/edit the commands, use Dry-run validation, save, and use the existing Run control explicitly. Pause/resume/stop are in the Manual Command Deck; pause waits for the next step boundary. The experimental AI drafting flag is off by default.

**Screen Awareness** is also off by default. Grant its separate capability in Settings, enable the feature, click Capture preview, and inspect it before approving a request to the disclosed provider. Vision support depends on your configured model. No image is sent automatically, no tool executes from its explanation, and cancellation cannot recall an already-approved transmission. Adapter formats follow [Google's image-input documentation](https://ai.google.dev/gemini-api/docs/generate-content/image-understanding) and [OpenAI-compatible image messages](https://developers.openai.com/api/docs/guides/images-vision); no model name or free-tier availability is assumed.

See **docs/GOD_MODE_HANDOFF.md** for the 1.3.3 checkpoint and **docs/INSTALLER_PERMISSION_OVERHAUL.md** for the installer and permission design. Machine-specific historical evidence remains local and is not part of this source repository.

Real provider inference depends on a working owner-configured provider and remains separately qualified. Three standalone speech cycles and five complete source/restart/executable/installer/portable voice cycles remain **PENDING USER VERIFICATION**. Windows 11, clean machines without Python, physical audio/hot-plug behavior and live taskbar grouping have not been certified. Automated fixtures never count as those real speech cycles.

Installer publication requires the owner’s explicit approval. Source improvements may be committed/pushed as authorized; credentials, personal data, recordings and local verification logs are excluded.


## Risk-based approvals

With the relevant capability enabled, explicit requests to open normal installed applications and curated/user-approved websites do not request confirmation on every launch. Verified installed paths and executable manifests determine risk; this is not a blanket executable trust rule. Untrusted/downloaded programs, installers, elevation-capable programs, unfamiliar domains, sensitive settings and destructive actions keep fresh review. Generic Windows system utilities do not inherit ordinary-app trust. Capabilities and approved folders remain revocable in Settings. The optional extra confirmation setting remains available and existing preferences are preserved.

## Build a complete Windows package

Use Python 3.12 x64 in an isolated environment, install requirements-dev.txt, and install this project with `pip install -e .`. Run `python scripts/build.py` to validate the official model, run tests/static checks and build the PyInstaller folder. The build explicitly prepares the approved 41.2 MB model if missing; no model is downloaded silently by the installed app. Direct spec builds require python scripts/prepare_model.py --download first. Model binaries are intentionally not stored in Git; the pinned manifest, official source URL and redistribution notices are included. Missing/altered model data stops the release build. Compile installer/NEXIS.iss with Inno Setup after building. Uploading an installer or publishing a Release remains a separate owner decision.

The supported NEXIS target is Windows 10 build 19045+ (x64), or Windows 11. Windows supplies SAPI voices, audio drivers and standard system fonts. The one-folder application bundles Python, Qt, native audio libraries and the default offline model. Always keep NEXIS.exe with its adjacent _internal folder.


The local 1.3.3 candidate is `dist/NEXIS/NEXIS.exe`; its installer is `dist/installer/NEXIS-Desktop-1.3.3.0-Setup.exe`, and its portable archive is `dist/NEXIS-Desktop-1.3.3-Windows-x64-Portable.zip`. These are local verification candidates, not a published release. The previous 1.3.2 distribution is retained separately. Run `python scripts/verify_five_rounds.py` for five serial regression processes with fresh temporary test state and an unchanged-source fingerprint. Local evidence is excluded from source publication.
