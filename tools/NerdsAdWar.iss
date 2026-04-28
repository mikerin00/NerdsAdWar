; ────────────────────────────────────────────────────────────────────────────
; NerdsAdWar.iss  —  Inno Setup script
; Usage: iscc tools\NerdsAdWar.iss /DMyAppVersion=v1.0
; Or via build.bat (handled automatically).
; ────────────────────────────────────────────────────────────────────────────

#ifndef MyAppVersion
  #define MyAppVersion "v0.0"
#endif

#define MyAppName      "Nerds at War"
#define MyAppExeName   "NerdsAdWar.exe"
#define MyAppPublisher "NerdsAdWar"

[Setup]
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\NerdsAdWar
DefaultGroupName={#MyAppName}
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\dist
OutputBaseFilename=Setup_NerdsAdWar_{#MyAppVersion}
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Desktop shortcut"; GroupDescription: "Additional options:"; Flags: unchecked

[Dirs]
Name: "{app}\maps"

[Files]
Source: "..\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\assets\audio\music_menu_custom.mpeg"; DestDir: "{app}\assets\audio"; Flags: ignoreversion skipifsourcedoesntexist

[Icons]
Name: "{group}\{#MyAppName}";           Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}";     Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Start {#MyAppName}"; Flags: nowait postinstall skipifsilent
