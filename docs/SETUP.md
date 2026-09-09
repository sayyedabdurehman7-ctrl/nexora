# Windows PowerShell setup

Already installed? Double-click **Open NEXORA.bat** in the project folder. It starts
the backend, waits until it is ready, and opens the app. Keep the launcher window open.
When the UI exits, the launcher stops only the backend it started itself.

Use Python 3.11 or newer. Open PowerShell in the `nexora` project folder.
These commands install only the Phase 1 dependencies and development checks.

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e '.[dev]'
Copy-Item .env.example .env
```

Copy `.env.example` only if you do not already have `.env`. Defaults use the free mock provider.
No API key is needed. Put secrets only in local `.env` when a later phase supports them.
Do not share `.env`, `data`, logs or the virtual environment.

Start the backend in the first terminal, from this project folder:

```powershell
.\.venv\Scripts\nexora-api.exe
```

Start the UI in a second terminal, from the same folder:

```powershell
.\.venv\Scripts\nexora-ui.exe
```

Flet may download its desktop runtime on the first launch. After that, Phase 1 needs
no internet. If that download is unavailable, the API and its local interactive docs
at http://127.0.0.1:8000/docs can still be used.

The backend creates `data/user_files` and `data/nexora.db` on startup. Put approved
UTF-8 `.txt`, `.md`, `.csv`, `.json` or `.log` files in `data/user_files`.
Try `calculate 2 + 3`, `list files`, or `approval demo`. Stop the servers with Ctrl+C.

Check the backend and run quality checks:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
```

If Windows' `python` or `py` opens the Store or fails, use an installed Python executable's
full path for the first command. No activation or PowerShell execution-policy change is needed.
If pip hangs writing its cache in a restricted environment, set `$env:PIP_NO_CACHE_DIR='1'`
and repeat the install command. This project was verified with a bundled Python 3.12 runtime.
Use only one backend process; do not add `--workers` or expose the port outside loopback.

Cloud, PDF, browser, voice and retrieval extras are defined in pyproject.toml but are not
part of Phase 1. Installing them does not implement those features.
