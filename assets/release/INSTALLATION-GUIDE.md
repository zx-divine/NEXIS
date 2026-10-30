# Installation and safe personal testing

Target: Windows 10 x64 build 19045 or newer, or Windows 11 x64. The current host
is Windows 10; consult the verification report for tests actually performed.

## Before opening this candidate

1. Read the candidate notice and limitations. Compare the installer/ZIP hashes
   with `SHA256SUMS.txt`. These hashes detect changes; they are not a publisher
   signature or malware certification.
2. Preserve the existing application, profile and backups. With NEXIS fully closed,
   copy the complete private data directory to a new private backup if needed.
   Do not copy only the main file of an active SQLite database. Never delete the
   original profile or modify the USB archive for this test.
3. Normal installed and portable launches use the current Windows account's
   NEXIS profile, normally `%LOCALAPPDATA%\NEXIS\NEXIS Desktop`. Existing setup and
   credentials are retained. A genuinely new Windows user starts clean onboarding.
4. This candidate adds database schema 5. Earlier builds may refuse that profile;
   a schema downgrade is unsupported. For independent first-run testing, use a
   separate Windows test account or the isolated smoke command below.

## Installer

Run `Nexis v1 Setup.exe`. Read the development-candidate notice, review the chosen
directory and choose whether to create a desktop shortcut. Installation is
per-user and does not permanently elevate NEXIS. The stable normal program
directory is `%LOCALAPPDATA%\Programs\NEXIS Desktop`; installing there can replace
an earlier program payload. The Start Menu/optional desktop shortcut is named Nexis v1. The uninstaller is provided.
Application data is stored separately from installed program files. Do not remove
that data manually when uninstalling. Upgrade/uninstall qualification is listed
separately in the manual checklist; it is not implied by a successful compilation.

## Uninstall or repair

Exit NEXIS completely, including its tray icon. Reopen `Nexis v1 Setup.exe`, click
Next, and select **Uninstall NEXIS**. Review the program path and confirm, then
follow the Windows uninstaller. Cancel keeps the app installed. Uninstall removes
installed program files/shortcuts and keeps the separate personal profile.

The same screen offers **Install / Repair NEXIS** when a usable installation is
detected, or **Install NEXIS** on a new account. Uninstall is disabled for an
uninstalled/portable copy or an unusable registration. For a damaged/older/all-users
installation, use **Windows Settings > Apps > Nexis v1 (or the older NEXIS entry) > Uninstall**. A download alone
is not an installation. Setup never performs a personal-data purge.

## Portable

Extract the complete ZIP to a writable local folder, then open `NEXIS/NEXIS.exe`.
Do not launch from inside the ZIP or move only the EXE. Portable means no installer
is required; the account profile still lives in LocalAppData. No development path,
Python installation or terminal is required for ordinary use.

## Optional isolated offline self-check

From a terminal you choose to open, run the extracted application with a new
output directory, for example:

```text
NEXIS.exe --smoke-test "C:\NexisTestEvidence-New" --offline-smoke
```

This developer diagnostic uses disposable synthetic data, loads/checks the bundled
decoder, exercises the actual UI/storage and writes results/screenshots. It does
not open the normal profile, record the microphone or certify real voice accuracy.
Choose a new output directory. The self-check must finish and report `ok: true`;
the mere presence of an EXE does not prove success.

If Windows denies an operation, respect that decision and review the actual cause.
Do not disable security software or bypass authentication to run a test. If voice
is unavailable, Chat and permitted Manual tools remain available.
