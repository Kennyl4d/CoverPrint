#define MyAppName "CoverPrint"
#define MyAppVersion "1.1.0"
#define MyAppPublisher "Kennyl4d"
#define MyAppExeName "CoverPrint.exe"

[Setup]
AppId={{D5312747-FF1B-46A1-9BA3-92E1D1A2F550}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\CoverPrint
DefaultGroupName=CoverPrint
DisableProgramGroupPage=yes
OutputDir=..\release
OutputBaseFilename=CoverPrint-1.1.0-Windows-Setup
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
LicenseFile=..\LICENSE

[Files]
Source: "..\dist\CoverPrint\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\CoverPrint"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\CoverPrint"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch CoverPrint"; Flags: nowait postinstall skipifsilent
