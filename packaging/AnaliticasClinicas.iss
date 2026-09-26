; Inno Setup: compilación desde Windows después de packaging/build-windows.ps1.
#ifndef MyAppVersion
  #define MyAppVersion "0.9.4"
#endif

#define MyAppName "Control Analíticas Clínicas"
#define MyAppExeName "AnaliticasClinicas.exe"

[Languages]
; Al incluir únicamente español, Inno Setup lo selecciona por defecto y no
; muestra un selector de idioma durante la instalación.
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Setup]
; No cambiar este identificador entre versiones: Inno Setup lo usa para
; reconocer una actualización y mantener un único registro de desinstalación.
AppId={{C3B0DD8A-1D44-485A-BDDE-BCF83BAF910D}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
SetupIconFile=logo.ico
UninstallDisplayIcon={app}\logo.ico
WizardImageFile=wizard-logo.bmp
AppPublisher=Control Analíticas Clínicas
DefaultDirName={localappdata}\Programs\AnaliticasClinicas
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
; La aplicación almacena los datos por usuario en %LOCALAPPDATA%. Permitir
; cambiar la carpeta de binarios facilitaría ejecutar versiones distintas
; contra esa misma base de datos, por lo que se usa una única ubicación fija.
DisableDirPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist-installer
OutputBaseFilename=cac-elrocho-v{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Files]
Source: "..\dist\AnaliticasClinicas\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\THIRD_PARTY_LICENSES.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\assets\logo.ico"; DestDir: "{app}"; Flags: ignoreversion

[Registry]
; Marcador independiente del registro de desinstalación de Inno Setup. Permite
; detectar de manera estable una instalación previa del producto.
Root: HKCU; Subkey: "Software\ControlAnaliticasClinicas"; ValueType: string; ValueName: "InstallPath"; ValueData: "{app}"; Flags: uninsdeletekey

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\logo.ico"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\logo.ico"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Crear un acceso directo en el escritorio"; Flags: unchecked

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Abrir {#MyAppName}"; Flags: nowait postinstall skipifsilent

[Code]
const
  ProductRegistryKey = 'Software\ControlAnaliticasClinicas';
  InnoUninstallKey = 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{C3B0DD8A-1D44-485A-BDDE-BCF83BAF910D}_is1';

function PreviousInstallationExists(): Boolean;
var
  InstallPath: String;
  UninstallCommand: String;
begin
  Result := RegQueryStringValue(HKCU, ProductRegistryKey, 'InstallPath', InstallPath)
    or RegQueryStringValue(HKCU, InnoUninstallKey, 'UninstallString', UninstallCommand);
end;

function InitializeSetup(): Boolean;
begin
  Result := not PreviousInstallationExists();
  if not Result then begin
    MsgBox(
      'Ya existe una instalación de ' + '{#MyAppName}' + '.' + #13#10 + #13#10 +
      'Desinstala la versión existente antes de instalar otra.' + #13#10 + #13#10 +
      'Tus datos clínicos, PDFs, copias de seguridad y configuración no se perderán: se conservan en %LOCALAPPDATA%\AnaliticasClinicas.' + #13#10 + #13#10 +
      'Aun así, se recomienda crear una copia de seguridad desde la aplicación antes de desinstalar la versión anterior.',
      mbError,
      MB_OK
    );
  end;
end;

// Los datos clínicos se guardan deliberadamente fuera de {app}, en
// %LOCALAPPDATA%\AnaliticasClinicas. Por tanto no se borran al desinstalar.
