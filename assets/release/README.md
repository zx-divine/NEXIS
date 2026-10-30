# NEXIS V1 — latest development test candidate

This build is **NEXIS v1.4** (Windows version **1.4.0**). Public product name: **Nexis v1**. Public target **1.0.0** has not been finalized.
Prepared for ASH's personal Windows installation and testing. **NOT READY for a
full-feature public release.** Do not redistribute this candidate.

Use `Nexis v1 Setup.exe` for installation or extract the entire
`Nexis v1 Portable.zip` before opening `NEXIS/NEXIS.exe`. Keep `_internal` beside
the executable. Python, Qt, audio runtimes and the pinned English Vosk recognition
model are bundled; no separate Python installation is required.

Included in NEXIS v1.4: visible Always Active controls, opt-in local Hey NEXIS phrase
listening, mandatory name/API setup decisions and conversational use of the saved
name. Say “Hey NEXIS”, pause for the listening indicator, then speak. Hard mute
stops capture. Real-room voice reliability still requires your testing.
Setup also offers Install / Repair and confirmed Uninstall NEXIS. Uninstall keeps
saved personal data. See INSTALLATION-GUIDE.md before installing or removing it.

This build comes from the current rebuilt source, including the uncommitted V1
foundation and partial Milestone 2 features. It is not a renamed older binary.
See `VERIFICATION/BUILD-REPORT.md` and `SOURCE-REVISION.json` for provenance.

Included: approved logo; NEXIS title; personalized welcome; three modes; onboarding;
eight Settings sections; six themes; state-driven orb; measured system information;
provider configuration/streaming architecture; explicit voice capture/local STT and
Windows TTS; permission-checked Windows/file tools; screen-preview workflow;
explicit local memory; saved searchable chats; Ollama preset; global launcher;
workflow editor; tray/companion; and NEXIS Doctor, within the documented limits.

Read `INSTALLATION-GUIDE.md`, `USER-GUIDE.md`, `KNOWN-LIMITATIONS.md` and
`RELEASE-VERIFICATION.md`. Confirm actual hashes in `SHA256SUMS.txt` before use.
Packages are unsigned; no publisher certificate or Windows 11 certification is
claimed. Windows security controls remain in force.

Original NEXIS code is proprietary, All Rights Reserved. `EULA-DRAFT.md` is for
review and is not an effective public distribution license. Third-party notices,
including library replacement/source obligations, remain separate and must be
respected. `LICENSE.txt` is intentionally absent until the final EULA is approved.
