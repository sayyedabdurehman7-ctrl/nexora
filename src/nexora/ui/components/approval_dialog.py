import flet as ft

from nexora.ui.components.task_panel import RISK_COLORS
from nexora.ui.theme import badge


def approval_dialog(app, task: dict) -> ft.AlertDialog:
    approval = task["approval"]

    async def approve(e):
        app.page.pop_dialog()
        await app.decide(approval["id"], True, task["id"])

    async def reject(e):
        app.page.pop_dialog()
        await app.decide(approval["id"], False, task["id"])

    async def cancel(e):
        app.page.pop_dialog()
        await app.stop_task(task["id"])

    return ft.AlertDialog(
        modal=True,
        title=ft.Text("Your approval is needed"),
        content=ft.Container(
            ft.Column(
                [
                    badge(approval["risk"].title() + " risk", RISK_COLORS[approval["risk"]]),
                    ft.Text("Exact action", weight=ft.FontWeight.BOLD),
                    ft.Text(approval["action"]),
                    ft.Text("Target", weight=ft.FontWeight.BOLD),
                    ft.Text(approval["target"], selectable=True),
                    ft.Text("Why approval is needed", weight=ft.FontWeight.BOLD),
                    ft.Text("This changes stored task data and needs your explicit permission."),
                    ft.Text("Consequence", weight=ft.FontWeight.BOLD),
                    ft.Text(approval["consequence"]),
                    ft.Text("Reversible: " + ("Yes" if approval["reversible"] else "No")),
                ],
                tight=True,
                scroll=ft.ScrollMode.AUTO,
            ),
            width=460,
            height=min(400, (app.page.height or 800) - 230),
        ),
        actions=[
            ft.TextButton("Cancel task", on_click=cancel),
            ft.TextButton("Reject", on_click=reject),
            ft.Button(
                "Approve exact action", on_click=approve, disabled=approval["risk"] == "critical"
            ),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
