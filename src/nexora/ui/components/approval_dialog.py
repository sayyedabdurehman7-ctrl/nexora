import flet as ft


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
        title=ft.Text("Waiting for your approval"),
        content=ft.Container(
            ft.Column(
                [
                    ft.Text("NEXORA needs permission before it continues."),
                    ft.Text("Action", weight=ft.FontWeight.BOLD),
                    ft.Text(approval["action"]),
                    ft.Text("What will happen", weight=ft.FontWeight.BOLD),
                    ft.Text(approval["consequence"]),
                    ft.Text("You can reject this action and NEXORA will stop the task."),
                ],
                tight=True,
                scroll=ft.ScrollMode.AUTO,
            ),
            width=460,
            height=min(400, (app.page.height or 800) - 230),
        ),
        actions=[
            ft.TextButton("Stop", on_click=cancel),
            ft.TextButton("Reject", on_click=reject),
            ft.Button("Approve", on_click=approve, disabled=approval["risk"] == "critical"),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
