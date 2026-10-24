#ifndef RepoDir
  #error RepoDir must be passed to the Inno Setup compiler
#endif
#ifndef DistDir
  #error DistDir must point to the packaged Practicum folder
#endif
#ifndef OutputDir
  #error OutputDir must be set to the release output folder
#endif

#define AppName "Practicum"
#define AppVersion "0.1.0"
#define AppPublisher "Practicum"

[Setup]
AppId={{44B7FC5F-0E73-4E0B-A531-9B359D3C0864}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppComments=Requires Docker Desktop installed and running to start labs.
DefaultDirName={localappdata}\Programs\Practicum
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64
SetupIconFile={#RepoDir}\assets\practicum.ico
UninstallDisplayIcon={app}\Practicum.exe
OutputDir={#OutputDir}
OutputBaseFilename=Practicum-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "{#DistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Practicum"; Filename: "{app}\Practicum.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\Practicum"; Filename: "{app}\Practicum.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\Practicum.exe"; Description: "Launch Practicum"; Flags: postinstall nowait skipifsilent
