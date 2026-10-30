# NEXIS Setup maintenance revision 2

Reopening Setup now offers Install / Repair and Uninstall NEXIS. Install is the
default. Uninstall is enabled only for a usable per-user Inno registration of
NEXIS's stable application identity. Portable copies are not installed programs.

Uninstall rechecks that registration, shows the program directory and asks for
confirmation with No selected by default. It launches the registered uninstaller
with a separate executable path and fixed `/NORESTART` arguments. Windows handles
the actual uninstall confirmation/removal. Cancellation/failure does not start
installation. Silent Setup keeps install/upgrade semantics; it has no new silent
uninstall switch.

Paths must be canonical absolute drive paths. The registered command must contain
only a quoted `uninsNNN.exe` in the registered InstallLocation, and that executable
must exist. Registry-supplied arguments, traversal, missing paths and other program
names are rejected. Damaged/all-users registrations can be reviewed in Windows
Settings > Apps. Setup does not elevate the complete application.

Inno removes only files it installed and its shortcuts/registration. No wildcard
folder removal or personal-profile deletion was added. Saved data under
`%LOCALAPPDATA%\NEXIS\NEXIS Desktop` is kept. Users should exit NEXIS and its tray
process before uninstalling. Existing backups remain separate and untouched.

For this installer-only update, engineering app version 1.3.8 and its verified
portable payload are unchanged. Setup's file description identifies maintenance
revision 2. Do not claim a new application regression or a new final public V1.

`verify_installer_maintenance.py` compiles the real shared Pascal code with an
isolated test identity, then tests actual install/detection/uninstall, invalid
commands and preservation of an untracked synthetic personal file. Fixture
inspection exits 1 intentionally via InitializeSetup=False; its written assertion
evidence is mandatory. It never uses the real application's uninstall identity.
`build_installer_maintenance.py` verifies that evidence, every original payload
file against the previously verified ZIP, and compiles a new Setup. Existing
five-round application-build gates remain intact.
