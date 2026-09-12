"""Truthful project information shown inside NEXORA."""

import flet as ft

from nexora.identity import NEXORA_PROJECT_DESCRIPTION
from nexora.ui.theme import card


def about(app) -> ft.Control:
    colors = app.colors
    website = app.state.settings.get("creator_website", "")
    details: list[ft.Control] = [
        ft.Text("About NEXORA", size=24, weight=ft.FontWeight.W_600),
        ft.Text(NEXORA_PROJECT_DESCRIPTION, size=15),
        ft.Text("Creator", size=12, color=colors["muted"], weight=ft.FontWeight.W_600),
        ft.Text("Sayed Abdur Rehman", size=15, weight=ft.FontWeight.W_600),
        ft.Text("Computer Science final-year project", size=13, color=colors["muted"]),
    ]
    if website:
        details.append(
            ft.TextButton(
                "Creator website",
                icon=ft.Icons.OPEN_IN_NEW,
                url=website,
                tooltip="Open creator website",
            )
        )
    return ft.Container(
        card(ft.Column(details, spacing=14), colors),
        alignment=ft.Alignment.TOP_CENTER,
        padding=ft.Padding.only(top=12),
        expand=True,
    )
