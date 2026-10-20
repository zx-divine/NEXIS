# NEXIS installer and permission overhaul

Historical 1.3.2 design/evidence below. For the final local 1.3.3 candidate and remaining gates, see [GOD_MODE_HANDOFF.md](GOD_MODE_HANDOFF.md), milestone F.

Work continued on 19 October 2026. Local engineering build; real hardware and clean-machine qualification are still required.

## Proven causes

The prior PyInstaller spec explicitly excluded speech models. The runtime could find bundled models, but no model was packaged, so a fresh installation required a separate download. Dependency imports alone did not catch this. The old smoke check did not load a packaged model.

Discovered applications were always assigned MEDIUM risk, even for ordinary installed executables. The AI wrapper could also prompt before invoking the manual Engine, which prompted again. The optional low-risk confirmation setting was false in the checked configuration; the hardcoded risk classification caused the prompts.

## Changes

- Include the exact existing vosk-model-small-en-us-0.15 model: 14 verified files, 70,898,967 bytes unpacked; official archive 41,205,931 bytes. Apache-2.0, with upstream README, full license and distribution notice. Archive SHA-256: 30f26242c4eb449f948e42cb302dd7a686cb29a3423a8367f99ff41780942498. Model hashes match the prior checksum-verified official download; these local hashes are not a separate publisher signature.
- Build preflight fails on missing/altered/unexpected model files. A fresh source build can explicitly download from the pinned official HTTPS source. Installers do not depend on a developer Desktop folder.
- A native PCM check proved the default model rejects 8 kHz. Capture now negotiates a compatible rate before opening the stream (16 kHz for that case), preserves explicitly compatible custom models, and fails clearly before capture if the input only supports incompatible rates. Native 16/44.1/48 kHz decoder checks use synthetic silence, not real speech evidence.
- Automatically select an included compatible model in wizard, settings and voice startup; retain consented repair provisioning. Structural readiness rejects incomplete model directories; packaged checks must load actual Vosk weights.
- Keep low risk for explicit ordinary installed-app launches in recognized installation locations, with valid PE targets and no elevation manifest. Other executable paths remain reviewed. Installer/updater/system/elevation cases cannot inherit this allowance. Existing app capability grants and revocation checks still apply.
- Remove duplicate wrapper/Engine confirmation while preserving the same Engine checks. Unknown domains, file changes, sensitive settings, deletion and protected steps keep review. Opening the installation directory retains fresh review because its target may be outside approved folders. Arbitrary shell execution and security bypasses remain unsupported.
- Preserve per-user Inno installation and unelevated executable manifests. Qt 6.12 requires Windows 10 1809+, so the installer now states that minimum.
- Bundle native audio/Qt/provider dependencies, official artwork, QSS, Python/third-party notices and embedded SQLite schema/migration code. User databases, provider keys, recordings and developer runtimes are not distributed. Writable settings remain in Qt's per-user AppLocalData directory.

No always-on wake-word implementation is present or enabled; no wake-word model is needed or bundled. Voice starts only from an explicit Talk/Record action. Start/stop/cancellation state tests are not physical wake-word tests.

## Security prompts

NEXIS prompts review application actions; the first-run disclosure/capability choices are separate from Windows security. Windows UAC controls elevation; this per-user installer requests no administrator privileges. SmartScreen reputation warnings are different again and may occur for an unsigned or unfamiliar installer. Signing requires an owner-controlled trusted Authenticode certificate/service; a signature does not guarantee immediate reputation. No certificate, Windows setting, antivirus policy, UAC policy or SmartScreen protection was changed. No bypass is implemented.

## Verification checkpoint

Baseline: 234 passed, 1 symlink-privilege skip. Current full suite: 249 passed, 1 skip; Ruff passes. Tests include launch repetition/revocation, retained installer approval, duplicate-confirmation prevention, fake PE rejection, model integrity and missing-file preflight, plus existing audio/provider/security/race suites. Controlled fixtures are not real microphone or audible-output evidence.

Final PyInstaller build, offline executable startup, 999-reference native import audit, Inno compiler, per-user installation and fresh portable extraction/startup all passed on the current Windows host. The compiled installation-directory review policy was inspected directly. All 14 bundled model files passed integrity checks and native model loading in executable, installed and portable variants. The installed test found 105 applications and two SAPI voices; it did not launch those applications or record audio. Existing user database and encrypted provider file hashes remained unchanged. Both shortcuts have the correct target, icon and NEXIS.Desktop AppUserModelID. The native Crimson HUD screenshot was reviewed. All 12 pages, seven icon sizes and bundled provider SDK fixture checks passed. Python was removed from the test process PATH; a Python socket block produced zero attempted connections in the offline executable smoke. This is not a physically disconnected clean-machine test.

A separate Windows SAPI synthesis-to-file check produced nonempty PCM and completed successfully. The temporary WAV was removed without playback. This does not prove audible speaker output.

Local artifacts: installer 101,413,951 bytes; portable ZIP 130,186,428 bytes. Complete local hashes and evidence are in ignored docs/installer-overhaul. No installers or model weights are uploaded with source. The first stale intermediate build was rejected and preserved; the delivered executable includes the final policy and sample-rate fixes. Real microphone capture, meaningful fresh speech, audible playback, physical device switching and a clean Windows environment without Python remain NOT VERIFIED. Historical provider HTTP 503 is not claimed repaired by packaging.

## References

- https://alphacephei.com/vosk/models — publisher model compatibility/license table
- https://doc.qt.io/qt-6.12/windows.html — Windows runtime baseline
- https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation — signing/reputation distinction

No installer or GitHub Release may be published without explicit owner approval.
