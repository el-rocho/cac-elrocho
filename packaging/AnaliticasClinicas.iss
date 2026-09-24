; Inno Setup: compilación desde Windows después de packaging/build-windows.ps1.
#ifndef MyAppVersion
  #define MyAppVersion "0.9.2"
#endif

#define MyAppName "Control Analíticas Clínicas"
#define MyAppExeName "AnaliticasClinicas.exe"

[Setup]
AppId={{C3B0DD8A-1D44-485A-BDDE-BCF83BAF910D}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
SetupIconFile=logo.ico
WizardImageFile=wizard-logo.bmp
AppPublisher=Control Analíticas Clínicas
DefaultDirName={localappdata}\Programs\AnaliticasClinicas
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist-installer
OutputBaseFilename=ControlAnaliticasClinicas-Setup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Files]
Source: "..\dist\AnaliticasClinicas\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\THIRD_PARTY_LICENSES.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Crear un acceso directo en el escritorio"; Flags: unchecked

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Abrir {#MyAppName}"; Flags: nowait postinstall skipifsilent

; Los datos clínicos se guardan deliberadamente fuera de {app}, en
; %LOCALAPPDATA%\AnaliticasClinicas. Por tanto no se borran al desinstalar.
