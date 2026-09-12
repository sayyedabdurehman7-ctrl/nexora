import flet as ft

from nexora.ui.components.chat_composer import composer
from nexora.ui.components.chat_message import messages
from nexora.ui.state import TERMINAL, response_text, simple_status
from nexora.ui.theme import PRIMARY


def _message_text(app, message: dict) -> tuple[str, str]:
    status = message["status"]
    if message.get("task_id"):
        task = app.state.task
        if task and task["id"] == message["task_id"]:
            text = response_text(task) if task["status"] == "COMPLETED" else ""
            return text, simple_status(task["status"])
    if status == "responding":
        return message["content"], "NEXORA is thinking..."
    if status == "failed":
        return "", "Something went wrong. Try again."
    if status == "cancelled":
        return message["content"].replace("Response stopped.", "").strip(), "Task stopped"
    return message["content"], ""


def _conversation_message(app, message: dict) -> ft.Control:
    colors = app.colors
    if message["role"] == "user":
        return ft.Container(
            ft.Container(
                ft.Column(
                    [
                        ft.Text("You", size=13, weight=ft.FontWeight.W_600),
                        ft.Text(message["content"], selectable=True, size=app.text_size),
                        ft.Text(
                            {
                                "light": "Low",
                                "medium": "Medium",
                                "strong": "Strong / Deep Reply",
                            }.get(message.get("answer_mode"), "Medium"),
                            size=11,
                            color=colors["muted"],
                        ),
                    ],
                    spacing=8,
                ),
                padding=ft.Padding.symmetric(horizontal=16, vertical=12),
                bgcolor=colors["accent"],
                border_radius=16,
                width=min(700, (app.page.width or 1000) * 0.68),
            ),
            alignment=ft.Alignment.CENTER_RIGHT,
            key=f"message-{message['id']}",
        )

    text, status_text = _message_text(app, message)
    task = app.state.task if message.get("task_id") else None
    active = bool(task and task["status"] not in TERMINAL) or message["status"] == "responding"
    action_controls: list[ft.Control] = []
    if text and (message["status"] == "completed" or task):
        action_controls.append(
            ft.TextButton("Copy Answer", icon=ft.Icons.COPY_OUTLINED, on_click=app.copy_handler(text))
        )
    if task:
        approval = task.get("approval")
        if task["status"] == "AWAITING_APPROVAL" and approval and approval.get("status") == "pending":
            action_controls += [
                ft.Button("Approve", icon=ft.Icons.CHECK, on_click=app.decision_handler(True)),
                ft.TextButton("Reject", icon=ft.Icons.CLOSE, on_click=app.decision_handler(False)),
            ]
    if message["status"] in ("failed", "cancelled") or (task and task["status"] in ("FAILED", "TIMED_OUT")):
        previous = next(
            (item["content"] for item in reversed(app.conversation["messages"]) if item["role"] == "user"),
            "",
        )
        action_controls.append(
            ft.Button("Retry", icon=ft.Icons.REFRESH, on_click=app.retry_handler({"user_text": previous}))
        )
    if message["status"] == "failed" or (task and task["status"] in ("FAILED", "TIMED_OUT")):
        action_controls.append(ft.TextButton("View Details", on_click=app.show_error_details))
    if message["status"] == "completed":
        action_controls.append(
            ft.PopupMenuButton(
                content=ft.Container(
                    ft.Row([ft.Text("More"), ft.Icon(ft.Icons.ARROW_DROP_DOWN, size=16)], spacing=2),
                    padding=6,
                ),
                tooltip="More",
                items=[
                    ft.PopupMenuItem(
                        content=ft.Text("Play voice"),
                        icon=ft.Icons.VOLUME_UP_OUTLINED,
                        on_click=app.speak_handler(message["id"]),
                    )
                ],
            )
        )

    body: list[ft.Control] = [ft.Text("NEXORA", size=12, weight=ft.FontWeight.W_600, color=colors["muted"])]
    if status_text:
        body.append(
            ft.Row(
                [
                    ft.ProgressRing(width=15, height=15, stroke_width=2, visible=active),
                    ft.Icon(
                        ft.Icons.CHECK_CIRCLE_OUTLINE,
                        size=17,
                        color="#268365",
                        visible=status_text == "Task completed",
                    ),
                    ft.Text(
                        status_text,
                        size=14,
                        color="#B4404A" if "wrong" in status_text or status_text == "Task stopped" else PRIMARY,
                        weight=ft.FontWeight.W_600,
                    ),
                ],
                spacing=8,
            )
        )
    if text:
        body.append(
            ft.Markdown(
                text,
                selectable=True,
                extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
                on_tap_link=app.source_link,
            )
        )
    action_row = None
    if action_controls:
        action_row = ft.Row(action_controls, wrap=True, spacing=6, opacity=0)
        body.append(action_row)

    def show_actions(e):
        if action_row is None:
            return
        action_row.opacity = 1 if str(e.data).lower() == "true" else 0
        action_row.update()

    return ft.Container(
        ft.Column(body, spacing=10),
        padding=ft.Padding.symmetric(horizontal=8, vertical=10),
        key=f"message-{message['id']}",
        on_hover=show_actions if action_row else None,
    )


def chat(app) -> ft.Control:
    colors = app.colors
    empty_conversation = False
    if getattr(app, "conversation", None):
        body = [_conversation_message(app, message) for message in app.conversation["messages"]]
    elif app.state.task:
        body = messages(app, app.state.task)
    elif hasattr(app, "conversation"):
        empty_conversation = True
        body = [
            ft.Container(
                ft.Column(
                    [
                        ft.Text("How can I help you today?", size=28, weight=ft.FontWeight.W_600),
                        ft.Text(
                            "Ask a question, talk through a problem, or give NEXORA a task.",
                            size=15,
                            color=colors["muted"],
                            text_align=ft.TextAlign.CENTER,
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=16,
                ),
                alignment=ft.Alignment.CENTER,
            )
        ]
    else:
        body = messages(app, app.state.task) if app.state.task else [
            ft.Container(height=40),
            ft.Text("How can I help you today?", size=28, weight=ft.FontWeight.W_600),
        ]
    conversation_area = (
        ft.Container(body[0], expand=True, alignment=ft.Alignment.CENTER)
        if empty_conversation
        else ft.ListView(
            body,
            expand=True,
            key="chat-messages",
            auto_scroll=getattr(app, "chat_at_bottom", True),
            on_scroll=getattr(app, "chat_scroll", None),
            spacing=14,
            padding=ft.Padding.only(left=8, right=8, bottom=20),
        )
    )
    return ft.Column(
        [
            conversation_area,
            composer(app),
        ],
        expand=True,
        spacing=12,
    )
