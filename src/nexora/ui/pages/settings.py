import flet as ft

from nexora.ui.theme import badge, card, coming


def settings(app) -> ft.Control:
    values, colors = app.state.settings, app.colors
    controls = [
        ft.Text("Settings", size=28, weight=ft.FontWeight.W_600),
        ft.Text("A local workspace, with clear boundaries.", color=colors["muted"]),
    ]
    controls.append(
        card(
            ft.Column(
                [
                    ft.Text("AI provider", size=19, weight=ft.FontWeight.W_600),
                    badge("Mock · selected · no API key"),
                    ft.Text(
                        "Model: deterministic commands. General questions are not supported yet."
                    ),
                    ft.Row(
                        [
                            ft.Button(
                                "Test connection", icon=ft.Icons.WIFI, on_click=app.reconnect
                            ),
                            coming("OpenAI"),
                            coming("Ollama"),
                        ],
                        wrap=True,
                    ),
                    ft.Text(
                        "Put credentials in local .env. Secret values are never shown.",
                        size=12,
                    ),
                ]
            ),
            colors,
        )
    )
    controls.append(
        card(
            ft.Column(
                [
                    ft.Text("Safety", size=19, weight=ft.FontWeight.W_600),
                    badge("Safe Mode on", "#268365"),
                    ft.Text(
                        f"Maximum steps: {values.get('max_plan_steps', 'Unavailable')}\n"
                        f"Maximum retries: {values.get('max_tool_retries', 'Unavailable')}\n"
                        f"Task duration: {values.get('max_task_seconds', 'Unavailable')} seconds"
                    ),
                    ft.Text("Approved workspace", weight=ft.FontWeight.W_600),
                    ft.Text(
                        values.get("workspace", "Connect to the backend to see the workspace."),
                        selectable=True,
                    ),
                    ft.Text("Allowed tools: Calculator, Files\nAllowed websites: none."),
                    coming("Edit safety settings"),
                    ft.Text(
                        "Edit .env and restart to change supported limits.",
                        size=12,
                    ),
                ]
            ),
            colors,
        )
    )
    controls.append(
        card(
            ft.Column(
                [
                    ft.Text("Memory & privacy", size=19, weight=ft.FontWeight.W_600),
                    ft.Text(
                        "Long-term memory: not implemented\nAudio and screenshots: not captured\n"
                        "Task history and audit events: kept locally until you manage the database"
                    ),
                    ft.Row(
                        [
                            coming("Enable memory"),
                            coming("Clear memory"),
                            coming("Export memory"),
                            coming("Log retention"),
                        ],
                        wrap=True,
                    ),
                ]
            ),
            colors,
        )
    )
    controls.append(
        card(
            ft.Column(
                [
                    ft.Text("Appearance", size=19, weight=ft.FontWeight.W_600),
                    ft.Row(
                        [
                            ft.Dropdown(
                                label="Theme",
                                width=180,
                                value=app.state.preferences["theme"],
                                options=[ft.DropdownOption(v) for v in ("light", "dark", "system")],
                                on_select=app.theme_changed,
                            ),
                            ft.Dropdown(
                                label="Density",
                                width=180,
                                value=app.state.preferences["density"],
                                options=[ft.DropdownOption(v) for v in ("Comfortable", "Compact")],
                                on_select=app.density_changed,
                            ),
                            ft.Dropdown(
                                label="Text size",
                                width=150,
                                value=str(app.text_size),
                                options=[ft.DropdownOption(str(v)) for v in (14, 16, 18)],
                                on_select=app.text_changed,
                            ),
                        ],
                        wrap=True,
                    ),
                ]
            ),
            colors,
        )
    )
    controls.append(
        card(
            ft.Column(
                [
                    ft.Text("About NEXORA", size=19, weight=ft.FontWeight.W_600),
                    ft.Text("Version 0.1.0 · Computer Science Final Year Project"),
                    ft.Text(
                        "An Autonomous Multimodal Personal AI Agent for Goal-Based Task Planning, "
                        "Tool Selection, and Cross-Application Execution"
                    ),
                    ft.Text("Connected" if app.state.connected else "Backend offline"),
                    ft.Row(
                        [
                            ft.TextButton("Quick guide", on_click=app.help_dialog),
                            ft.TextButton("First-run guide", on_click=app.welcome_dialog),
                        ],
                        wrap=True,
                    ),
                    ft.Text(
                        "Full documentation: README.md and docs/SETUP.md in your NEXORA folder.",
                        size=12,
                    ),
                ]
            ),
            colors,
        )
    )
    return ft.ListView(controls, expand=True, spacing=18)
