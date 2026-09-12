"""Hosted entrypoint combining the FastAPI API and Flet web UI."""

import flet.fastapi as flet_fastapi

from nexora.api.app import create_app
from nexora.ui.app import build

app = create_app()
app.mount("/", flet_fastapi.app(build, app_name="NEXORA", app_short_name="NEXORA"))
