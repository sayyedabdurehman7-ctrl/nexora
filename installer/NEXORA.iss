#define AppName "NEXORA"
#define AppVersion "0.1.0"
#define AppPublisher "NEXORA"
#define AppExeName "launch-nexora.cmd"

[Setup]
AppId={{B1C8E19A-2E9C-4A34-9DBA-6D58D8C3A9F4}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={localappdata}\Programs\NEXORA
DefaultGroupName=NEXORA
OutputDir=output
OutputBaseFilename=NEXORA-Setup
Compression=lzma
SolidCompression=yes
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64
UninstallDisplayIcon={app}\NEXORA.exe

[Files]
Source: "output\NEXORA\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "launch-nexora.cmd"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autodesktop}\NEXORA"; Filename: "{app}\launch-nexora.cmd"; WorkingDir: "{app}"
Name: "{group}\NEXORA"; Filename: "{app}\launch-nexora.cmd"; WorkingDir: "{app}"

[Run]
Filename: "{app}\launch-nexora.cmd"; Description: "Launch NEXORA"; Flags: postinstall nowait skipifsilent
