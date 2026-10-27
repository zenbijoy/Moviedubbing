; Inno Setup 6 Script for Movie Dubbing Studio AI Workstation
; Standalone 64-bit Windows Installer Configuration

#define MyAppName "Movie Dubbing Studio"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "AI Dubbing Studio Engineering"
#define MyAppURL "https://github.com/zenbijoy/Moviedubbing"
#define MyAppExeName "MovieDubbingStudio.bat"
#define MyDistDir "..\dist\MovieDubbingStudio_win64"

[Setup]
; Unique GUID for Application Version Upgrades
AppId={{C289F4BD-8A19-4C4F-94B6-6BFA45D99812}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\MovieDubbingStudio
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
LicenseFile=..\LICENSE
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=MovieDubbingStudio_v{#MyAppVersion}_Setup
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
ChangesAssociations=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "fileassoc"; Description: "Associate .aidub project files with Movie Dubbing Studio"; GroupDescription: "File Associations:"

[Files]
; Copy all files and folders assembled by packaging/build_windows.py
Source: "{#MyDistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{group}\Movie Dubbing Studio CLI"; Filename: "{app}\aidub.bat"; WorkingDir: "{app}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Registry]
; Associate .aidub project files with Movie Dubbing Studio launcher
Root: HKA; Subkey: "Software\Classes\.aidub"; ValueType: string; ValueName: ""; ValueData: "AIDubStudio.Project"; Flags: uninsdeletevalue; Tasks: fileassoc
Root: HKA; Subkey: "Software\Classes\AIDubStudio.Project"; ValueType: string; ValueName: ""; ValueData: "Movie Dubbing Studio Project Package"; Flags: uninsdeletekey; Tasks: fileassoc
Root: HKA; Subkey: "Software\Classes\AIDubStudio.Project\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\resources\icons\project.ico,0"; Flags: uninsdeletevalue; Tasks: fileassoc
Root: HKA; Subkey: "Software\Classes\AIDubStudio.Project\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Flags: uninsdeletekey; Tasks: fileassoc

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: shellexec postinstall skipifsilent nowait
