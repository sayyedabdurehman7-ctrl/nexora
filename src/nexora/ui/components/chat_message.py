import flet as ft

from nexora.ui.state import TERMINAL, label, response_text, timestamp
from nexora.ui.theme import PRIMARY, badge


def messages(app, task: dict) -> list[ft.Control]:
    colors = app.colors
    text = response_text(task)
    user = ft.Container(
        ft.Column(
            [
                ft.Text("YOU", size=10, color=PRIMARY, weight=ft.FontWeight.BOLD),
                ft.Text(task["user_text"], selectable=True, size=app.text_size),
                ft.Text(timestamp(task["created_at"]), size=10, color=colors["muted"]),
            ]
        ),
        padding=18,
        border_radius=16,
        bgcolor=colors["accent"],
    )
    actions = [
        ft.IconButton(
            ft.Icons.COPY_OUTLINED, tooltip="Copy response", on_click=app.copy_handler(text)
        ),
        ft.IconButton(
            ft.Icons.THUMB_UP_OUTLINED, disabled=True, tooltip="Save feedback · Coming Soon"
        ),
        ft.IconButton(
            ft.Icons.THUMB_DOWN_OUTLINED, disabled=True, tooltip="Save feedback · Coming Soon"
        ),
    ]
    if task["status"] in TERMINAL:
        actions.append(
            ft.TextButton(
                "Run again",
                icon=ft.Icons.REPLAY,
                on_click=app.retry_handler(task),
                tooltip="Create a fresh task",
            )
        )
    assistant = ft.Container(
        ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(ft.Icons.AUTO_AWESOME, color=PRIMARY, size=18),
                        ft.Text("NEXORA", weight=ft.FontWeight.BOLD, size=12),
                        badge(label(task["status"])),
                        ft.ProgressRing(
                            width=14,
                            height=14,
                            stroke_width=2,
                            visible=task["status"] not in TERMINAL,
                        ),
                    ]
                ),
                ft.Markdown(
                    text,
                    selectable=True,
                    extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
                    on_tap_link=app.source_link,
                ),
                ft.Text(
                    timestamp(task.get("ended_at") or task["created_at"]),
                    size=10,
                    color=colors["muted"],
                ),
                ft.Row(actions, wrap=True),
            ],
            spacing=14,
        ),
        padding=18,
    )
    return [user, assistant]
