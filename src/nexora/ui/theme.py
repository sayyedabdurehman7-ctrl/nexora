"""Original NEXORA colors and reusable visual primitives."""

import flet as ft

PRIMARY = "#596FE8"


def palette(dark: bool) -> dict[str, str]:
    return {
        "bg": "#0B0B0D" if dark else "#F7F7F8",
        "surface": "#17191F" if dark else "#FFFFFF",
        "sidebar": "#101114" if dark else "#ECEEF2",
        "text": "#F4F4F5" if dark else "#17181C",
        "muted": "#A7AAB2" if dark else "#666B76",
        "border": "#2A2D34" if dark else "#DDE0E6",
        "accent": "#20232A" if dark else "#E9ECF8",
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
        border_radius=12,
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
