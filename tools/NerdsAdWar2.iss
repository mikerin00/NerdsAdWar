; ────────────────────────────────────────────────────────────────────────────
; NerdsAdWar2.iss  —  Inno Setup script
; Gebruik: iscc NerdsAdWar2.iss /DMyAppVersion=v2.9
; Of via build.bat (doet dit automatisch).
; ────────────────────────────────────────────────────────────────────────────

#ifndef MyAppVersion
  #define MyAppVersion "v0.0"
#endif

#define MyAppName      "Nerds ad War 2"
#define MyAppExeName   "NerdsAdWar2.exe"
#define MyAppPublisher "NerdsAdWar"

[Setup]
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
; Installeer per gebruiker — geen admin-rechten nodig, updater kan de exe vervangen
DefaultDirName={localappdata}\NerdsAdWar2
DefaultGroupName={#MyAppName}
; Geen admin vereist (updater schrijft straks ook zonder admin naar deze map)
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=dist
OutputBaseFilename=Setup_NerdsAdWar2_{#MyAppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
; Icoon voor de installer zelf (optioneel)
; SetupIconFile=icon.ico

[Languages]
Name: "dutch"; MessagesFile: "compiler:Languages\Dutch.isl"

[Tasks]
Name: "desktopicon"; Description: "Snelkoppeling op bureaublad"; GroupDescription: "Extra opties:"; Flags: unchecked

[Files]
; De gecompileerde exe
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
; Maps-map (standaard + eerder gemaakte sandbox-maps)
Source: "maps\*"; DestDir: "{app}\maps"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Start-menu
Name: "{group}\{#MyAppName}";          Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Verwijder {#MyAppName}"; Filename: "{uninstallexe}"
; Bureaublad (alleen als taak aangevinkt)
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; Optioneel: start het spel direct na installatie
Filename: "{app}\{#MyAppExeName}"; Description: "Start {#MyAppName}"; Flags: nowait postinstall skipifsilent
