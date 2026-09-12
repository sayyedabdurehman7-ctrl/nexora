# Windows setup

NEXORA supports Gemini AI for online chat and Mock AI for free offline testing. Chat
history stays in the local SQLite database. Your Gemini key stays only in the ignored
`.env` file on this computer.

NEXORA resolves this `.env` from the application or launcher folder, so it works the same
way from `Open NEXORA.bat`, PowerShell, Command Prompt, or a desktop shortcut. It does not
use the terminal's current folder to find the key.

## First setup

For a friend or tester, use `installer\output\NEXORA-Setup-v0.2.0.exe`. They do not need
Python, Git, a terminal, or an API key. The installer creates the desktop shortcut and
starts Demo mode automatically. `Open NEXORA.bat` is retained only as an optional
developer diagnostic launcher.

Open PowerShell in the NEXORA project folder and run:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev,voice]"
Copy-Item .env.example .env
```

Create your own key in [Google AI Studio](https://aistudio.google.com/app/apikey). Never
paste the key into chat. Open this local file in Notepad:

```text
C:\Users\aj\Documents\Codex\2026-09-09\files-mentioned-by-the-user-nexora\outputs\nexora\.env
```

Set these values:

```dotenv
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_key_from_google_ai_studio
GEMINI_MODEL=your_model_id_from_google_ai_studio
DATABASE_URL=sqlite:///data/nexora.db
NEXORA_SAFE_MODE=true
```

Save the file, close older NEXORA windows, then double-click `Open NEXORA.bat`.

## Provider settings (developer build only)

Open **More → Settings**. Choose **Gemini AI** or **Mock AI**, enter the Gemini model,
and select **Save Settings**. **Test Gemini Connection** makes one small request and
uses your available Gemini quota. These controls are not included in Tester or Production settings.

Without a key, NEXORA explains that it is using Mock mode. Mock AI needs no key or
internet and produces scripted responses for testing.

## Voice

Push-to-talk uses faster-whisper for speech recognition and pyttsx3 for playback. Audio
is temporary and recording begins only after the microphone button is pressed. The first
transcription can download the configured speech model.

## Development checks

```powershell
.\.venv\Scripts\python.exe -m ruff check src tests
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
.\.venv\Scripts\python.exe -m pip check
```

Tests use fake Gemini and audio clients. They do not use a real key, internet, or quota.
