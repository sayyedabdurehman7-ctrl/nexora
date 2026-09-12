#define AppName "NEXORA"
#define AppVersion "0.3.1"
#define AppPublisher "NEXORA"

[Setup]
AppId={{B1C8E19A-2E9C-4A34-9DBA-6D58D8C3A9F4}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
VersionInfoVersion={#AppVersion}
VersionInfoDescription=NEXORA Windows Installer
DefaultDirName={localappdata}\Programs\NEXORA
DefaultGroupName=NEXORA
OutputDir=output
OutputBaseFilename=NEXORA-Setup-v{#AppVersion}-Tester
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\NEXORA.exe
InfoAfterFile=TESTER_INSTRUCTIONS.txt
CloseApplications=yes
RestartApplications=no

[Files]
Source: "output\NEXORA\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{autodesktop}\NEXORA"; Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File ""{app}\launch-installed.ps1"""; WorkingDir: "{app}"; IconFilename: "{app}\NEXORA.exe"
Name: "{group}\NEXORA"; Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File ""{app}\launch-installed.ps1"""; WorkingDir: "{app}"; IconFilename: "{app}\NEXORA.exe"
Name: "{group}\Tester Instructions"; Filename: "{app}\TESTER_INSTRUCTIONS.txt"
Name: "{group}\Readme"; Filename: "{app}\README.md"
Name: "{group}\Uninstall NEXORA"; Filename: "{uninstallexe}"

[Run]
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File ""{app}\launch-installed.ps1"""; Description: "Launch NEXORA"; Flags: postinstall nowait skipifsilent

[UninstallDelete]
; User chats and feedback under {localappdata}\NEXORA are intentionally preserved.
