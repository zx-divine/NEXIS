; Compile after PyInstaller: ISCC.exe installer\NEXIS.iss
; Stable identity must match nexis.branding.APP_USER_MODEL_ID.
#define AppVersion GetVersionNumbersString("..\dist\NEXIS\NEXIS.exe")
#define AppModelID "NEXIS.Desktop"

[Setup]
AppId={{F462E4BE-1F1F-428C-AD8C-4B5C06972164}
AppName=NEXIS Desktop
AppVersion={#AppVersion}
DefaultDirName={localappdata}\Programs\NEXIS Desktop
DefaultGroupName=NEXIS Desktop
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; Qt 6.12 requires Windows 10 version 1809 or newer.
MinVersion=10.0.17763
OutputDir=..\dist\installer
OutputBaseFilename=NEXIS-Desktop-{#AppVersion}-Setup
SetupIconFile=..\assets\branding\NEXIS.ico
UninstallDisplayIcon={app}\NEXIS.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
WizardSmallImageFile=..\assets\branding\NEXIS_logo.png
CloseApplications=yes
RestartApplications=no

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Files]
Source: "..\dist\NEXIS\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\NEXIS Desktop"; Filename: "{app}\NEXIS.exe"; WorkingDir: "{app}"; IconFilename: "{app}\NEXIS.exe"; IconIndex: 0; AppUserModelID: "{#AppModelID}"
Name: "{autodesktop}\NEXIS Desktop"; Filename: "{app}\NEXIS.exe"; WorkingDir: "{app}"; IconFilename: "{app}\NEXIS.exe"; IconIndex: 0; AppUserModelID: "{#AppModelID}"; Tasks: desktopicon

[Run]
Filename: "{app}\NEXIS.exe"; Description: "Launch NEXIS Desktop"; Flags: nowait postinstall skipifsilent
