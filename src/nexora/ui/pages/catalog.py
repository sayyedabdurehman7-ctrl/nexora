"""Honest capability screens: no invented projects, memories or generated files."""

import flet as ft

from nexora.ui.state import timestamp
from nexora.ui.theme import badge, card, coming, empty


def unavailable(app, name: str) -> ft.Control:
    info = {
        "Projects": (
            ft.Icons.FOLDER_OUTLINED,
            "Give your bigger goals a home",
            "Project organization is coming soon. Current tasks remain available in Task history.",
            ["Create project", "Milestones"],
        ),
        "Memory": (
            ft.Icons.BOOKMARK_BORDER,
            "Your memory, under your control",
            "Memory is coming soon. Messages are not saved as long-term memory.",
            ["Add memory", "Edit", "Disable", "Delete", "Export memories"],
        ),
    }
    icon, title, description, actions = info[name]
    controls = [
        ft.Text(name, size=28, weight=ft.FontWeight.W_600),
        badge("Coming Soon"),
        empty(icon, title, description, app.colors),
    ]
    if name == "Memory":
        controls += [
            ft.Text("NEXORA only uses enabled memories. You can edit or delete them at any time."),
            ft.Text(
                "These controls will become available when memory storage is connected.",
                color=app.colors["muted"],
            ),
            ft.TextField(label="Search memories · Coming Soon", disabled=True),
            ft.Text("Planned categories: Project · Preference · Workflow · Decision · Pending task"),
        ]
    controls.append(ft.Row([coming(action) for action in actions], wrap=True))
    return ft.ListView(controls, spacing=18, expand=True)


def files(app) -> ft.Control:
    controls = [
        ft.Text("Generated files", size=28, weight=ft.FontWeight.W_600),
        ft.Text(
            "NEXORA does not generate files yet. Below are actual files processed in saved tasks.",
            color=app.colors["muted"],
        ),
    ]
    seen = set()
    for task in app.state.tasks:
        for step in task["plan"]["steps"]:
            result = step.get("result") or {}
            evidence = result.get("evidence", {})
            path = evidence.get("path")
            if not path or "bytes" not in evidence or path in seen:
                continue
            seen.add(path)
            controls.append(
                card(
                    ft.Column(
                        [
                            ft.Text(path, selectable=True, weight=ft.FontWeight.W_600),
                            ft.Text(f"{timestamp(task.get('ended_at'))} · {evidence['bytes']} bytes"),
                            badge("Processed file · existing workspace"),
                            ft.Text(
                                "Recorded evidence; the file may have changed since this run.",
                                size=12,
                            ),
                            ft.Row(
                                [
                                    ft.TextButton("View saved result", on_click=app.open_handler(task["id"])),
                                    coming("Open file"),
                                    coming("Show in folder"),
                                    coming("Export"),
                                    coming("Delete"),
                                ],
                                wrap=True,
                            ),
                        ]
                    ),
                    app.colors,
                )
            )
    if not seen:
        controls.append(
            empty(
                ft.Icons.INSERT_DRIVE_FILE_OUTLINED,
                "No processed files yet",
                "Place an approved text file in your workspace, then try 'read notes.txt'.",
                app.colors,
            )
        )
    return ft.ListView(controls, spacing=18, expand=True)


def tools(app) -> ft.Control:
    available = {tool["name"] for tool in app.state.tools}
    entries = [
        (
            "Calculator",
            "calculator",
            "Bounded arithmetic with verified results.",
            "calculate 2 + 3",
        ),
        ("Files", "files", "List, read and search approved local text files.", "list files"),
        ("PDF Reader", "pdf", "Extract text and metadata from approved PDFs.", None),
        ("Web Research", "research", "Find sources and retain evidence.", None),
        ("Memory", "memory", "Save only the information you explicitly choose.", None),
    ]
    controls = [
        ft.Text("Tools", size=28, weight=ft.FontWeight.W_600),
        ft.Text(
            "The mock planner selects tools from your command. Only registered tools can run.",
            color=app.colors["muted"],
        ),
    ]
    for title, name, purpose, command in entries:
        enabled = name in available
        controls.append(
            card(
                ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Text(title, size=18, weight=ft.FontWeight.W_600),
                                badge(
                                    "Available" if enabled else "Coming Soon",
                                    "#268365" if enabled else "#64738D",
                                ),
                            ],
                            wrap=True,
                        ),
                        ft.Text(purpose),
                        ft.Text(
                            "Local · Low risk" if enabled else "Provider and risk available after integration",
                            size=12,
                        ),
                        ft.Row(
                            [
                                ft.Button(
                                    "Test tool" if enabled else "Test · Coming Soon",
                                    disabled=not enabled,
                                    on_click=app.suggestion_handler(command) if enabled else None,
                                ),
                                coming("Enable / disable"),
                            ],
                            wrap=True,
                        ),
                    ]
                ),
                app.colors,
            )
        )
    controls += [
        ft.Text("On the roadmap", size=18),
        ft.Text("Browser Automation · Voice · Screen Understanding · Image Creation · Video Creation"),
        badge("Coming Soon"),
    ]
    return ft.ListView(controls, expand=True, spacing=16)
