import flet as ft

from nexora.ui.state import TERMINAL
from nexora.ui.theme import PRIMARY


def composer(app) -> ft.Control:
    state, colors = app.state, app.colors
    active = state.task and state.task["status"] not in TERMINAL
    app.goal.disabled = state.busy
    return ft.Container(
        ft.Column(
            [
                app.goal,
                ft.Row(
                    [
                        ft.IconButton(
                            ft.Icons.ATTACH_FILE, disabled=True, tooltip="Attach file · Coming Soon"
                        ),
                        ft.IconButton(
                            ft.Icons.MIC_NONE, disabled=True, tooltip="Voice · Coming Soon"
                        ),
                        ft.TextButton(
                            "Tools",
                            icon=ft.Icons.TUNE,
                            on_click=app.navigate_handler("Tools"),
                            tooltip="View available tools; the mock planner selects automatically",
                        ),
                        ft.Container(expand=True),
                        ft.IconButton(
                            ft.Icons.STOP_CIRCLE_OUTLINED,
                            tooltip="Stop current task",
                            on_click=app.stop,
                            visible=bool(active),
                            icon_color="#DC5656",
                        ),
                        ft.Button(
                            "Run",
                            icon=ft.Icons.ARROW_UPWARD,
                            on_click=app.submit,
                            disabled=state.busy or not state.connected,
                            color="white",
                            bgcolor=PRIMARY,
                            tooltip="Send goal and run its safe plan",
                        ),
                    ]
                ),
                ft.Text(
                    "Mock · Free, local commands   /   Enter to run · Shift+Enter for a new line",
                    size=10,
                    color=colors["muted"],
                ),
            ],
            spacing=4,
        ),
        padding=14,
        border_radius=18,
        bgcolor=colors["surface"],
        border=ft.Border.all(1, colors["border"]),
    )
