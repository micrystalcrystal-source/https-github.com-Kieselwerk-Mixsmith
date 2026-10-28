; Inno Setup script for the full Mixsmith package (program + PyTorch + Demucs model + ffmpeg).
; Further separation models are not bundled: Mixsmith downloads them on first use from their authors' sources (see LIZENZEN.md).
; Build:  python build.py full   (runs PyInstaller into dist_full, then ISCC with this script)
; Expects the PyInstaller onedir output in dist_full\Mixsmith and the folders profiles, models, bin next to this script.
; Mixsmith has its own AppId: it installs next to an existing Mastering-Tool 2.x instead of replacing it.

#define AppName "Mixsmith"
#ifndef AppVersion
  #define AppVersion "1.0.1"
#endif
#define AppPublisher "Kieselwerk"
#define AppExe "Mixsmith.exe"

[Setup]
AppId={{806DC58E-2B7C-47B7-9048-6541CD1B72AD}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
UninstallDisplayIcon={app}\logo.ico
OutputDir=installer
OutputBaseFilename=Mixsmith-{#AppVersion}-Setup
SetupIconFile=logo.ico
LicenseFile=LICENSE
Compression=lzma2/fast
SolidCompression=yes
LZMAUseSeparateProcess=yes
DiskSpanning=no
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
WizardStyle=modern
ShowLanguageDialog=no
CloseApplications=yes

[Languages]
Name: "german"; MessagesFile: "compiler:Languages\German.isl"

[Tasks]
Name: "desktopicon"; Description: "Verknüpfung auf dem Desktop anlegen"; GroupDescription: "Zusätzliche Verknüpfungen:"

[InstallDelete]
; models of 1.0.0 that are no longer bundled (downloads go to %APPDATA%\Mixsmith\models)
Type: files; Name: "{app}\models\*.ckpt"
Type: files; Name: "{app}\models\*.pth"
; remove the program files of older versions (user profiles live in %APPDATA%\Mixsmith and are kept)
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "dist_full\Mixsmith\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "profiles\*"; DestDir: "{app}\profiles"; Flags: ignoreversion recursesubdirs
Source: "models\htdemucs_6s.yaml"; DestDir: "{app}\models"; Flags: ignoreversion
Source: "models\5c90dfd2-34c22ccb.th"; DestDir: "{app}\models"; Flags: ignoreversion
Source: "models\*.json"; DestDir: "{app}\models"; Flags: ignoreversion
Source: "bin\ffmpeg.exe"; DestDir: "{app}\bin"; Flags: ignoreversion
Source: "logo.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "logo.png"; DestDir: "{app}"; Flags: ignoreversion
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "LIZENZEN.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"; IconFilename: "{app}\logo.ico"
Name: "{group}\{#AppName} deinstallieren"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; IconFilename: "{app}\logo.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{#AppName} jetzt starten"; Flags: nowait postinstall skipifsilent
