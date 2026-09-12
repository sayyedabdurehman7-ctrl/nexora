# NEXORA v0.3.0 Tester release report

## Evidence and root causes

The previous packaged UI launched successfully, but PowerShell did not wait for the native GUI process. The launcher continued into shutdown and stopped the backend it owned. The surviving Flet window then displayed `App connection: Not connected`, `Connection lost`, and `NEXORA cannot connect to its local service`. The local diagnostic log records a successful backend health check immediately followed by the launcher's mistaken `The desktop interface closed with an error` decision. This explains the connection screenshots and is fixed by starting and monitoring the UI process explicitly.

An earlier packaging defect also flattened PyInstaller's backend `_internal` directory. That made Windows unable to load `python312.dll`. The build now preserves the complete backend runtime tree and verifies the packaged backend health endpoint.

The Settings screenshot exposed Gemini provider, model, and key controls because the old package had no build-profile boundary. Tester mode now forces deterministic Mock/Demo operation, omits those fields from `/api/v1/settings`, and does not register provider-changing or Gemini diagnostic routes. The tester UI only says `Demo mode`.

The reported phrase described as “lexical unsupported” is not present in the supplied screenshots, the available tester report, the repository, or the available local logs. Its exact old traceback cannot be recovered from those artifacts, so no exact cause is claimed. The v0.3.0 build validates model strings, maps HTTP 400 unsupported/unknown-parameter failures to a safe provider error, records a privacy-safe exception category and stack location, and cannot reach Gemini in Tester mode. A future occurrence will therefore be captured without exposing prompts or keys.

## Verification performed on the build computer

- Ruff: passed.
- Offline suite: 124 passed, 1 skipped. The skipped test requires Windows symlink privileges.
- Demo conversation: 20 messages passed and persisted in SQLite.
- Text: English, Urdu, Hindi, emoji, and a 2,000-character message passed.
- Tester profile: provider/model/key fields absent; developer-only routes returned 404.
- Provider errors: missing configuration, invalid model, unsupported parameter, network timeout retry, quota, and empty response covered using fake clients.
- Data export and confirmed local-data clearing passed.

The installer is also smoke-tested from a clean destination and clean Local AppData test folder on this Windows computer. This is not a separate physical computer or a clean virtual machine, so hardware microphone behavior, antivirus reputation, and machines with no development tools remain external tester checks.

### Final packaged-release results

| Check | Result |
| --- | --- |
| Installer compilation | Pass |
| Silent install into a fresh folder | Pass |
| Packaged backend `/health` | Pass: v0.3.0, tester, demo |
| Provider/model/key fields hidden | Pass |
| Developer-only provider route | Pass: HTTP 404 |
| First-run database creation | Pass |
| Forced backend termination and automatic restart | Pass; process ID changed and the UI remained open |
| Close, reopen, and SQLite history persistence | Pass |
| Uninstall and reinstall | Pass |
| Preserve user database during uninstall | Pass |
| Installer secret scan | Pass: no key-shaped strings and no `.env` file |
| Removed-provider repository scan | Pass: zero active references |
| English, Urdu, Hindi, emoji, 2,000-character input, and 20 messages | Pass in the offline suite |
| Network disconnect/reconnect on separate hardware | Not run; backend-loss recovery was exercised locally |
| Real microphone on the tester's computer | Not run on that hardware |
| Windows machine with no Python installed | Not available; both packaged executables were run directly and contain their own Python runtime |

Final installer: `NEXORA-Setup-v0.3.0-Tester.exe` (149,342,955 bytes / 142.42 MiB).

SHA-256: `FAF27B6252916498867B80EE162AC5F680FE06467AC0111A59441B1BC65A261D`

## Build

```powershell
.\installer\build.ps1 -Profile tester
```

The tester installs per user, creates desktop and Start Menu shortcuts, needs no administrator access, and stores writable data under `%LOCALAPPDATA%\NEXORA`.
