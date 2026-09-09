"""Original NEXORA colors and reusable visual primitives."""

import flet as ft

PRIMARY = "#5265DC"


def palette(dark: bool) -> dict[str, str]:
    return {
        "bg": "#111827" if dark else "#FAFBFE",
        "surface": "#182235" if dark else "#FFFFFF",
        "sidebar": "#131D2E" if dark else "#F0F3FA",
        "text": "#E9EEF9" if dark else "#202C46",
        "muted": "#A8B6CC" if dark else "#64738D",
        "border": "#2E3D55" if dark else "#E1E7F1",
        "accent": "#273754" if dark else "#E9EDFF",
    }


def badge(label: str, color: str = PRIMARY) -> ft.Container:
    return ft.Container(
        ft.Text(label, size=12, color=ft.Colors.ON_SURFACE, weight=ft.FontWeight.W_600),
        padding=ft.Padding.symmetric(horizontal=9, vertical=5),
        border_radius=8,
        bgcolor=ft.Colors.with_opacity(0.10, color),
    )


def card(content: ft.Control, colors: dict, **kwargs) -> ft.Container:
    return ft.Container(
        content,
        padding=18,
        bgcolor=colors["surface"],
        border_radius=16,
        border=ft.Border.all(1, colors["border"]),
        **kwargs,
    )


def empty(icon, title: str, description: str, colors: dict) -> ft.Control:
    return card(
        ft.Column(
            [
                ft.Icon(icon, color=PRIMARY, size=32),
                ft.Text(title, size=21, weight=ft.FontWeight.W_600),
                ft.Text(description, color=colors["muted"], size=14),
            ],
            spacing=14,
        ),
        colors,
    )


def coming(label: str) -> ft.Button:
    return ft.Button(
        f"{label} · Coming Soon",
        disabled=True,
        tooltip="The backend for this feature is not implemented yet.",
    )
