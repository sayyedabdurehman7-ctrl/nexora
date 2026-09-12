# Build the Windows installer

From the NEXORA project folder, run:

```powershell
.\installer\build.ps1 -Profile tester
```

The script creates a portable package in `installer\output\NEXORA`. If Inno Setup is installed, it also creates `installer\output\NEXORA-Setup-v0.3.0-Tester.exe`.

If Inno Setup is not installed, use the portable folder or install Inno Setup, then run the build script again. The installer uses a per-user folder and does not require administrator access. Tester builds always use keyless Demo mode. Developer settings belong in `%LOCALAPPDATA%\NEXORA\.env`, never in the installed program folder.

The finished tester installer is `installer\output\NEXORA-Setup-v0.3.1-Tester.exe`. Send this single file to another Windows user. They double-click it, accept the default install folder, and use the NEXORA desktop shortcut. The app starts in Demo mode and does not require Python, Git, or an API key.
