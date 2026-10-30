# NEXIS 1.4.1 — setup acknowledgment recovery

29 October 2026. Development/test candidate; no public release is approved.

The required “I understand” checkbox must stay **checked** to continue. Unchecked
consent blocks Next. All optional capability choices can stay selected or off.
The requirement is now displayed above the scrollable permission choices.

The older normal 1.4.0 installation can retain Qt's initial-value mandatory-field
bug. Earlier Living Core test installers installed separately, so the normal
NEXIS shortcut could still launch that older executable. This 1.4.1 installer uses
the normal application identity and upgrades the registered installation and
normal shortcuts. The particle core and other recent features are retained.

Close the older NEXIS window and tray instance before installing. Run
`NEXIS-Desktop-1.4.1.0-Setup.exe` from Release Nexis. Choose Install / Repair,
retain the registered program directory, and launch NEXIS after installation.
Saved settings, provider credentials and conversations remain in the existing
account profile; setup does not reset that profile. The new EXE version is 1.4.1.

Tests cover fresh and saved consent, saved capability selections, repeated
checking/unchecking, Back navigation, keyboard activation and actual native
page transitions. See the matching build/verification report for measured results
and any unverified checks. Do not substitute an older 1.4.0 executable or installer.
