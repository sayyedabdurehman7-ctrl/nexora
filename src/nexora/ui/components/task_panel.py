import flet as ft

from nexora.ui.state import duration, label, timestamp
from nexora.ui.theme import PRIMARY, badge, card

RISK_COLORS = {"low": "#268365", "medium": "#B87516", "high": "#D94B59", "critical": "#922937"}


def task_panel(app) -> ft.Control:
    state, colors = app.state, app.colors
    task = state.task
    tabs = ft.Row(
        [
            ft.TextButton(
                name,
                on_click=app.panel_tab_handler(name),
                expand=True,
                style=ft.ButtonStyle(
                    color=ft.Colors.PRIMARY if state.panel_tab == name else colors["muted"],
                    padding=4,
                ),
            )
            for name in ("Plan", "Activity", "Evidence", "Details")
        ],
        spacing=0,
        wrap=False,
    )
    content = []
    if not task:
        content = [
            ft.Icon(ft.Icons.ROUTE_OUTLINED, size=32, color=PRIMARY),
            ft.Text("A clear path to your goal", size=17, weight=ft.FontWeight.W_600),
            ft.Text(
                "Your plan, progress and verified evidence will appear here when you run a task.",
                color=colors["muted"],
            ),
        ]
    elif state.panel_tab == "Plan":
        content = [
            ft.Text(task["user_text"], weight=ft.FontWeight.W_600),
            badge(label(task["status"])),
        ]
        for step in task["plan"]["steps"]:
            status = "Pending" if step["status"] == "PLANNED" else label(step["status"])
            content.append(
                card(
                    ft.Column(
                        [
                            ft.Row(
                                [
                                    badge(str(step["order"])),
                                    ft.Text(status, weight=ft.FontWeight.W_600),
                                ]
                            ),
                            ft.Text(step["description"]),
                            ft.Text(
                                f"Tool: {step['selected_tool']}", size=12, color=colors["muted"]
                            ),
                            ft.Row(
                                [
                                    badge(
                                        step["risk_level"].title() + " risk",
                                        RISK_COLORS[step["risk_level"]],
                                    ),
                                    ft.Text(f"Retries: {step['retry_count']}", size=11),
                                ],
                                wrap=True,
                            ),
                        ]
                    ),
                    colors,
                )
            )
        if not task["plan"]["steps"]:
            content.append(ft.Text("No executable plan. Try a supported mock command."))
    elif state.panel_tab == "Activity":
        content = [ft.Text("Live activity", size=17, weight=ft.FontWeight.W_600)]
        content += [
            ft.Row(
                [
                    ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE, size=16, color=PRIMARY),
                    ft.Column(
                        [
                            ft.Text(event["message"], size=13),
                            ft.Text(timestamp(event["timestamp"]), size=10, color=colors["muted"]),
                        ],
                        expand=True,
                    ),
                ]
            )
            for event in state.events
        ]
        if not state.events:
            content.append(ft.Text("No activity recorded yet."))
    elif state.panel_tab == "Evidence":
        for step in task["plan"]["steps"]:
            if not step.get("result"):
                continue
            result = step["result"]
            rows = [
                ft.Text(step["selected_tool"].title(), weight=ft.FontWeight.W_600),
                badge(
                    "Verified" if step["status"] == "COMPLETED" else "Not verified",
                    "#268365" if step["status"] == "COMPLETED" else "#B87516",
                ),
            ]
            for key, value in result["evidence"].items():
                rows += [
                    ft.Text(key.replace("_", " ").title(), size=11, color=colors["muted"]),
                    ft.Text(str(value), selectable=True, size=12),
                ]
            rows.append(
                ft.Text(
                    "Completed " + timestamp(task.get("ended_at")), size=10, color=colors["muted"]
                )
            )
            content.append(card(ft.Column(rows), colors))
        if not content:
            content = [ft.Text("No evidence yet. Results appear only after a tool runs.")]
    else:
        for key, value in {
            "Task ID": task["id"],
            "Started": timestamp(task.get("started_at")),
            "Completed": timestamp(task.get("ended_at")),
            "Duration": duration(task),
            "Steps": len(task["plan"]["steps"]),
            "Human approvals": task["interventions"],
            "Provider": task["provider"],
            "API usage": "None · deterministic mock",
        }.items():
            content += [
                ft.Text(key, size=11, color=colors["muted"]),
                ft.Text(str(value), selectable=True),
            ]
    return ft.Column(
        [
            ft.Row(
                [
                    ft.Text("TASK INTELLIGENCE", size=11, weight=ft.FontWeight.BOLD, expand=True),
                    ft.IconButton(
                        ft.Icons.CLOSE, tooltip="Hide task panel", on_click=app.close_panel
                    ),
                ]
            ),
            tabs,
            ft.Divider(color=colors["border"]),
            ft.Column(content, spacing=16, scroll=ft.ScrollMode.AUTO, expand=True),
        ],
        expand=True,
    )
