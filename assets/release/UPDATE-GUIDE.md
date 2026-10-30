# NEXIS Windows update guide

## Using updates

Open Settings → General → Software Updates. New profiles enable automatic checks and downloads. Previously saved opt-outs remain off. Network access must be allowed in NEXIS permissions; changing update preferences does not grant it. Checks run after normal startup and at most once daily, with a lightweight timer checking whether a daily request is due. A failed attempt is also throttled. Check for Updates can be used at any time.

When a newer compatible build is found, NEXIS shows the current/new public versions and engineering builds, signed release notes and download size. Download Update shows percentage, bytes and speed. Interrupted downloads can be retried; partial data is discarded and the retry downloads a fresh copy. No partial package is executed. Remind Me Later postpones the notification for a day. A ready package can remain staged for a later session; signed metadata and package hashes are verified again before use.

Save unsaved chats, finish active work, then choose Restart & Install. NEXIS does not automatically interrupt voice, AI, file or command tasks. It copies the installed application to a separate helper directory and snapshots the profile before shutdown. The helper waits for the app's single-instance lock, verifies the package again while holding a Windows handle that denies writes/replacement, and runs fixed Inno Setup switches with the existing per-user install directory. It never uses runas, a shell or an administrator service. Portable/source copies cannot silently replace an installation.

Windows 10 build 19045+ / Windows 11 x64 remains the existing minimum. No binaries are installed on macOS or iPadOS by this adapter.

## Trust and version rules

The existing remote and GitHub repository API identify `https://github.com/zx-divine/NEXIS` (repository ID 1421538618) as the release source. TUF metadata is fetched from `https://github.com/zx-divine/NEXIS/releases/latest/download/`. HTTPS redirects are restricted to that repository's versioned release assets and `release-assets.githubusercontent.com`. URLs and local target names cannot be supplied through settings.

The bundled `nexis/assets/updates/root.json` is the initial trust anchor. Root metadata has a 2-of-3 Ed25519 threshold; targets, snapshot and timestamp use separate Ed25519 keys. python-tuf checks the signature chain, metadata versions, expiry, lengths and hashes. The fixed signed `NEXIS-Windows-x64.json` target identifies a stable release, compatible AppId, Windows x64, Inno per-user installer and schema 5. The EXE itself is a separately authenticated TUF target. A GitHub release body, GitHub digest or SHA256SUMS alone never authorizes installation.

Installable engineering builds must be strictly newer than the running build and no older than a previously observed build. Public versions must not decrease. Stable numeric semantic versions are required; prerelease/malformed versions are rejected. Public 1.1.0 uses engineering 1.4.2 because existing engineering versions had already reached 1.4.1. For example, public 1.1.1 should use engineering 1.4.3 or later.

TUF target signatures authenticate bytes through signed hashes; they are carried in `targets.json`, with the signed timestamp/snapshot chain, rather than a WinSparkle `.sig` or Electron `latest.yml`. NEXIS is Python/PySide6/PyInstaller with Inno Setup. The updater is the Python TUF reference client, not an Electron/Tauri updater or an abandoned PyUpdater client. Authenticode is additional Windows publisher identity and is not bypassed. If available, sign the application and Setup with the owner-controlled Authenticode certificate **before** generating TUF metadata. Never replace a signed target's bytes after generating metadata.

## Publisher workflow — local preparation only

Private signing keys are never bundled, committed or uploaded. Initial production keys were generated outside this checkout under the current Windows account's `%LOCALAPPDATA%\NEXIS-Release-Signing\windows-v1.1-20261030`. Each private key is encrypted with current-user Windows DPAPI. Only the public trust root belongs in source. Back up the signing environment using an owner-controlled secure procedure; DPAPI files alone are not portable to another account/machine. Separate root keys/offline storage and a dedicated signing machine are recommended before public operation. Loss of the required signing keys requires a separately trusted manual recovery installer; never enroll replacement keys from an unsigned feed.

Use the existing isolated Python build environment with the pinned requirements. Run the complete regression suite and Ruff. Build `NEXIS.spec`, compile `installer/NEXIS.iss` with the resulting bundle, then prepare a **new** output directory:

```powershell
python scripts/update_repository.py sign `
  --keys-dir "$env:LOCALAPPDATA\NEXIS-Release-Signing\windows-v1.1-20261030" `
  --installer "PATH\NEXIS-Desktop-1.4.2.0-Setup.exe" `
  --notes assets/release/UPDATE-RELEASE-NOTES.md `
  --build 1.4.2 --public 1.1.0 `
  --output "Release Nexis\NEXIS-1.1.0-build-1.4.2"
```

The output includes the correctly named Setup, signed `root.json`, every versioned `N.root.json`, `timestamp.json`, `snapshot.json`, `targets.json`, `NEXIS-Windows-x64.json`, notes, a summary manifest and SHA256SUMS. Metadata sequence numbers increase in the external signing directory and must never be reset or reused. Keep previous complete release directories. Do not copy QA trust roots or QA installers into production output.

After owner authorization, create a draft GitHub release tagged `v<public-version>` and attach the complete metadata/target set as **flat assets**. Include all historical versioned roots in every current release so old clients can traverse key rotations. Publish only after verifying the exact upload set. GitHub's “latest” release must be the supported stable Windows release. Uploading an arbitrary EXE or a ZIP without the TUF repository does not enable updates. A concurrent latest-release change may safely fail verification; users can retry.

Timestamp metadata expires after 14 days, snapshot after 30, targets after 90 and the initial root after two years. Refresh and re-sign metadata before expiry even if the installer stays unchanged; increment all metadata sequence numbers. Use the TUF documented root-rotation procedure with consecutive versions and signatures meeting both the old and new root thresholds. Distribute rotations before old root expiry. The initial tooling does not automate root rotation; rehearse it in isolation before use. Never change the bundled trust root to an unrelated key for an in-app update path.

No production uploads or pushes are performed by these tools. See RELEASE-VERIFICATION.md for evidence and remaining qualification limits.

## Data migrations and recovery

The organization/app names, AppId, install directory rules and `%LOCALAPPDATA%\NEXIS\NEXIS Desktop` profile location are unchanged. This release keeps schema 5 and adds settings defaults without replacing existing rows. Existing opt-outs, provider DPAPI files, saved model choices, voice settings, themes, orb settings, memories, conversations, grants, plugins/skills and adjacent files are retained. The installer has no profile deletion action. New schema versions must first ship a compatible migration/recovery design; this updater rejects descriptors advertising unsupported schemas. The database rejects a newer schema rather than resetting it.

Recovery records are under the profile's `updates` folder:

- `state.json`: phase, expected build, error, backup and previous application locations.
- `installer.log`: Inno's installation log; keep private as it contains local paths.
- `backups/<id>`: SQLite online backup checked with `PRAGMA quick_check`, plus adjacent profile files. Logs/locks and the update cache are excluded. Snapshot failures block installation.
- `runners/<id>`: the previous complete application bundle used as a helper and retained for recovery. These copies are deliberately retained; remove old recovery copies manually after confirming a successful update.

Offline, missing feeds, rate limits and server errors do not block launching NEXIS. Retry a check/download after connectivity is restored. For expired metadata, check the Windows clock and contact the publisher for refreshed signed metadata. Signature/hash failures must be treated as rejected updates; do not run the downloaded EXE manually to work around them. Low storage/folder failures require free space or corrected current-user access, followed by retry.

Setup failure retains the snapshot and previous bundle and records the Inno exit code. Restart failure records that installation completed but startup was not acknowledged. Launch NEXIS from the Start menu; a successful normal startup acknowledges the expected build. If the installed app cannot start, first preserve the whole profile and recovery directories, then use the prior application copy at the recorded `runners/<id>/NEXIS.exe` or repair with a previously verified installer. Recovery copies use the existing profile and its normal lock. Avoid running old code against a newer schema. Do not uninstall/delete the profile or automatically restore a snapshot over newer user data. Restore a preserved snapshot only while all NEXIS processes are stopped and after retaining the current profile separately. No silent data rollback occurs.

The existing explicit “Delete all NEXIS data” confirmation also authorizes erasing update recovery snapshots, helper copies, cached packages and updater logs. Cleanup refuses linked/junctioned paths and waits for the updater operation lock. A canceled confirmation erases nothing. The automatic installer uses `/NOCLOSEAPPLICATIONS`: if another process locks the installation, Setup must fail safely instead of closing active work.

The isolated upgrade test script builds a separate AppId/profile with independent keys and a loopback HTTPS fixture adapter. It runs the real signed-download, backup, native installer, helper and restart path as a non-elevated user. It changes neither production feeds nor Windows certificate trust. It is not evidence of a public GitHub upgrade or clean-machine Windows 10/11 qualification.
