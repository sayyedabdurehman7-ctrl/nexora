# Progress

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
