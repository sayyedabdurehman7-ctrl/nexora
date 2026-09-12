import flet as ft

from nexora.ui.state import TERMINAL, duration, label, simple_status, timestamp
from nexora.ui.theme import PRIMARY, badge, card

RISK_COLORS = {"low": "#268365", "medium": "#B87516", "high": "#D94B59", "critical": "#922937"}


def _clean_step(description: str) -> str:
    return description.replace(" (mock plan)", "")


def _simple_task_panel(app) -> ft.Control:
    state, colors, task = app.state, app.colors, app.state.task
    header = ft.Row(
        [
            ft.Text("NEXORA Workspace", size=16, weight=ft.FontWeight.W_600, expand=True),
            ft.IconButton(ft.Icons.CLOSE, tooltip="Close", on_click=app.close_panel),
        ]
    )
    quick_actions = ft.Column(
        [
            ft.Text("Quick Actions", size=12, color=colors["muted"], weight=ft.FontWeight.W_600),
            ft.TextButton(
                "Research a topic",
                icon=ft.Icons.TRAVEL_EXPLORE_OUTLINED,
                on_click=app.suggestion_handler("Research "),
            ),
            ft.TextButton(
                "Summarize a file",
                icon=ft.Icons.DESCRIPTION_OUTLINED,
                on_click=app.suggestion_handler("summarize pdf "),
            ),
            ft.TextButton(
                "Create a task plan",
                icon=ft.Icons.FORMAT_LIST_NUMBERED,
                on_click=app.suggestion_handler("Create a plan for "),
            ),
            ft.TextButton(
                "Continue a project",
                icon=ft.Icons.FOLDER_OPEN_OUTLINED,
                on_click=app.navigate_handler("Projects"),
            ),
        ],
        spacing=0,
    )
    pending = sum(item.get("status") not in TERMINAL for item in state.tasks)
    saved_context: list[ft.Control] = []
    if pending:
        saved_context = [
            ft.Text("Saved Context", size=12, color=colors["muted"], weight=ft.FontWeight.W_600),
            ft.Text(f"Pending tasks: {pending}", size=13),
        ]
    if not task:
        return ft.Column(
            [
                header,
                ft.Divider(color=colors["border"]),
                ft.Text("Task Pulse", size=12, color=colors["muted"], weight=ft.FontWeight.W_600),
                ft.Text("No active task", size=14, weight=ft.FontWeight.W_600),
                ft.Text("Plans and progress appear here when needed.", size=13, color=colors["muted"]),
                ft.Divider(color=colors["border"]),
                quick_actions,
                *([ft.Divider(color=colors["border"]), *saved_context] if saved_context else []),
            ],
            spacing=10,
        )
    steps = task["plan"]["steps"]
    completed = sum(step["status"] == "COMPLETED" for step in steps)
    current = next(
        (step for step in steps if step["status"] not in ("COMPLETED", "FAILED", "CANCELLED")),
        steps[-1] if steps else None,
    )
    progress = completed / len(steps) if steps else (1 if task["status"] == "COMPLETED" else 0)
    controls = [
        header,
        ft.Divider(color=colors["border"]),
        ft.Text("Task Pulse", size=12, color=colors["muted"], weight=ft.FontWeight.W_600),
        ft.Text("Current task", size=12, color=colors["muted"], weight=ft.FontWeight.W_600),
        ft.Text(task["user_text"], size=15, weight=ft.FontWeight.W_600),
        ft.Text(simple_status(task["status"]), color=PRIMARY, weight=ft.FontWeight.W_600),
        ft.ProgressBar(value=progress, color=PRIMARY, bgcolor=colors["border"]),
        ft.Text(
            f"{completed} of {len(steps)} steps complete" if steps else "Preparing the first step…",
            size=12,
            color=colors["muted"],
        ),
    ]
    if current:
        controls += [
            ft.Text("Current step", size=12, color=colors["muted"], weight=ft.FontWeight.W_600),
            ft.Text(_clean_step(current["description"]), size=14),
        ]
    if state.plan_expanded and steps:
        controls += [ft.Divider(color=colors["border"]), ft.Text("Full plan", weight=ft.FontWeight.W_600)]
        for step in steps:
            step_label = {
                "COMPLETED": "Done",
                "FAILED": "Failed",
                "CANCELLED": "Stopped",
                "EXECUTING": "In progress",
                "VERIFYING": "Checking",
            }.get(step["status"], "Next")
            controls.append(
                ft.Row(
                    [
                        ft.Container(
                            ft.Text(str(step["order"]), color="white", size=12, text_align=ft.TextAlign.CENTER),
                            bgcolor=PRIMARY if step["status"] == "COMPLETED" else colors["muted"],
                            width=25,
                            height=25,
                            border_radius=13,
                            alignment=ft.Alignment.CENTER,
                        ),
                        ft.Column(
                            [
                                ft.Text(_clean_step(step["description"]), size=13),
                                ft.Text(step_label, size=12, color=colors["muted"]),
                            ],
                            spacing=1,
                            expand=True,
                        ),
                    ]
                )
            )
    actions = [
        ft.TextButton(
            "Hide Plan" if state.plan_expanded else "View Plan",
            icon=ft.Icons.FORMAT_LIST_NUMBERED,
            on_click=app.toggle_plan_steps,
        ),
        ft.TextButton("View Details", icon=ft.Icons.INFO_OUTLINE, on_click=app.show_task_details),
    ]
    if task["status"] not in TERMINAL:
        actions.insert(0, ft.Button("Stop", icon=ft.Icons.STOP_CIRCLE_OUTLINED, on_click=app.stop))
    controls.append(ft.Row(actions, wrap=True))
    controls.extend([ft.Divider(color=colors["border"]), quick_actions])
    if saved_context:
        controls.extend([ft.Divider(color=colors["border"]), *saved_context])
    return ft.Column(
        [
            *controls[:1],
            ft.Column(controls[1:], spacing=14, scroll=ft.ScrollMode.AUTO, expand=True),
        ],
        expand=True,
    )


def task_panel(app) -> ft.Control:
    if hasattr(app, "conversation"):
        return _simple_task_panel(app)
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
        conversation = getattr(app, "conversation", None)
        if conversation and len(conversation["messages"]) >= 2:
            latest = conversation["messages"][-1]
            request = conversation["messages"][-2]["content"].lower()
            if "plan" in request and latest["role"] == "assistant":
                content = [
                    ft.Text("Suggested plan", weight=ft.FontWeight.BOLD),
                    ft.Text("Advice only. No tools are executing.", size=12),
                    ft.Text(latest["content"] or "Preparing your plan…", selectable=True),
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
                            ft.Text(f"Tool: {step['selected_tool']}", size=12, color=colors["muted"]),
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
            content.append(ft.Text("No executable plan. Try a supported command."))
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
            rows.append(ft.Text("Completed " + timestamp(task.get("ended_at")), size=10, color=colors["muted"]))
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
                    ft.IconButton(ft.Icons.CLOSE, tooltip="Hide task panel", on_click=app.close_panel),
                ]
            ),
            tabs,
            ft.Divider(color=colors["border"]),
            ft.Column(content, spacing=16, scroll=ft.ScrollMode.AUTO, expand=True),
        ],
        expand=True,
    )
