import flet as ft

from nexora.ui.components.chat_composer import composer
from nexora.ui.components.chat_message import messages
from nexora.ui.theme import PRIMARY, card


def chat(app) -> ft.Control:
    colors = app.colors
    if app.state.task:
        body = messages(app, app.state.task)
    else:
        suggestions = [
            ("Research a topic", ft.Icons.TRAVEL_EXPLORE, None),
            ("Summarize a PDF", ft.Icons.DESCRIPTION_OUTLINED, None),
            ("Find a file", ft.Icons.FOLDER_OPEN, "list files"),
            ("Create a project plan", ft.Icons.ROUTE_OUTLINED, None),
            ("Continue my FYP", ft.Icons.SCHOOL_OUTLINED, None),
            ("View my saved memory", ft.Icons.BOOKMARK_BORDER, None),
        ]
        cards = []
        for title, icon, command in suggestions:
            cards.append(
                card(
                    ft.Column(
                        [
                            ft.Icon(icon, color=PRIMARY, size=22),
                            ft.Text(title, weight=ft.FontWeight.W_600, size=13),
                            ft.Text(
                                "Run: list files" if command else "Coming Soon",
                                size=11,
                                color=colors["muted"],
                            ),
                            ft.TextButton(
                                "Try it" if command else "Coming Soon",
                                disabled=not bool(command),
                                on_click=app.suggestion_handler(command) if command else None,
                            ),
                        ],
                        spacing=6,
                    ),
                    colors,
                    col={"xs": 12, "sm": 6, "lg": 4},
                )
            )
        body = [
            ft.Container(height=20),
            ft.Icon(ft.Icons.AUTO_AWESOME, size=36, color=PRIMARY),
            ft.Text("How can I help you today?", size=30, weight=ft.FontWeight.W_600),
            ft.Text("Give me a goal. I will plan, execute and verify it.", color=colors["muted"]),
            ft.Text(
                "Start with a supported mock command. General chat arrives with AI providers.",
                size=12,
                color=colors["muted"],
            ),
            ft.ResponsiveRow(cards, spacing=12, run_spacing=12),
            ft.Row(
                [
                    ft.TextButton(
                        "Try a calculation", on_click=app.suggestion_handler("calculate 2 + 3 * 4")
                    ),
                    ft.TextButton(
                        "Explore approval", on_click=app.suggestion_handler("approval demo")
                    ),
                ],
                wrap=True,
            ),
        ]
    return ft.Column(
        [
            ft.ListView(body, expand=True, spacing=18, padding=ft.Padding.only(bottom=20)),
            composer(app),
        ],
        expand=True,
        spacing=12,
    )
