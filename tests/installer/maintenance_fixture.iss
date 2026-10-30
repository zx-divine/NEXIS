; Isolated verification installer, never a distributable NEXIS build.
; The caller supplies a new, non-production AppIdentity and a disposable directory.
#ifndef AppIdentity
  #error Test AppIdentity must be supplied explicitly
#endif
#if AppIdentity == "F462E4BE-1F1F-428C-AD8C-4B5C06972164"
  #error Tests must never use the real application identity
#endif
#include "..\..\installer\NEXIS.iss"

[Code]
var
  VerificationChecks: String;

procedure CheckMaintenance(Condition: Boolean; const Name: String);
begin
  if not Condition then RaiseException('Maintenance check failed: ' + Name);
  VerificationChecks := VerificationChecks + 'PASS: ' + Name + #13#10;
end;

function InitializeSetup: Boolean;
var
  Mode, ReportPath, Executable, OriginalCommand, Directory: String;
  ResultCode: Integer;
begin
  Result := True;
  Mode := ExpandConstant('{param:NEXISVERIFY|}');
  if Mode = '' then Exit;
  ReportPath := ExpandConstant('{param:NEXISREPORT|}');
  VerificationChecks := '';
  if Mode = 'missing' then begin
    CheckMaintenance(not FindRegisteredInstallation, 'missing installation is unavailable');
    CheckMaintenance(not RunRegisteredUninstaller('/NORESTART', ResultCode), 'missing uninstaller cannot execute');
    CheckMaintenance(ResultCode = 2, 'missing uninstaller has actionable status');
  end else begin
    CheckMaintenance(FindRegisteredInstallation, 'installed fixture is detected');
    Directory := InstalledDirectory;
    CheckMaintenance(RegQueryStringValue(HKCU64, NexisUninstallKey, 'UninstallString', OriginalCommand), 'registered command is available');
    CheckMaintenance(ValidateUninstallCommand(Directory, OriginalCommand, Executable), 'valid quoted Inno path is accepted');
    CheckMaintenance(not ValidateUninstallCommand(Directory, OriginalCommand + ' /SILENT', Executable), 'registry arguments rejected');
    CheckMaintenance(not ValidateUninstallCommand(Directory, InstalledUninstaller, Executable), 'unquoted command rejected');
    CheckMaintenance(not ValidateUninstallCommand(Directory, '"' + Directory + '\other.exe"', Executable), 'arbitrary executable rejected');
    CheckMaintenance(not ValidateUninstallCommand(Directory, '"' + Directory + '\uninsxyz.exe"', Executable), 'invalid uninstaller index rejected');
    CheckMaintenance(not ValidateUninstallCommand(Directory, '"' + Directory + '\unins999.exe"', Executable), 'missing executable rejected');
    CheckMaintenance(not ValidateUninstallCommand(Directory, '"C:\Windows\unins000.exe"', Executable), 'outside directory rejected');
    CheckMaintenance(not ValidateUninstallCommand(Directory, '"' + Directory + '\..\unins000.exe"', Executable), 'traversal rejected');
    CheckMaintenance(not ValidateUninstallCommand('relative', OriginalCommand, Executable), 'relative directory rejected');
    CheckMaintenance(not ValidateUninstallCommand('C:\', '"C:\unins000.exe"', Executable), 'drive root rejected');
    CheckMaintenance(not ValidateUninstallCommand(Directory + '\..', OriginalCommand, Executable), 'noncanonical directory rejected');
    CheckMaintenance(RegWriteStringValue(HKCU64, NexisUninstallKey, 'UninstallString', OriginalCommand + ' /SILENT'), 'fixture tampering prepared');
    try
      CheckMaintenance(not RunRegisteredUninstaller('/NORESTART', ResultCode), 'execution revalidates registry immediately');
      CheckMaintenance(ResultCode = 2, 'unsafe command fails closed');
    finally
      RegWriteStringValue(HKCU64, NexisUninstallKey, 'UninstallString', OriginalCommand);
    end;
    if Mode = 'remove' then begin
      CheckMaintenance(RunRegisteredUninstaller('/VERYSILENT /SUPPRESSMSGBOXES /NORESTART', ResultCode), 'registered fixture uninstaller executed');
      CheckMaintenance(ResultCode = 0, 'fixture uninstaller exit zero');
      CheckMaintenance(not FindRegisteredInstallation, 'fixture registration removed');
      CheckMaintenance(not FileExists(Directory + '\NEXIS.exe'), 'installed fixture executable removed');
      CheckMaintenance(FileExists(Directory + '\user-created-keep.txt'), 'untracked personal file preserved');
    end;
  end;
  CheckMaintenance(SaveStringToFile(ReportPath, VerificationChecks, False), 'verification evidence written');
  Result := False; // Inspection/removal must never proceed to installation.
end;
