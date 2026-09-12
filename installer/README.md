# Build the Windows installer

From the NEXORA project folder, run:

```powershell
.\installer\build.ps1
```

The script creates a portable package in `installer\output\NEXORA`. If Inno Setup is installed, it also creates `installer\output\NEXORA-Setup-v0.2.0.exe`.

If Inno Setup is not installed, use the portable folder or install Inno Setup, then run the build script again. The installer uses a per-user folder and does not require administrator access. It includes `.env.example`; copy it to `.env` in the installed NEXORA folder before adding your own settings.

The finished installer is `installer\output\NEXORA-Setup-v0.2.0.exe`. Send this single file to another Windows user. They double-click it, accept the default install folder, and use the NEXORA desktop shortcut. The app starts in Mock mode and does not require Python or Git.
