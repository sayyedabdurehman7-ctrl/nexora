"""Stable NEXORA navigation and independently scrolling recent chats."""

from pathlib import Path

import flet as ft

from nexora.config import application_dir

FEATURES = [
    ("Projects", "Projects", ft.Icons.FOLDER_OUTLINED),
    ("Tasks", "Task history", ft.Icons.CHECKLIST_OUTLINED),
    ("Research", "Research", ft.Icons.TRAVEL_EXPLORE_OUTLINED),
    ("Files", "Generated files", ft.Icons.INSERT_DRIVE_FILE_OUTLINED),
    ("Memory", "Memory", ft.Icons.BOOKMARK_BORDER),
    ("Tools", "Tools", ft.Icons.GRID_VIEW_ROUNDED),
    ("Settings", "Settings", ft.Icons.SETTINGS_OUTLINED),
]


def _wordmark(compact: bool) -> ft.Control:
    source = Path(application_dir()) / "assets" / "NEXORA_Wordmark_White.svg"
    return ft.Image(
        src=str(source),
        width=42 if compact else 150,
        height=34,
        fit=ft.BoxFit.CONTAIN,
        tooltip="NEXORA",
    )


def _nav_button(app, label: str, screen: str, icon, compact: bool) -> ft.Control:
    selected = app.state.screen == screen
    content = (
        ft.IconButton(icon, tooltip=label, on_click=app.navigate_handler(screen))
        if compact
        else ft.TextButton(
            label,
            icon=icon,
            tooltip=label,
            on_click=app.navigate_handler(screen),
            width=216,
            style=ft.ButtonStyle(
                alignment=ft.Alignment.CENTER_LEFT,
                padding=ft.Padding.symmetric(horizontal=12, vertical=7),
            ),
        )
    )
    return ft.Container(
        content,
        key=f"nav-{screen.lower().replace(' ', '-')}",
        border_radius=9,
        bgcolor=app.colors["accent"] if selected else None,
    )


def _chat_row(app, conversation: dict) -> ft.Control:
    chat_id = conversation["id"]
    title = (conversation.get("title") or "New conversation").strip()
    short_title = title if len(title) <= 24 else title[:23].rstrip() + "…"
    active = bool(app.conversation and app.conversation.get("id") == chat_id)
    return ft.Container(
        ft.Row(
            [
                ft.TextButton(
                    short_title,
                    tooltip=title,
                    on_click=app.chat_handler(chat_id),
                    expand=True,
                    style=ft.ButtonStyle(
                        alignment=ft.Alignment.CENTER_LEFT,
                        padding=ft.Padding.symmetric(horizontal=8, vertical=5),
                    ),
                ),
                ft.PopupMenuButton(
                    icon=ft.Icons.MORE_HORIZ,
                    tooltip="Chat actions",
                    icon_size=17,
                    items=[
                        ft.PopupMenuItem(
                            content=ft.Text("Rename"),
                            icon=ft.Icons.EDIT_OUTLINED,
                            on_click=app.rename_chat_handler(chat_id, title),
                        ),
                        ft.PopupMenuItem(
                            content=ft.Text("Delete"),
                            icon=ft.Icons.DELETE_OUTLINE,
                            on_click=app.delete_chat_handler(chat_id),
                        ),
                    ],
                ),
            ],
            spacing=0,
        ),
        key=f"chat-{chat_id}",
        border_radius=9,
        bgcolor=app.colors["accent"] if active else None,
        padding=ft.Padding.only(right=2),
    )


def sidebar(app, compact: bool) -> ft.Control:
    colors = app.colors
    header = ft.Container(
        _wordmark(compact),
        height=48,
        alignment=ft.Alignment.CENTER if compact else ft.Alignment.CENTER_LEFT,
        padding=ft.Padding.only(left=4),
    )
    new_chat = (
        ft.IconButton(ft.Icons.ADD_COMMENT_OUTLINED, tooltip="New Chat", on_click=app.new_task)
        if compact
        else ft.Button(
            "New Chat",
            icon=ft.Icons.ADD,
            on_click=app.new_task,
            height=40,
            width=216,
            tooltip="Start a new conversation",
        )
    )
    feature_controls = [new_chat]
    feature_controls.extend(_nav_button(app, label, screen, icon, compact) for label, screen, icon in FEATURES)

    controls: list[ft.Control] = [header, ft.Column(feature_controls, spacing=3)]
    if compact:
        controls.extend(
            [
                ft.Container(expand=True),
                ft.IconButton(ft.Icons.MENU, tooltip="Expand sidebar", on_click=app.toggle_sidebar),
            ]
        )
    else:
        conversations = getattr(app, "conversations", [])[:40]
        recent = [_chat_row(app, item) for item in conversations]
        controls.extend(
            [
                ft.Divider(color=colors["border"], height=16),
                ft.Text("Recent Chats", size=12, color=colors["muted"], weight=ft.FontWeight.W_600),
                ft.Column(
                    recent or [ft.Text("Your conversations will appear here.", size=12, color=colors["muted"])],
                    key="recent-chats",
                    expand=True,
                    scroll=ft.ScrollMode.AUTO,
                    spacing=2,
                ),
                ft.IconButton(ft.Icons.MENU_OPEN, tooltip="Collapse sidebar", on_click=app.toggle_sidebar),
            ]
        )
    return ft.Container(
        ft.Column(controls, key="sidebar-content", spacing=8, expand=True),
        key="nexora-sidebar",
        width=68 if compact else 248,
        padding=ft.Padding.symmetric(horizontal=12, vertical=10),
        bgcolor=colors["sidebar"],
        border=ft.Border.only(right=ft.BorderSide(1, colors["border"])),
    )
