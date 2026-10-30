; Compile after PyInstaller: ISCC.exe installer\NEXIS.iss
; Stable identity must match nexis.branding.APP_USER_MODEL_ID.
#ifndef AppSourceDir
  #define AppSourceDir "..\dist\NEXIS"
#endif
#define AppVersion GetVersionNumbersString(AddBackslash(AppSourceDir) + "NEXIS.exe")
#define AppDisplayVersion GetStringFileInfo(AddBackslash(AppSourceDir) + "NEXIS.exe", "ProductVersion")
#define AppModelID "NEXIS.Desktop"
#ifndef AppIdentity
  #define AppIdentity "F462E4BE-1F1F-428C-AD8C-4B5C06972164"
#endif
#define MaintenanceRevision "2"
#ifdef IsolatedCandidate
  #define InstallCaption "Nexis v1 - " + IsolatedCandidate
  #define InstallFolder "NEXIS-" + IsolatedCandidate
#else
  #define InstallCaption "Nexis v1"
  #define InstallFolder "NEXIS Desktop"
#endif
#ifndef ProjectRoot
  #define ProjectRoot AddBackslash(SourcePath) + ".."
#endif

[Setup]
AppId={{{#AppIdentity}}
AppName={#InstallCaption}
AppVersion={#AppVersion}
AppVerName=Nexis v1 - {#AppDisplayVersion}
AppPublisher=ASH
VersionInfoVersion={#AppVersion}
VersionInfoTextVersion={#AppVersion}
VersionInfoProductVersion={#AppVersion}
VersionInfoProductTextVersion={#AppDisplayVersion}
VersionInfoDescription=Nexis v1 - {#AppDisplayVersion} Setup (maintenance revision {#MaintenanceRevision})
InfoBeforeFile={#ProjectRoot}\assets\release\CANDIDATE-NOTICE.txt
DefaultDirName={localappdata}\Programs\{#InstallFolder}
DefaultGroupName={#InstallCaption}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; Supported NEXIS launch target: Windows 10 22H2 build 19045+, or Windows 11.
MinVersion=10.0.19045
OutputDir=..\dist\installer
OutputBaseFilename=NEXIS-Desktop-{#AppVersion}-Setup
SetupIconFile={#ProjectRoot}\assets\branding\NEXIS.ico
UninstallDisplayIcon={app}\NEXIS.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
DisableWelcomePage=no
WizardImageFile={#ProjectRoot}\assets\branding\installer-sidebar.png
WizardSmallImageFile={#ProjectRoot}\assets\branding\NEXIS_symbol.png
CloseApplications=yes
RestartApplications=no

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Files]
Source: "{#AppSourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#InstallCaption}"; Filename: "{app}\NEXIS.exe"; WorkingDir: "{app}"; IconFilename: "{app}\NEXIS.exe"; IconIndex: 0; AppUserModelID: "{#AppModelID}"
Name: "{autodesktop}\{#InstallCaption}"; Filename: "{app}\NEXIS.exe"; WorkingDir: "{app}"; IconFilename: "{app}\NEXIS.exe"; IconIndex: 0; AppUserModelID: "{#AppModelID}"; Tasks: desktopicon

[Run]
Filename: "{app}\NEXIS.exe"; Description: "Launch Nexis v1"; Flags: nowait postinstall skipifsilent

[Code]
#include "maintenance.iss"
