// Setup maintenance revision 2. Only the registered Inno uninstaller removes files.
// Never recursively remove application folders or the separate personal profile.
const
  NexisUninstallKey = 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{{#AppIdentity}}_is1';

var
  MaintenancePage: TWizardPage;
  InstallChoice, UninstallChoice: TNewRadioButton;
  InstallDetails, UninstallDetails: TNewStaticText;
  InstalledDirectory, InstalledUninstaller, InstalledVersion: String;
  MaintenanceComplete: Boolean;

function ValidateUninstallCommand(const Directory, Command: String; var Executable: String): Boolean;
var
  Candidate, Name, NormalDirectory: String;
  I: Integer;
begin
  Result := False;
  Executable := '';
  NormalDirectory := RemoveBackslashUnlessRoot(Trim(Directory));
  if (Length(NormalDirectory) < 4) or (Copy(NormalDirectory, 2, 2) <> ':\') then Exit;
  if CompareText(NormalDirectory, ExpandFileName(NormalDirectory)) <> 0 then Exit;
  Candidate := Trim(Command);
  if Length(Candidate) < 2 then Exit;
  if (Candidate[1] <> '"') or (Candidate[Length(Candidate)] <> '"') then Exit;
  Candidate := Copy(Candidate, 2, Length(Candidate) - 2);
  if Pos('"', Candidate) <> 0 then Exit;
  if CompareText(ExtractFileDir(Candidate), NormalDirectory) <> 0 then Exit;
  if CompareText(Candidate, ExpandFileName(Candidate)) <> 0 then Exit;
  Name := Lowercase(ExtractFileName(Candidate));
  if (Length(Name) <> 12) or (Copy(Name, 1, 5) <> 'unins') or
     (Copy(Name, 9, 4) <> '.exe') then Exit;
  for I := 6 to 8 do
    if (Name[I] < '0') or (Name[I] > '9') then Exit;
  if not FileExists(Candidate) then Exit;
  Executable := Candidate;
  Result := True;
end;

function FindRegisteredInstallation: Boolean;
var
  Directory, Command, Executable: String;
begin
  InstalledDirectory := '';
  InstalledUninstaller := '';
  InstalledVersion := '';
  Result := False;
  // NEXIS is installed per-user. Do not select another user's/all-users installation.
  if not RegQueryStringValue(HKCU64, NexisUninstallKey, 'InstallLocation', Directory) then Exit;
  if not RegQueryStringValue(HKCU64, NexisUninstallKey, 'UninstallString', Command) then Exit;
  if not ValidateUninstallCommand(Directory, Command, Executable) then Exit;
  InstalledDirectory := RemoveBackslashUnlessRoot(Trim(Directory));
  InstalledUninstaller := Executable;
  RegQueryStringValue(HKCU64, NexisUninstallKey, 'DisplayVersion', InstalledVersion);
  Result := True;
end;

procedure RefreshMaintenance;
begin
  UninstallChoice.Enabled := FindRegisteredInstallation;
  if UninstallChoice.Enabled then begin
    InstallChoice.Caption := '&Install / Repair NEXIS';
    UninstallDetails.Caption := 'Installed version: ' + InstalledVersion + #13#10 +
      InstalledDirectory + #13#10 +
      'Removes installed program files and shortcuts. Your saved settings, credentials and conversations are kept.';
    Log('NEXIS maintenance: registered per-user installation available.');
  end else begin
    InstallChoice.Caption := '&Install NEXIS';
    UninstallChoice.Checked := False;
    InstallChoice.Checked := True;
    UninstallDetails.Caption := 'No usable NEXIS installation was found for this Windows account. ' +
      'Portable copies are not registered installations. If an installation is damaged, use Windows Settings > Apps.';
    Log('NEXIS maintenance: no usable registered per-user installation.');
  end;
end;

function RunRegisteredUninstaller(const Parameters: String; var ResultCode: Integer): Boolean;
begin
  Result := False;
  // Re-read and validate immediately before execution. No registry-supplied arguments.
  if not FindRegisteredInstallation then begin
    ResultCode := 2;
    Exit;
  end;
  Result := Exec(InstalledUninstaller, Parameters, InstalledDirectory,
    SW_SHOWNORMAL, ewWaitUntilTerminated, ResultCode);
end;

procedure InitializeWizard;
begin
  MaintenancePage := CreateCustomPage(wpWelcome, 'Install or uninstall NEXIS',
    'Choose what you would like to do. Uninstall always requires confirmation.');
  InstallChoice := TNewRadioButton.Create(MaintenancePage);
  InstallChoice.Parent := MaintenancePage.Surface;
  InstallChoice.SetBounds(0, ScaleY(4), MaintenancePage.SurfaceWidth, ScaleY(24));
  InstallChoice.Caption := '&Install NEXIS';
  InstallChoice.Checked := True;
  InstallChoice.TabOrder := 0;
  InstallDetails := TNewStaticText.Create(MaintenancePage);
  InstallDetails.Parent := MaintenancePage.Surface;
  InstallDetails.SetBounds(ScaleX(22), ScaleY(34), MaintenancePage.SurfaceWidth - ScaleX(22), ScaleY(64));
  InstallDetails.AutoSize := False;
  InstallDetails.WordWrap := True;
  InstallDetails.Caption := 'Install this NEXIS candidate, or reinstall its program files to repair an existing installation. ' +
    'Personal data is stored separately and is preserved.';
  UninstallChoice := TNewRadioButton.Create(MaintenancePage);
  UninstallChoice.Parent := MaintenancePage.Surface;
  UninstallChoice.SetBounds(0, ScaleY(112), MaintenancePage.SurfaceWidth, ScaleY(24));
  UninstallChoice.Caption := '&Uninstall NEXIS';
  UninstallChoice.TabOrder := 1;
  UninstallDetails := TNewStaticText.Create(MaintenancePage);
  UninstallDetails.Parent := MaintenancePage.Surface;
  UninstallDetails.SetBounds(ScaleX(22), ScaleY(142), MaintenancePage.SurfaceWidth - ScaleX(22),
    MaintenancePage.SurfaceHeight - ScaleY(142));
  UninstallDetails.AutoSize := False;
  UninstallDetails.WordWrap := True;
  MaintenanceComplete := False;
  RefreshMaintenance;
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID = MaintenancePage.ID then RefreshMaintenance;
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  // Silent automation keeps its existing install/upgrade behavior. No silent uninstall switch.
  Result := WizardSilent and (PageID = MaintenancePage.ID);
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  ResultCode: Integer;
begin
  Result := True;
  if (CurPageID <> MaintenancePage.ID) or not UninstallChoice.Checked then Exit;
  Result := False;
  if not FindRegisteredInstallation then begin
    RefreshMaintenance;
    MsgBox('The registered uninstaller is unavailable. Use Windows Settings > Apps to review this installation.', mbError, MB_OK);
    Exit;
  end;
  if MsgBox('Uninstall NEXIS from:' + #13#10 + InstalledDirectory + #13#10#13#10 +
    'Program files and shortcuts will be removed. Your saved personal data will be kept.' + #13#10#13#10 +
    'Close NEXIS, including its tray icon, before continuing. Continue to the Windows uninstaller?',
    mbConfirmation, MB_YESNO or MB_DEFBUTTON2) <> IDYES then Exit;
  WizardForm.Enabled := False;
  try
    if not RunRegisteredUninstaller('/NORESTART', ResultCode) then begin
      MsgBox('The uninstaller could not be started: ' + SysErrorMessage(ResultCode) +
        '' + #13#10 + 'Use Windows Settings > Apps if the installation needs repair.', mbError, MB_OK);
      Exit;
    end;
  finally
    WizardForm.Enabled := True;
  end;
  RefreshMaintenance;
  if ResultCode <> 0 then begin
    MsgBox('Uninstallation did not complete (code ' + IntToStr(ResultCode) + '). ' +
      'Nothing will be installed by this action. You can retry or close Setup.', mbInformation, MB_OK);
    Exit;
  end;
  if UninstallChoice.Enabled then begin
    MsgBox('NEXIS is still registered as installed. The uninstallation may have been canceled. ' +
      'No installation has been started.', mbInformation, MB_OK);
    Exit;
  end;
  MaintenanceComplete := True;
  MsgBox('NEXIS was uninstalled. Saved personal data has been kept. ' +
    'Run this Setup again whenever you want to reinstall.', mbInformation, MB_OK);
  WizardForm.Close;
end;

procedure CancelButtonClick(CurPageID: Integer; var Cancel, Confirm: Boolean);
begin
  if MaintenanceComplete then Confirm := False;
end;


