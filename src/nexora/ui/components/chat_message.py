import flet as ft

from nexora.ui.state import TERMINAL, response_text, simple_status
from nexora.ui.theme import PRIMARY


def messages(app, task: dict) -> list[ft.Control]:
    colors = app.colors
    text = response_text(task)
    user = ft.Container(
        ft.Column(
            [
                ft.Text("YOU", size=10, color=PRIMARY, weight=ft.FontWeight.BOLD),
                ft.Text(task["user_text"], selectable=True, size=app.text_size),
            ]
        ),
        padding=18,
        border_radius=16,
        bgcolor=colors["accent"],
    )
    actions = [
        ft.TextButton("Copy Answer", icon=ft.Icons.COPY_OUTLINED, on_click=app.copy_handler(text)),
        ft.TextButton("View Plan", icon=ft.Icons.FORMAT_LIST_NUMBERED, on_click=app.open_plan),
    ]
    if task["status"] in TERMINAL:
        actions.append(
            ft.TextButton(
                "Retry",
                icon=ft.Icons.REPLAY,
                on_click=app.retry_handler(task),
            )
        )
    assistant = ft.Container(
        ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(ft.Icons.AUTO_AWESOME, color=PRIMARY, size=18),
                        ft.Text("NEXORA", weight=ft.FontWeight.BOLD, size=12),
                        ft.ProgressRing(
                            width=14,
                            height=14,
                            stroke_width=2,
                            visible=task["status"] not in TERMINAL,
                        ),
                    ]
                ),
                ft.Text(simple_status(task["status"]), color=PRIMARY, weight=ft.FontWeight.W_600),
                ft.Markdown(
                    text,
                    selectable=True,
                    extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
                    on_tap_link=app.source_link,
                ),
                ft.Row(actions, wrap=True),
            ],
            spacing=14,
        ),
        padding=18,
    )
    return [user, assistant]
