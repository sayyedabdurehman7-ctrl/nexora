# Chat and push-to-talk voice

NEXORA uses Gemini AI for online conversation, Mock AI for free offline testing, SQLite
for saved chats, faster-whisper for speech recognition, and pyttsx3 for speech playback.

## Use

- Start **New Chat**, send text, or reopen a previous conversation from the sidebar.
- Rename or delete the current conversation from **More**.
- Use **Stop** to cancel a running response.
- Choose **Low**, **Medium**, or **Strong / Deep Reply** from the small menu beside the microphone.
- Open **View Plan** for action requests.
- Press the microphone once to record and again to stop.
- Edit the transcript before sending it.
- Turn spoken answers on in **Settings → Voice Settings**.

Low gives a concise response, Medium gives a normal explanation, and Strong gives a
structured analysis. Strong mode does not invent citations. When chat has no live web
retrieval, it says that live sources are unavailable.

Audio stays in memory except for a temporary synthesis file that is removed after use or
cancellation. The microphone never listens until its button is pressed.

Wake Word is off by default and currently appears as **Experimental - setup required**.
Selecting it shows a privacy warning and keeps Push-to-Talk active because a reliable local
wake detector is not installed. No background microphone is started.

Supported task commands include `calculate`, `list files`, `read`, `search`,
`research`, `summarize pdf`, and `approval demo`. Destructive file actions remain
blocked.

Configuration and Windows startup steps are in [SETUP.md](SETUP.md).
