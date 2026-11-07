; Inno Setup script for AutoH.
; Normally run by scripts\build.py (PyInstaller -> copy model -> this script).
; Manual: "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\AutoH.iss
; Expects the one-folder build in ..\dist\AutoH (incl. models\typhoon-asr-realtime).
;
; User data is NOT installed here: settings, modes, aliases and logs live in
; %LOCALAPPDATA%\AutoH\autoh.db, created by the app on first start. Uninstall
; leaves that database in place.

#ifndef MyAppVersion
  #define MyAppVersion "2.0.0"
#endif
#define MyAppName "AutoH"
#define MyAppPublisher "AutoH"
#define MyAppExeName "AutoH.exe"

[Setup]
AppId={{D9B4E88A-E9EA-4C16-9122-5B10A7E2C97A}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupIconFile=..\assets\autoH_icon.ico
OutputDir=..\installer-output
OutputBaseFilename=AutoH-Setup-{#MyAppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
CloseApplications=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
LicenseFile=..\LICENSE
InfoAfterFile=THIRD_PARTY_NOTICES.txt

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
; Whole one-folder build: AutoH.exe, _internal\, models\, notices
Source: "..\dist\AutoH\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
; v1 was a single AutoH.exe that wrote log.txt next to it; logs now go to the database.
; config.json is kept on purpose: the app imports it once into the database.
Type: files; Name: "{app}\log.txt"

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[Code]
function IsSameOrSubPath(const BasePath, TargetPath: string): Boolean;
var
	NormalizedBase: string;
	NormalizedTarget: string;
begin
	NormalizedBase := AddBackslash(Uppercase(Trim(BasePath)));
	NormalizedTarget := AddBackslash(Uppercase(Trim(TargetPath)));
	Result := Pos(NormalizedBase, NormalizedTarget) = 1;
end;

function IsBlockedInstallDir(const Dir: string): Boolean;
begin
	Result :=
		IsSameOrSubPath(ExpandConstant('{pf}'), Dir) or
		IsSameOrSubPath(ExpandConstant('{pf32}'), Dir) or
		IsSameOrSubPath(ExpandConstant('{pf64}'), Dir);
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
	Result := True;

	if CurPageID = wpSelectDir then
	begin
		if IsBlockedInstallDir(WizardDirValue) then
		begin
			MsgBox(
				'Please choose a folder outside Program Files.' + #13#10 +
				'AutoH is installed per user and does not need administrator rights.',
				mbError,
				MB_OK
			);
			Result := False;
		end;
	end;
end;
