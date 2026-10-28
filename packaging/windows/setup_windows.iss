; Inno Setup script for the Windows installer of Mixsmith (version without AI separation).
; Build:  python build.py setup   (PyInstaller onedir into dist_setup, then ISCC with this script)
; Wizard pictures in Kieselwerk style: python packaging/windows/make_wizard_images.py

#define AppName "Mixsmith"
#ifndef AppVersion
  #define AppVersion "1.0.1"
#endif
#define AppPublisher "Kieselwerk"
#define AppExe "Mixsmith.exe"
#define Root "..\.."

[Setup]
AppId={{806DC58E-2B7C-47B7-9048-6541CD1B72AD}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL=https://kieselwerk.com
AppContact=info@kieselwerk.com
AppComments=Mischen und Mastern nach Referenzsongs. Kieselwerk, Kay Seufferheld, Augsburg.
AppSupportURL=https://github.com/Kieselwerk/Mixsmith/issues
AppUpdatesURL=https://kieselwerk.itch.io/mixsmith
AppCopyright=© 2026 Kay Seufferheld, Kieselwerk, Augsburg
VersionInfoCompany=Kieselwerk – Kay Seufferheld, Augsburg
VersionInfoDescription=Mixsmith Setup – Mischen und Mastern nach Referenzsongs
VersionInfoVersion={#AppVersion}
VersionInfoTextVersion={#AppVersion}
VersionInfoProductName=Mixsmith
VersionInfoProductVersion={#AppVersion}
VersionInfoProductTextVersion={#AppVersion}
VersionInfoCopyright=© 2026 Kay Seufferheld, Kieselwerk, Augsburg. GNU GPLv3.
VersionInfoOriginalFileName=Mixsmith-{#AppVersion}-Windows-Setup.exe
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
OutputDir={#Root}\installer
OutputBaseFilename=Mixsmith-{#AppVersion}-Windows-Setup
SetupIconFile={#Root}\logo.ico
LicenseFile={#Root}\LICENSE
WizardStyle=modern
WizardImageFile=wizard_164.bmp,wizard_205.bmp,wizard_246.bmp,wizard_328.bmp
WizardSmallImageFile=wizard_small_55.bmp,wizard_small_69.bmp,wizard_small_83.bmp,wizard_small_110.bmp
WizardImageStretch=no
WizardImageAlphaFormat=defined
WizardImageBackColor=$00706C25
WizardSmallImageBackColor=$00706C25
Compression=lzma2/max
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ShowLanguageDialog=no
CloseApplications=yes

[Languages]
Name: "german"; MessagesFile: "compiler:Languages\German.isl"

[Messages]
german.WelcomeLabel1=Willkommen bei Mixsmith
german.WelcomeLabel2=Mixsmith mischt und mastert eigene Songs nach dem Vorbild von Songs, deren Klang dir gefällt.%n%nDieser Assistent installiert [name/ver] auf deinem Computer. Mixsmith ist freie Software von Kieselwerk unter der GNU GPLv3.%n%nSchließe am besten alle anderen Programme, bevor du fortfährst.
german.FinishedHeadingLabel=Mixsmith ist installiert
german.FinishedLabel=Mixsmith ist jetzt auf deinem Computer. Du findest es im Startmenü.%n%nTipp: Unter „Tutorial ansehen“ zeigt dir Mixi in zweieinhalb Minuten die wichtigsten Funktionen.

[Tasks]
Name: "desktopicon"; Description: "Verknüpfung auf dem Desktop anlegen"; GroupDescription: "Zusätzliche Verknüpfungen:"

[InstallDelete]
; program files of older versions (profiles and settings live in %APPDATA%\Mixsmith and are kept)
Type: filesandordirs; Name: "{app}\_internal"
Type: files; Name: "{app}\models\*.ckpt"
Type: files; Name: "{app}\models\*.pth"

[Files]
Source: "{#Root}\dist_setup\Mixsmith\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#Root}\profiles\*"; DestDir: "{app}\profiles"; Flags: ignoreversion recursesubdirs
Source: "{#Root}\logo.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#Root}\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#Root}\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#Root}\LIZENZEN.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"; Comment: "Mischen und Mastern nach Referenzsongs"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "Mixsmith jetzt starten"; Flags: nowait postinstall skipifsilent

[Code]
{ Kieselwerk colours (TColor is $00BBGGRR): sand #EFEBE4, petrol #256C70, graphite #1F2422, light petrol #BFD3D2 }
const
  Sand = $00E4EBEF; Petrol = $00706C25; Graphit = $0022241F; PetrolHell = $00D2D3BF;

procedure InitializeWizard;
begin
  WizardForm.Color := Sand;
  WizardForm.MainPanel.Color := Petrol;
  WizardForm.PageNameLabel.Font.Color := Sand;
  WizardForm.PageNameLabel.Font.Name := 'Segoe UI Semibold';
  WizardForm.PageDescriptionLabel.Font.Color := PetrolHell;
  WizardForm.InnerPage.Color := Sand;
  WizardForm.WelcomePage.Color := Sand;
  WizardForm.FinishedPage.Color := Sand;
  WizardForm.WelcomeLabel1.Font.Color := Petrol;
  WizardForm.WelcomeLabel1.Font.Name := 'Segoe UI Semibold';
  WizardForm.WelcomeLabel2.Font.Color := Graphit;
  WizardForm.FinishedHeadingLabel.Font.Color := Petrol;
  WizardForm.FinishedHeadingLabel.Font.Name := 'Segoe UI Semibold';
  WizardForm.FinishedLabel.Font.Color := Graphit;
end;
