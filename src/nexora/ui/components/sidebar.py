import flet as ft

from nexora.ui.state import timestamp
from nexora.ui.theme import PRIMARY

NAV = [
    ("Chat", ft.Icons.CHAT_BUBBLE_OUTLINE),
    ("Projects", ft.Icons.FOLDER_OUTLINED),
    ("Generated files", ft.Icons.INSERT_DRIVE_FILE_OUTLINED),
    ("Memory", ft.Icons.BOOKMARK_BORDER),
    ("Tools", ft.Icons.GRID_VIEW_ROUNDED),
    ("Task history", ft.Icons.HISTORY),
    ("Settings", ft.Icons.SETTINGS_OUTLINED),
]


def sidebar(app, compact: bool) -> ft.Control:
    colors, state = app.colors, app.state
    controls = [
        ft.Row(
            [
                ft.Container(
                    ft.Text("N", size=23, color="white", weight=ft.FontWeight.BOLD),
                    bgcolor=PRIMARY,
                    padding=10,
                    border_radius=12,
                ),
                *([] if compact else [ft.Text("NEXORA", size=20, weight=ft.FontWeight.BOLD)]),
            ]
        ),
        ft.IconButton(ft.Icons.ADD, tooltip="New Task", on_click=app.new_task)
        if compact
        else ft.Button(
            "New Task",
            icon=ft.Icons.ADD,
            on_click=app.new_task,
            width=220,
            tooltip="Start a fresh goal",
        ),
    ]
    for name, icon in NAV:
        controls.append(
            ft.Container(
                ft.IconButton(icon, tooltip=name, on_click=app.navigate_handler(name))
                if compact
                else ft.TextButton(name, icon=icon, on_click=app.navigate_handler(name), tooltip=name, width=218),
                bgcolor=colors["accent"] if state.screen == name else None,
                border_radius=10,
            )
        )
    if not compact:
        controls += [
            ft.Divider(color=colors["border"]),
            ft.Text("RECENT CONVERSATIONS", size=10, color=colors["muted"]),
            ft.TextField(
                hint_text="Search conversations",
                prefix_icon=ft.Icons.SEARCH,
                value=state.search,
                dense=True,
                on_change=app.search_changed,
            ),
        ]
        recent = []
        for task in state.filtered_tasks()[:20]:
            active = state.task and state.task["id"] == task["id"]
            recent.append(
                ft.Container(
                    ft.Column(
                        [
                            ft.TextButton(
                                task["user_text"][:32],
                                on_click=app.open_handler(task["id"]),
                                tooltip=task["user_text"][:200],
                            ),
                            ft.Text(
                                timestamp(task.get("ended_at") or task["created_at"]),
                                size=10,
                                color=colors["muted"],
                            ),
                        ],
                        spacing=0,
                    ),
                    padding=6,
                    border_radius=10,
                    bgcolor=colors["accent"] if active else None,
                )
            )
        controls.append(
            ft.Column(
                recent or [ft.Text("Your tasks will appear here.", size=12, color=colors["muted"])],
                expand=True,
                scroll=ft.ScrollMode.AUTO,
            )
        )
    else:
        controls.append(ft.Container(expand=True))
    controls += [
        ft.IconButton(
            ft.Icons.MENU_OPEN,
            tooltip="Expand sidebar" if compact else "Collapse sidebar",
            on_click=app.toggle_sidebar,
        ),
        ft.Row(
            [
                ft.CircleAvatar(content=ft.Text("L"), radius=15, bgcolor=colors["accent"]),
                *([] if compact else [ft.Text("Local workspace\nPersonal · no account", size=11)]),
            ]
        ),
    ]
    return ft.Container(
        ft.Column(controls, spacing=8, expand=True),
        width=76 if compact else 250,
        padding=14,
        bgcolor=colors["sidebar"],
    )
