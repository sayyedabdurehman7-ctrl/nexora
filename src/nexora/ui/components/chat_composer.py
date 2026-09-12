import flet as ft

from nexora.ui.state import TERMINAL
from nexora.ui.theme import PRIMARY


def _voice_status(voice: dict) -> str:
    if voice.get("error"):
        return "Voice is unavailable. Check Voice settings and try again."
    return {
        "starting": "Starting microphone…",
        "recording": "Recording… Press the microphone again when finished.",
        "transcribing": "Turning your voice into text…",
        "ready": "Your transcript is ready. Edit it above, then press Send.",
    }.get(voice.get("phase"), "")


def _modern_composer(app, active: bool) -> ft.Control:
    state, colors, voice = app.state, app.colors, app.voice
    voice_status = _voice_status(voice)
    mode_labels = {
        "light": "Low",
        "medium": "Medium",
        "strong": "Strong / Deep Reply",
    }
    mode_menu = ft.PopupMenuButton(
        content=ft.Container(
            ft.Row(
                [
                    ft.Text(mode_labels.get(app.answer_mode, "Medium"), size=13),
                    ft.Icon(ft.Icons.ARROW_DROP_DOWN, size=17),
                ],
                spacing=1,
                tight=True,
            ),
            padding=ft.Padding.symmetric(horizontal=9, vertical=6),
            border_radius=10,
            border=ft.Border.all(1, colors["border"]),
            tooltip="Choose answer detail",
        ),
        tooltip="Choose answer detail",
        menu_position=ft.PopupMenuPosition.OVER,
        menu_padding=4,
        items=[
            ft.PopupMenuItem(content=ft.Text("Low"), height=38, on_click=app.answer_mode_handler("light")),
            ft.PopupMenuItem(content=ft.Text("Medium"), height=38, on_click=app.answer_mode_handler("medium")),
            ft.PopupMenuItem(
                content=ft.Text("Strong / Deep Reply"),
                height=38,
                on_click=app.answer_mode_handler("strong"),
            ),
        ],
    )
    controls = [
        ft.Container(height=0, visible=False),
        ft.Row(
            [
                ft.IconButton(
                    ft.Icons.ATTACH_FILE,
                    tooltip="Attach a workspace file",
                    on_click=app.attach,
                ),
                ft.IconButton(
                    ft.Icons.STOP if voice.get("phase") == "recording" else ft.Icons.MIC_NONE,
                    tooltip="Stop recording" if voice.get("phase") == "recording" else "Record a voice message",
                    on_click=app.microphone,
                    icon_color="#D94B59" if voice.get("phase") == "recording" else None,
                ),
                mode_menu,
                ft.Container(app.goal, expand=True),
                ft.Button(
                    "Stop",
                    icon=ft.Icons.STOP_CIRCLE_OUTLINED,
                    tooltip="Stop the current response",
                    on_click=app.stop,
                    visible=bool(active),
                    color="#B4404A",
                ),
                ft.Button(
                    "Send",
                    icon=ft.Icons.ARROW_UPWARD,
                    on_click=app.submit,
                    disabled=state.busy or not state.connected,
                    color="white",
                    bgcolor=PRIMARY,
                    tooltip="Send message",
                ),
            ],
            spacing=4,
            vertical_alignment=ft.CrossAxisAlignment.END,
        ),
    ]
    if voice_status:
        controls.append(
            ft.Row(
                [
                    ft.ProgressRing(
                        width=15,
                        height=15,
                        stroke_width=2,
                        visible=voice.get("phase") == "transcribing",
                    ),
                    ft.Text(voice_status, size=13, color=colors["muted"]),
                ]
            )
        )
    controls.append(ft.Text("Enter to send · Shift+Enter for a new line", size=12, color=colors["muted"]))
    return ft.Container(
        ft.Column(controls, spacing=5),
        padding=ft.Padding.symmetric(horizontal=10, vertical=8),
        border_radius=14,
        bgcolor=colors["surface"],
        border=ft.Border.all(1, colors["border"]),
    )


def composer(app) -> ft.Control:
    state, colors = app.state, app.colors
    active = bool(state.task and state.task["status"] not in TERMINAL)
    modern = hasattr(app, "conversation")
    if modern and app.conversation:
        active = active or any(m["status"] == "responding" for m in app.conversation["messages"])
    app.goal.disabled = False
    if modern:
        return _modern_composer(app, active)
    return ft.Container(
        ft.Column(
            [
                app.goal,
                ft.Row(
                    [
                        ft.Container(expand=True),
                        ft.TextButton("Plan", on_click=app.toggle_panel),
                        ft.Button(
                            "Stop",
                            icon=ft.Icons.STOP_CIRCLE_OUTLINED,
                            on_click=app.stop,
                            visible=active,
                        ),
                        ft.Button(
                            "Run",
                            icon=ft.Icons.ARROW_UPWARD,
                            on_click=app.submit,
                            disabled=state.busy or not state.connected,
                            color="white",
                            bgcolor=PRIMARY,
                        ),
                    ]
                ),
            ]
        ),
        padding=14,
        border_radius=18,
        bgcolor=colors["surface"],
        border=ft.Border.all(1, colors["border"]),
    )
