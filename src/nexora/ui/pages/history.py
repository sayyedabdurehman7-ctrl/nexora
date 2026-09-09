import flet as ft

from nexora.ui.state import LABELS, duration, label, timestamp
from nexora.ui.theme import badge, card, coming, empty


def history(app) -> ft.Control:
    controls = [
        ft.Text("Task history", size=28, weight=ft.FontWeight.W_600),
        ft.Text("Your real, locally saved runs. Open one to inspect its plan and evidence."),
        ft.Row(
            [
                ft.Dropdown(
                    label="Status",
                    width=180,
                    value=app.state.status_filter,
                    options=[ft.DropdownOption("All")]
                    + [ft.DropdownOption(key, text=value) for key, value in LABELS.items()],
                    on_select=app.filter_status,
                ),
                ft.TextField(
                    label="Created date (YYYY-MM-DD)",
                    width=220,
                    value=app.state.date_filter,
                    on_change=app.filter_date,
                ),
                coming("Project filter"),
            ],
            wrap=True,
        ),
    ]
    for task in app.state.filtered_tasks():
        controls.append(
            card(
                ft.Column(
                    [
                        ft.Text(task["user_text"], size=16, weight=ft.FontWeight.W_600),
                        ft.Row(
                            [
                                badge(label(task["status"])),
                                ft.Text(timestamp(task["created_at"]), size=12),
                                ft.Text(
                                    f"{duration(task)} · {len(task['plan']['steps'])} steps"
                                    f" · {task['provider']}",
                                    size=12,
                                ),
                            ],
                            wrap=True,
                        ),
                        ft.Row(
                            [
                                ft.TextButton(
                                    "Open details", on_click=app.open_handler(task["id"])
                                ),
                                ft.TextButton("Run again", on_click=app.retry_handler(task)),
                                coming("Delete history"),
                            ],
                            wrap=True,
                        ),
                    ]
                ),
                app.colors,
            )
        )
    if not app.state.filtered_tasks():
        controls.append(
            empty(
                ft.Icons.HISTORY,
                "No matching tasks",
                "Start a new goal or change your filters.",
                app.colors,
            )
        )
    return ft.ListView(controls, expand=True, spacing=16)
