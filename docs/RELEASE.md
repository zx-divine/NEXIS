# Windows build and release qualification — 1.3.2

1. Use Windows x64 and an isolated Python environment. This build was verified with Python 3.12.14; the source declares Python 3.11–3.13.
2. Install requirements-dev.txt and install the project editable. No Node.js or separate server is required.
3. Run python scripts/build.py. It prepares the pinned official model, runs tests and Ruff, then builds NEXIS.spec. The development build may download the documented 41.2 MB model; installed users do not need to download it.
4. Compile installer/NEXIS.iss with Inno Setup. The installer is per-user and targets Windows 10 1809+ or Windows 11 x64. Preserve previous distributions before rebuilding.
5. Verify the executable, local installation and extracted portable ZIP. The supplied QA scripts run only when explicitly invoked; scripts/verify_complete_package.py also installs the local build and must only be used for an authorized installation test.
6. Test on a clean supported Windows machine without Python. Verify real microphone speech, configured AI inference, audible TTS, cancellation, restart, missing devices, read-only installation paths and display scaling. Current-host automated startup is not clean-machine qualification.
7. Review licenses and dependency advisories. Sign with an owner-controlled Authenticode certificate/service when available. Record artifact hashes. Never disable SmartScreen or UAC to avoid warnings.

The one-folder bundle contains the exact vosk-model-small-en-us-0.15 model, mandatory Vosk/PortAudio runtimes, applicable Qt plugins, provider adapters, branding, QSS and notices. The spec validates the model manifest before building. Model weights are intentionally excluded from Git and reproduced from the pinned official archive. User databases, credentials, recordings and developer dependencies must never be distributed. See INSTALLER_PERMISSION_OVERHAUL.md for sources, hashes, policy and verification limits.

Windows SAPI uses installed Windows voices through bundled COM bindings; Windows voices and drivers are operating-system components. There is no enabled always-on wake-word subsystem. No speech synthesis API return value proves audibility.

## Isolated packaged smoke check

Run NEXIS.exe --smoke-test OUTPUT_DIRECTORY. It uses temporary application data, visits every page, verifies resources and loads the actual bundled Vosk model, then exits. --offline-smoke blocks Python socket connections during that check; it does not alter Windows networking. --capability-smoke inspects native device/voice availability without recording or speaking. Decoder checks use synthetic silence and never count as real speech recognition.

Qt 6.12 uses Windows ICU. Preserve the spec's exclusion of unrelated development ICU DLLs and its Qt WebEngine exclusions. If OneDrive/ACLs prevent replacing an old build, preserve it and use a fresh output folder; do not change user ACLs automatically.

The source push is owner-authorized. Installer upload, GitHub Release publication and deployment still require separate approval. See the local ignored docs/installer-overhaul directory for machine-specific verification evidence.
