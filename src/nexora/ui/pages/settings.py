import flet as ft

from nexora.ui.theme import PRIMARY, card


def settings(app) -> ft.Control:
    values, colors = app.state.settings, app.colors
    provider_controls = hasattr(app, "provider_changed")
    selected = getattr(app, "pending_provider", None) or values.get("provider", "gemini")
    model = (
        app.pending_gemini_model
        if getattr(app, "pending_gemini_model", None) is not None
        else values.get("gemini_model", "")
    )
    provider_options = [
        ft.DropdownOption("gemini", "Gemini AI"),
        ft.DropdownOption("mock", "Mock AI"),
    ]
    voice_mode = getattr(app, "pending_voice_mode", None) or values.get("voice_mode", "push_to_talk")
    assistant_voice = (
        app.pending_assistant_voice
        if getattr(app, "pending_assistant_voice", None) is not None
        else values.get("assistant_voice_enabled", False)
    )
    wake_phrase = getattr(app, "pending_wake_phrase", None) or values.get("wake_phrase", "Hey NEXORA")
    creator_website = (
        app.pending_creator_website
        if getattr(app, "pending_creator_website", None) is not None
        else values.get("creator_website", "")
    )
    content = ft.Column(
        [
            ft.Text("AI Settings", size=28, weight=ft.FontWeight.W_600),
            ft.Text("Choose the AI used for new replies.", color=colors["muted"]),
            card(
                ft.Column(
                    [
                        ft.Dropdown(
                            label="AI Provider",
                            value=selected,
                            options=provider_options,
                            on_select=getattr(app, "provider_changed", None),
                            disabled=not provider_controls,
                            width=300,
                        ),
                        ft.Text(
                            "Gemini API: Connected"
                            if values.get("gemini_key_status") == "Configured"
                            else "Gemini API key: Not configured",
                            weight=ft.FontWeight.W_600,
                        ),
                        ft.TextField(
                            label="Gemini Model",
                            value=model,
                            hint_text="Enter the model ID from Google AI Studio",
                            on_change=getattr(app, "gemini_model_changed", None),
                            disabled=not provider_controls,
                            width=420,
                        ),
                        ft.Row(
                            [
                                ft.Button(
                                    "Test Gemini Connection",
                                    icon=ft.Icons.WIFI,
                                    on_click=getattr(app, "test_gemini", None),
                                    disabled=not provider_controls,
                                ),
                                ft.Button(
                                    "Save Settings",
                                    icon=ft.Icons.SAVE_OUTLINED,
                                    on_click=getattr(app, "save_provider_settings", None),
                                    disabled=not provider_controls,
                                    color="white",
                                    bgcolor=PRIMARY,
                                ),
                            ],
                            wrap=True,
                        ),
                        ft.Text(
                            getattr(app, "gemini_status", ""),
                            size=13,
                            color=colors["muted"],
                        ),
                    ],
                    spacing=18,
                ),
                colors,
            ),
            ft.Text("Voice Settings", size=24, weight=ft.FontWeight.W_600),
            card(
                ft.Column(
                    [
                        ft.Dropdown(
                            label="Voice mode",
                            value=voice_mode,
                            options=[
                                ft.DropdownOption("off", "Off"),
                                ft.DropdownOption("push_to_talk", "Push-to-Talk"),
                                ft.DropdownOption("wake_word", "Wake Word — Experimental - setup required"),
                            ],
                            on_select=getattr(app, "voice_mode_changed", None),
                            width=430,
                        ),
                        ft.Text(
                            "Microphone permission: "
                            + getattr(app, "voice", {}).get("microphone_permission", "Not tested"),
                            weight=ft.FontWeight.W_600,
                        ),
                        ft.Switch(
                            label="Assistant voice",
                            value=assistant_voice,
                            on_change=getattr(app, "assistant_voice_changed", None),
                        ),
                        ft.TextField(
                            label="Wake phrase",
                            value=wake_phrase,
                            hint_text="Hey NEXORA",
                            on_change=getattr(app, "wake_phrase_changed", None),
                            width=420,
                        ),
                        ft.Text(
                            "Wake Word is off by default. Enabling it would keep the microphone available, so "
                            "NEXORA shows a privacy warning first. Local wake detection is not installed yet.",
                            size=12,
                            color=colors["muted"],
                        ),
                        ft.Row(
                            [
                                ft.Button(
                                    "Test microphone",
                                    icon=ft.Icons.MIC_NONE,
                                    on_click=getattr(app, "test_microphone", None),
                                ),
                                ft.Button(
                                    "Test NEXORA voice",
                                    icon=ft.Icons.VOLUME_UP_OUTLINED,
                                    on_click=getattr(app, "test_voice", None),
                                ),
                                ft.Button(
                                    "Stop Listening",
                                    icon=ft.Icons.MIC_OFF_OUTLINED,
                                    on_click=lambda event: app.page.run_task(app.voice_action, "cancel"),
                                    visible=bool(
                                        getattr(app, "voice", {}).get("microphone_active")
                                        and voice_mode == "wake_word"
                                    ),
                                ),
                            ],
                            wrap=True,
                        ),
                        ft.Button(
                            "Save voice settings",
                            icon=ft.Icons.SAVE_OUTLINED,
                            on_click=getattr(app, "save_voice_settings", None),
                            color="white",
                            bgcolor=PRIMARY,
                        ),
                    ],
                    spacing=16,
                ),
                colors,
            ),
            ft.Row(
                [
                    ft.Text("About", size=20, weight=ft.FontWeight.W_600, expand=True),
                    ft.TextButton(
                        "About this project",
                        icon=ft.Icons.INFO_OUTLINE,
                        on_click=app.navigate_handler("About NEXORA"),
                    ),
                ]
            ),
            card(
                ft.Column(
                    [
                        ft.TextField(
                            label="Creator website",
                            value=creator_website,
                            hint_text="https://your-website-link.com",
                            on_change=getattr(app, "creator_website_changed", None),
                            width=460,
                        ),
                        ft.Text(
                            "The link appears in About responses only after you save a valid URL.",
                            size=12,
                            color=colors["muted"],
                        ),
                        ft.Button(
                            "Save About settings",
                            icon=ft.Icons.SAVE_OUTLINED,
                            on_click=getattr(app, "save_about_settings", None),
                            color="white",
                            bgcolor=PRIMARY,
                        ),
                    ],
                    spacing=12,
                ),
                colors,
            ),
        ],
        spacing=18,
    )
    return ft.ListView([content], expand=True, spacing=18)
