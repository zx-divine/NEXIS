# NEXIS public 1.1.0 — secure Windows updates

Engineering build: 1.4.2. Qualification candidate; publication is separate.

- Software Updates is available in Settings → General and the Updates page.
- Startup and daily checks use signed TUF metadata from the official NEXIS GitHub release infrastructure. Existing opt-outs and network permissions are respected.
- Optional automatic downloads show percentage, transferred bytes and speed. Downloaded packages are checked against Ed25519-authenticated SHA-256 hashes and lengths.
- Restart & Install waits for active work to finish, creates a consistent recovery snapshot and uses the existing per-user Inno Setup installer without requesting elevation.
- Ready updates can be postponed and re-verified after restarting NEXIS.
- Invalid signatures, expired metadata, older versions, unexpected destinations and incompatible installers fail closed. Update failures leave normal application startup available.

Public versions and engineering builds remain separate. This preserves the existing monotonic 1.4.x build sequence; no application downgrade to engineering 1.1.0 is performed.

AI providers, onboarding, voice, themes, orb, permissions, memory and saved conversations retain their existing implementation and data locations. Unsaved conversations still require an explicit Save conversation before closing.

Windows x64 is supported. A future macOS adapter can use the signed repository interface; no macOS/iPadOS installer is implemented.

The initial updater-enabled installer must be installed once on older builds that only support release discovery. Subsequent properly published, signed releases can be installed in NEXIS. TUF signatures authenticate update packages; a public Authenticode certificate is a separate publisher prerequisite for removing unsigned-publisher warnings.
