# Progress

## Stable tester release and connection recovery — 2026-09-12

- Added explicit `developer`, `tester`, and `production` build profiles. Tester mode forces deterministic Demo/Mock operation, removes provider/model/key data from public settings, and does not register developer-only configuration routes.
- Fixed the installed-launcher race that stopped the healthy backend immediately after opening the native Flet window. The launcher now waits for the real UI process, monitors backend health, performs three bounded restarts, accepts a user-requested restart signal, and closes its child backend when the UI exits.
- Added Starting, Connected, Reconnecting, Offline, and Recovery failed UI states with one compact status surface. Unsent input and the current conversation remain in the UI during recovery.
- Added UTF-8-safe rotating diagnostics with version, build profile, Windows/Python version, startup stage, safe exception category, correlation ID, stack locations, backend exit code, and health transitions. Secrets and message contents are excluded.
- Tester Settings now contains normal appearance, voice, language/privacy, memory, local export/clear, About, feedback, and basic connection controls. AI provider and model controls remain developer-only.
- Updated Windows CI to supported Python 3.11 and 3.12. Added tests for 20 Demo messages, English, Urdu, Hindi, emoji, long input, profile boundaries, unsupported model/parameter, timeout retry, invalid response, export, and clear.
- Verification before packaging: Ruff passed; **124 passed, 1 skipped**. See `docs/TESTER_RELEASE_v0.3.0.md` for the evidence and clean-machine limitations.

## Professional black workspace redesign — 2026-09-12

- Added the white `assets/NEXORA_Wordmark_White.svg` brand wordmark and removed the old blue-square mark from the chat experience.
- Reworked the dark palette to near-black, charcoal surfaces, subtle gray borders, and a restrained indigo primary action.
- Split the sidebar into fixed feature navigation and an independently scrolling Recent Chats area. Chat and message rows now have stable keys, short titles, active highlighting, and working rename/delete menus.
- Reduced the composer to a compact single-row layout with Attach, Microphone, answer mode, expandable message field, Stop, and Send controls.
- Added the collapsed-by-default NEXORA Workspace panel with Task Pulse, working quick actions, real task progress, and real pending-task context only.
- Reduced the chat title to a small top-bar label and removed the old assistant icon from empty and reply states.
- Verification: Ruff passes; **105 passed, 1 skipped**. The five-message regression check confirms unique stable message keys and independent Recent Chats scrolling. Responsive control-tree rendering covers 1440×900, 900×650, and 640×550. Native screenshot capture was unavailable in this session.

## NEXORA identity policy and provider privacy — 2026-09-11

- Added one central identity policy to every online AI request. NEXORA now identifies itself
  only as NEXORA and uses a fixed introduction and project description for direct identity
  questions.
- Added an output guard before chat persistence and speech playback. Unsafe self-identification
  triggers one automatic rewrite; a second failure returns the safe NEXORA fallback. Previously
  saved unsafe replies are also hidden and are never spoken.
- Removed backend provider names from the composer, chat fallback notices, task history, task
  details, activity surfaces, welcome text, and general user guidance. Provider configuration
  remains available only in Settings. Explicit user questions about AI services are answered
  honestly without changing NEXORA's identity.
- Verification: **104 passed, 1 skipped**. Identity tests cover six requested questions, one
  rewrite, repeated-failure fallback, saved-reply display protection, voice protection, loading
  text, and provider privacy in the composer. Ruff passes.

## Answer modes, stable replies, and voice settings — 2026-09-11

- Added persisted Low, Medium, and Strong / Deep Reply modes to every user and assistant
  message. Gemini receives mode-specific response instructions without changing the configured
  model. Strong mode requires structure and never invents sources; when chat has no live web
  retrieval it clearly says live sources are unavailable.
- Fixed reply flicker by keeping one empty assistant placeholder while the provider works and
  saving one merged final response. Cumulative or repeated long chunks are de-duplicated, and
  the UI no longer rebuilds for every token. Stop still cancels the provider task immediately.
- Reworked the composer with a larger prompt field, visible mode selector,
  microphone, Send, and response-only Stop button. The path-only attachment control is hidden.
- Added Voice Settings for Off / Push-to-Talk / Wake Word, microphone permission testing,
  assistant speech, voice testing, wake phrase, and saved preferences. Wake Word remains off by
  default and is labeled `Experimental - setup required`; selecting it shows a privacy warning
  and does not activate background listening because no reliable wake detector is installed.
- Verification: **94 passed, 1 skipped** before final visual QA; focused tests cover all modes,
  one-bubble cumulative streaming, Stop, Mock fallback, transient audio, voice settings, and
  wake-word defaults. Responsive Flet control construction passed at 1440×900, 900×650, and
  640×550. The Windows visual inspection helper was unavailable, so no native screenshot was
  captured in this check.

## Compact answer-mode control — 2026-09-11

Replaced the large answer-mode selector above the chat with a small dropdown inside the
composer. It shows the current choice and offers Low, Medium, and Strong / Deep Reply;
the selected internal mode continues to be saved with every message. The empty-chat
welcome state now fills and centers within the conversation area instead of appearing as
a padded list item, removing the large blank block and preserving usable space.

Visual inspection at a 748×608 viewport confirmed the welcome message, composer, provider
status, and Send action remain visible without overflow. The compact menu opens upward,
shows all three choices, closes after selection, and updates its label; selecting Strong /
Deep Reply was confirmed in the running interface.

## Application-local Gemini configuration — 2026-09-11

The Gemini key now loads from an absolute `.env` path beside the NEXORA launcher instead
of from the terminal's current working directory. Both development and installed launchers
set `NEXORA_APP_DIR`, while direct terminal startup resolves the source project directory
from `config.py`. `load_dotenv()` runs before settings are created, and copied keys are
trimmed of surrounding whitespace and quote marks without being printed or returned.

Added a safe diagnostic endpoint/function that returns only `Gemini key detected` or
`Gemini key not detected`. User-facing Gemini status is limited to `Gemini API: Connected`,
`Gemini API key: Not configured`, or `Gemini API error`; Mock remains the automatic fallback.

Verification: **90 passed, 1 skipped**; Ruff and dependency checks pass. Fake clients cover
configured, missing, invalid, offline, quota, and Mock fallback paths without using the real
key. A backend launched from `C:\Windows\Temp` detected the project-local key. The normal
launcher also detected it, and its live connection test returned `Gemini API: Connected`.
The key value was never displayed.

## Gemini and Mock provider cleanup — 2026-09-11

NEXORA now has exactly two chat providers: Gemini AI and Mock AI. Gemini is the primary
configured provider, while Mock supplies deterministic offline responses for tests and
for sessions without a Gemini key. Removed the unused local-model provider implementation,
configuration, dependency, selection path, UI option, error messages, documentation, and
tests. Older saved provider preferences are migrated to Gemini automatically.

Gemini fallback messages now clearly distinguish a missing key, exhausted free quota,
and an unavailable internet connection. The Settings screen contains only the provider
choice, key status, model, connection test, and save action. Secrets remain confined to
the ignored local `.env` file and never appear in API responses or UI logs.

The chat interface remains simple: New Chat and recent chats in the left sidebar, the
conversation and composer in the center, and an opt-in plan panel. Push-to-talk remains
local and transient through faster-whisper and pyttsx3.

Verification: the complete source, tests, documentation, environment example, and ignored
local preferences contain no references to the removed provider. Ruff and `pip check`
pass; the offline suite is **88 passed, 1 skipped**. The skipped test requires Windows
symlink privileges.

A live backend started with Gemini selected and no key. Sending `hi` displayed
“Gemini API key is not configured. NEXORA is using Mock mode.” Switching to Mock AI and
sending `hi` returned the scripted Mock response directly. The live Settings dropdown
showed exactly Gemini AI and Mock AI. No real Gemini request was made because this computer
does not have a Gemini key configured; the connected, quota, offline, and missing-key paths
are covered with fake SDK clients without using network or quota.

## Implemented foundation

- Flet UI, loopback FastAPI backend, plain Python core, and SQLite persistence.
- Saved multi-turn conversations with rename, delete, stop, retry, and reopen.
- Gemini streaming through Google's current Python SDK with a fake-client test boundary.
- Deterministic Mock conversation and goal planning without network access.
- Calculator, approved-workspace read-only files, PDF extraction, mock research, and
  controlled memory storage.
- Explicit task transitions, bounded retries and deadlines, verification, evidence,
  exact-action approvals, and cooperative cancellation.
- Push-to-talk recording, editable transcription, speech playback, mute, pause, and cancel.
- Clean user-facing task statuses with plans and technical details hidden by default.

## Current limits

Gemini needs a user-created key and internet access. Mock AI is intentionally scripted.
Speech hardware access and a live Gemini account must be checked on the user's computer.
Destructive filesystem tools, unrestricted desktop control, real-time voice, video, and
image generation are outside the current scope.
# Windows installer packaging — 2026-09-11

- Added a repeatable `installer/build.ps1` workflow that packages the Flet desktop UI and FastAPI backend into a self-contained Windows portable folder.
- Added `installer/launch-installed.ps1`, a safe per-user launcher, desktop/start-menu command file, Inno Setup script, and build instructions.
- Verified Flet and backend packaging completed successfully. The generated portable package is under `installer/output/NEXORA` (about 579 MB because optional voice/runtime libraries are bundled).
- Inno Setup was not installed on this machine, so `NEXORA-Setup.exe` could not be compiled here. Installing Inno Setup and rerunning `.\installer\build.ps1` will produce it.

## Hosted deployment preparation (2026-09-11)
- Added 
exora.web_app:app to serve FastAPI and Flet together for a hosted service.
- Added Dockerfile, ender.yaml, and docs/DEPLOY_RENDER.md for GitHub-connected Render deployment.
- API host/port and UI client now honor HOST, PORT, and NEXORA_ALLOWED_HOSTS.
- Verified hosted entrypoint imports successfully. Full pytest run is blocked by Windows temp-folder permissions in this workspace (38 passed, 67 setup errors).
- Added Hugging Face Docker Space metadata and deployment instructions as a no-card alternative.
- Built a complete per-user Windows installer at `installer/output/NEXORA-Setup.exe` using Inno Setup 6.7.3.

## Stable chat shell and About NEXORA — 2026-09-12

- Kept the app shell at the viewport boundary and clipped outer overflow. The sidebar has a stable cached control tree, while Recent Chats and the message history keep independent scroll areas.
- Preserved stable chat and message keys. Idle polling skips unchanged snapshots, token chunks are merged in the backend, and the UI receives one assistant placeholder followed by one final update instead of repainting for every token.
- Auto-scroll now activates only while the user is within 100 pixels of the newest message. A user reading older messages is not forced back to the bottom.
- Reduced the normal composer to a one-line input that expands only for multiline prompts. Attach, microphone, answer mode, input, and Send remain in one compact rounded bar.
- Added About NEXORA navigation, the approved project and creator introduction, and a validated optional Creator website setting stored in SQLite. Invalid or invented links are never shown.
- Added regression coverage for 60-message conversations, long answer text, unique stable keys, scroll policy, stable sidebar reuse, About prompts, creator-link validation, and saved About settings.
- Verification: Ruff passed and the offline suite completed with **115 passed, 1 skipped**. The skipped check requires Windows symlink privileges.

## Reliable Windows installer and tester feedback — 2026-09-12

- Diagnosed the shared-installer crash from the packaged executable: the build copied PyInstaller's `_internal` runtime directory into a flattened backend folder, so Windows could not load `python312.dll`. The build now creates the destination first and preserves the complete runtime tree.
- The installed launcher now uses absolute installation paths, creates writable per-user data under `%LOCALAPPDATA%\NEXORA`, selects an available loopback port, waits for `/health` with version and safe-mode checks, prevents duplicate launches, and stops only its own backend child.
- Added a professional Recovery window with Try Again, Open Diagnostic Folder, Copy Error Report, and Close. Startup logs record UTC timestamp, version, Windows version, stage, and sanitized traceback without API keys or message content.
- Fresh installs start in Mock Demo mode and copy a non-secret `.env.example` into the user data folder. Uninstall removes program files while leaving chats, settings, logs, feedback, and workspace data in Local AppData.
- Added a local tester feedback form with five rating levels, confusion/error/liked-feature/next-feature fields, optional sanitized diagnostics, clipboard copy, and JSON file export. No login or network is required.
- Added `TESTER_INSTRUCTIONS.txt` and `CHANGELOG-v0.2.0.txt`. The new installer includes desktop and Start Menu shortcuts, Readme, tester instructions, and an uninstall entry.
- Packaged backend smoke test passed from the installed folder: `/health` returned `status=ok`, `version=0.2.0`, `provider_status=demo`, and `safe_mode=true`. Recovery-window smoke test exited successfully. Final offline verification: **117 passed, 1 skipped**; Ruff passed.

## Stable tester release v0.3.0 — 2026-09-12

- Corrected the desktop launcher lifecycle so it waits for the actual UI process and keeps its owned local backend alive until the user closes NEXORA.
- Added managed startup on a free loopback port, version/profile health validation, bounded automatic backend recovery, one compact UI connection state, and privacy-safe rotating diagnostics.
- Added developer, tester, and production build profiles. Tester mode is locked to deterministic Demo mode; provider, model, key, connection-test controls, and their API routes are absent.
- Preserved chats and unsent input during recovery, added confirmed data clearing and local export, and kept user data under `%LOCALAPPDATA%\NEXORA` across uninstall/reinstall.
- Fixed the backend package layout and removed a duplicate Flet runtime that exceeded normal Windows installer path limits. The packaged backend includes `python312.dll` and starts without a system Python command.
- Final verification: Ruff passed; **124 tests passed, 1 skipped**; packaged `/health` passed; clean-folder install, backend crash recovery, reopen/history persistence, uninstall, reinstall, secret scan, and removed-provider search passed.
- Built `installer/output/NEXORA-Setup-v0.3.0-Tester.exe` (142.42 MiB), SHA-256 `FAF27B6252916498867B80EE162AC5F680FE06467AC0111A59441B1BC65A261D`.

## Demo self-introduction and secure online-service boundary v0.3.1 — 2026-09-12

- Diagnosed the tester screenshot: Demo mode was intentional because the build profile forces keyless offline operation, while the generic Demo echo branch ran before identity matching. The old generic echo is removed.
- Added semantic local intent handling for self-introduction, creator, capabilities, help, greetings, privacy, feedback, navigation, and feature questions. Unsupported general questions now explain the online-service limitation honestly.
- Added an authenticated HTTPS `NexoraServiceProvider` boundary for a future developer-operated service. Tester and production builds use it only when both a service URL and credential are provisioned; otherwise they remain Demo mode. Tokens can be read from Windows Credential Manager and are never logged or bundled.
- Added mode-aware health/settings status (`online`, `demo`, `reconnecting`, `offline`) while keeping provider details out of normal tester UI.
- Verification: Ruff passed; **126 passed, 1 skipped**; the v0.3.1 packaged backend returned the exact NEXORA introduction; secret and removed-provider scans passed.
- Built `installer/output/NEXORA-Setup-v0.3.1-Tester.exe` (142.46 MiB), SHA-256 `5C8D514A679CDD6F4F52E7EF5F68BD2C6ECD49A1D9C8A87C5D7591BD7444930C`. See `docs/TESTER_RELEASE_v0.3.1.md`.
## Truthful online-service readiness v0.3.2 — 2026-09-12

- Diagnosed the tester screenshot: the package was intentionally built as keyless Tester mode; the launcher forces `LLM_PROVIDER=mock`, the tester settings validator strips Gemini credentials, and no `NEXORA_SERVICE_URL`/service token is configured. Demo mode was therefore expected, not a failed Gemini health check.
- Kept the secure service boundary intact: Tester/Production use the authenticated HTTPS NEXORA service when both URL and credential are provisioned; otherwise they remain deterministic Demo mode.
- The launcher now waits for an online service to report healthy before treating a configured deployment as ready. Health responses include only safe mode/status fields, and developer diagnostics report redacted configuration and fallback state.
- Unsupported Demo questions now use the honest wording requested by the tester brief. No secret is bundled.
## Online-only transition v1.0.0 — 2026-09-12

- Desktop chat traffic now selects the authenticated `NexoraServiceProvider` for every build and does not return local chat replies when the service is unavailable.
- The launcher requires `/health` to report `mode=online` before opening the desktop UI; missing URL/token or an unhealthy service stops startup and preserves local data.
- Public settings no longer expose a Demo flag. The connection surface reports only ready, reconnecting, or temporarily offline states.
- Built `installer/output/NEXORA-Setup-v1.0.0.exe` without the repository `.env` file or personal credentials.
- Real online verification remains blocked until a developer provisions an HTTPS `NEXORA_SERVICE_URL` and matching `NEXORA_SERVICE_TOKEN`.
