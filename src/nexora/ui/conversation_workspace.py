"""Conversation UI layered over the existing task workspace."""

import asyncio
import json

import flet as ft
import httpx

from nexora.ui.workspace import Workspace


class ConversationWorkspace(Workspace):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.conversation = None
        self.conversations = []
        self.voice = {}
        self.voice_mode = False
        self.transcript_seen = ""
        self.spoken = set()
        self.state.panel_open = False
        self.state.plan_expanded = False
        self.editing = False
        self.pending_provider = None
        self.pending_gemini_model = None
        self.pending_voice_mode = None
        self.pending_assistant_voice = None
        self.pending_wake_phrase = None
        self.pending_creator_website = None
        self.feedback_values = {
            "overall_experience": 5,
            "confusing": "",
            "error_seen": "",
            "liked_feature": "",
            "add_next": "",
            "attach_diagnostic": False,
        }
        self.answer_mode = self.state.preferences.get("answer_mode", "medium")
        self.chat_at_bottom = True
        self.gemini_status = ""
        self.goal.on_focus = self.input_focus
        self.goal.on_blur = self.input_blur
        self.goal.on_change = self.input_change

    async def input_focus(self, e=None):
        self.editing = True

    async def input_blur(self, e=None):
        self.editing = False

    async def input_change(self, e):
        self.goal.value = e.control.value

    async def refresh(self):
        await super().refresh()
        if self.state.connected:
            try:
                desired = self.state.preferences.get("provider") or self.state.settings.get("provider")
                desired_model = self.state.preferences.get("gemini_model") or self.state.settings.get(
                    "gemini_model", ""
                )
                if self.state.settings.get("provider") and (
                    self.state.settings["provider"] != desired
                    or self.state.settings.get("gemini_model", "") != desired_model
                ):
                    selected = await self.client.request(
                        "PATCH",
                        "/api/v1/settings/provider",
                        json={"provider": desired, "gemini_model": desired_model},
                    )
                    self.state.settings.update(selected)
                desired_voice_mode = self.state.preferences.get("voice_mode", "push_to_talk")
                desired_voice_enabled = bool(self.state.preferences.get("assistant_voice_enabled", False))
                desired_wake_phrase = self.state.preferences.get("wake_phrase", "Hey NEXORA")
                if any(
                    (
                        self.state.settings.get("voice_mode") != desired_voice_mode,
                        self.state.settings.get("assistant_voice_enabled") != desired_voice_enabled,
                        self.state.settings.get("wake_phrase") != desired_wake_phrase,
                    )
                ):
                    voice_settings = await self.client.request(
                        "PATCH",
                        "/api/v1/voice/settings",
                        json={
                            "voice_mode": desired_voice_mode,
                            "assistant_voice_enabled": desired_voice_enabled,
                            "wake_phrase": desired_wake_phrase,
                        },
                    )
                    self.state.settings.update(
                        voice_mode=voice_settings["voice_mode"],
                        assistant_voice_enabled=voice_settings["assistant_voice_enabled"],
                        wake_phrase=voice_settings["wake_phrase"],
                    )
                self.voice_mode = desired_voice_enabled
                self.conversations = await self.client.request("GET", "/api/v1/conversations")
            except (httpx.HTTPError, KeyError, ValueError):
                self.state.connected = False
                self.error = "NEXORA cannot connect. Restart NEXORA and try again."

    async def submit(self, e=None):
        text = (self.goal.value or "").strip()
        if not text or self.state.busy:
            return
        self.editing = False
        self.state.busy = True
        try:
            if not self.conversation:
                self.conversation = await self.client.request("POST", "/api/v1/conversations")
            self.conversation = await self.client.request(
                "POST",
                f"/api/v1/conversations/{self.conversation['id']}/messages",
                json={"text": text, "answer_mode": self.answer_mode},
            )
            self.goal.value = ""
            self.chat_at_bottom = True
            await self.sync_chat()
            await self.refresh()
            self.error = ""
        except Exception:
            self.error = "Something went wrong. Try again. Your message is still here."
        finally:
            self.state.busy = False
            self.render()

    async def sync_chat(self):
        if not self.conversation:
            return
        self.conversation = await self.client.request("GET", f"/api/v1/conversations/{self.conversation['id']}")
        linked = [m for m in self.conversation["messages"] if m.get("task_id")]
        if linked:
            await self.load_task(linked[-1]["task_id"])

    def open_handler(self, task_id):
        original = super().open_handler(task_id)

        async def open_task(e=None):
            self.conversation = None
            await original(e)

        return open_task

    async def stop(self, e=None):
        await self.voice_action("cancel")
        if self.conversation:
            self.conversation = await self.client.request(
                "POST", f"/api/v1/conversations/{self.conversation['id']}/cancel"
            )
        else:
            await super().stop(e)
        self.render()

    async def new_task(self, e=None):
        await self.voice_action("cancel")
        self.conversation = None
        self.state.panel_open = False
        self.state.plan_expanded = False
        await super().new_task(e)

    def chat_handler(self, chat_id):
        async def open_chat(e=None):
            await self.voice_action("cancel")
            self.conversation = await self.client.request("GET", f"/api/v1/conversations/{chat_id}")
            self.spoken.update(m["id"] for m in self.conversation["messages"])
            self.state.task = None
            self.state.panel_open = False
            self.state.plan_expanded = False
            self.state.screen = "Chat"
            await self.sync_chat()
            self.render()

        return open_chat

    async def voice_action(self, action):
        try:
            self.voice = await self.client.request("POST", f"/api/v1/voice/{action}")
        except Exception:
            self.error = "Voice control failed. Check the backend connection."
        self.render()

    async def microphone(self, e=None):
        if self.state.settings.get("voice_mode", "push_to_talk") == "off":
            self.notify("Choose Push-to-Talk in Voice Settings first.")
            return
        self.transcript_seen = ""
        await self.voice_action("stop" if self.voice.get("phase") == "recording" else "start")

    async def mute(self, e=None):
        await self.voice_action("mute")

    async def pause_voice(self, e=None):
        await self.voice_action("pause")

    async def mode(self, e=None):
        self.voice_mode = not self.voice_mode
        self.render()

    def answer_mode_handler(self, answer_mode: str):
        async def select(e=None):
            self.answer_mode = answer_mode if answer_mode in {"light", "medium", "strong"} else "medium"
            self.state.preferences["answer_mode"] = self.answer_mode
            self.state.save_preferences()
            self.render()

        return select

    async def chat_scroll(self, e):
        self.chat_at_bottom = e.pixels >= e.max_scroll_extent - 100

    async def voice_mode_changed(self, e):
        selected = e.control.value or "push_to_talk"
        if selected == "wake_word":
            self.pending_voice_mode = "push_to_talk"
            e.control.value = "push_to_talk"
            self.page.show_dialog(
                ft.AlertDialog(
                    modal=True,
                    title=ft.Text("Wake Word is experimental"),
                    content=ft.Text(
                        "Reliable local wake detection is not installed. Wake Word remains off and the microphone "
                        "is not activated. Use Push-to-Talk for now."
                    ),
                    actions=[ft.Button("Use Push-to-Talk", on_click=lambda event: self.page.pop_dialog())],
                )
            )
            return
        self.pending_voice_mode = selected

    async def assistant_voice_changed(self, e):
        self.pending_assistant_voice = bool(e.control.value)

    async def wake_phrase_changed(self, e):
        self.pending_wake_phrase = e.control.value or "Hey NEXORA"

    async def save_voice_settings(self, e=None):
        values = self.state.settings
        mode = self.pending_voice_mode or values.get("voice_mode", "push_to_talk")
        enabled = (
            self.pending_assistant_voice
            if self.pending_assistant_voice is not None
            else values.get("assistant_voice_enabled", False)
        )
        phrase = self.pending_wake_phrase or values.get("wake_phrase", "Hey NEXORA")
        try:
            self.voice = await self.client.request(
                "PATCH",
                "/api/v1/voice/settings",
                json={
                    "voice_mode": mode,
                    "assistant_voice_enabled": enabled,
                    "wake_phrase": phrase,
                },
            )
            values.update(
                voice_mode=self.voice["voice_mode"],
                assistant_voice_enabled=self.voice["assistant_voice_enabled"],
                wake_phrase=self.voice["wake_phrase"],
            )
            self.voice_mode = enabled
            self.state.preferences.update(
                voice_mode=mode,
                assistant_voice_enabled=enabled,
                wake_phrase=phrase,
            )
            self.state.save_preferences()
            self.notify("Voice settings saved.")
        except Exception:
            self.error = "Voice settings could not be saved. Try again."
        self.render()

    async def test_microphone(self, e=None):
        try:
            self.voice = await self.client.request("POST", "/api/v1/voice/test-microphone")
            message = (
                "Microphone is ready."
                if self.voice["microphone_permission"] == "Allowed"
                else "Microphone permission is unavailable."
            )
            self.notify(message)
        except Exception:
            self.error = "Microphone test failed. Check Windows microphone permission."
        self.render()

    async def test_voice(self, e=None):
        try:
            self.voice = await self.client.request("POST", "/api/v1/voice/test-voice")
            self.notify("Playing the NEXORA test voice.")
        except Exception:
            self.error = "NEXORA voice test failed. Check your speaker and voice settings."
        self.render()

    async def provider_changed(self, e):
        self.pending_provider = (e.control.value or "").lower()

    async def gemini_model_changed(self, e):
        self.pending_gemini_model = e.control.value or ""

    async def save_provider_settings(self, e=None):
        provider = self.pending_provider or self.state.settings.get("provider", "mock")
        model = (
            self.pending_gemini_model
            if self.pending_gemini_model is not None
            else self.state.settings.get("gemini_model", "")
        )
        try:
            result = await self.client.request(
                "PATCH", "/api/v1/settings/provider", json={"provider": provider, "gemini_model": model}
            )
            self.state.settings.update(result)
            self.state.preferences.update({"provider": provider, "gemini_model": model})
            self.state.save_preferences()
            self.pending_provider = self.pending_gemini_model = None
            self.gemini_status = (
                "Gemini API: Connected"
                if result.get("gemini_key_status") == "Configured"
                else "Gemini API key: Not configured"
            )
            self.error = ""
        except Exception as exc:
            self.error = str(exc) if isinstance(exc, ValueError) else "Could not save provider settings."
        self.render()

    async def test_gemini(self, e=None):
        model = (
            self.pending_gemini_model
            if self.pending_gemini_model is not None
            else self.state.settings.get("gemini_model", "")
        )
        try:
            result = await self.client.request("POST", "/api/v1/settings/gemini/test", json={"model": model})
            self.gemini_status = (
                result["message"]
                if result.get("status") in {"Connected", "API key missing"}
                else "Gemini API error"
            )
            self.error = ""
        except Exception:
            self.gemini_status = "Gemini API error"
        self.render()

    async def creator_website_changed(self, e):
        self.pending_creator_website = e.control.value or ""

    async def save_about_settings(self, e=None):
        website = (
            self.pending_creator_website
            if self.pending_creator_website is not None
            else self.state.settings.get("creator_website", "")
        )
        try:
            result = await self.client.request(
                "PATCH", "/api/v1/settings/about", json={"creator_website": website}
            )
            self.state.settings.update(result)
            self.pending_creator_website = None
            self.error = ""
            self.notify("About settings saved.")
        except Exception:
            self.error = "Enter a valid website beginning with http:// or https://"
        self.render()

    def feedback_changed(self, name: str):
        async def changed(e):
            value = e.control.value
            self.feedback_values[name] = int(value) if name == "overall_experience" else value

        return changed

    def feedback_report(self) -> str:
        values = self.feedback_values
        rating = int(values["overall_experience"])
        stars = "★" * rating + "☆" * (5 - rating)
        return "\n".join(
            [
                "NEXORA Tester Feedback",
                f"Overall experience: {stars} ({rating}/5)",
                f"Was anything confusing? {values['confusing'] or 'No response'}",
                f"Did you see an error? {values['error_seen'] or 'No response'}",
                f"Feature you liked: {values['liked_feature'] or 'No response'}",
                f"What should NEXORA add next? {values['add_next'] or 'No response'}",
            ]
        )

    async def copy_feedback(self, e=None):
        try:
            await ft.Clipboard().set(self.feedback_report())
            self.notify("Feedback copied. You can paste it into WhatsApp or a message.")
        except Exception:
            self.error = "Feedback could not be copied. Try Save Feedback File instead."
            self.render()

    async def save_feedback(self, e=None):
        try:
            result = await self.client.request("POST", "/api/v1/feedback", json=self.feedback_values)
            self.notify(f"Feedback saved as {result['filename']} in your NEXORA feedback folder.")
        except Exception:
            self.error = "Feedback could not be saved. Try again."
            self.render()

    def speak_handler(self, message_id):
        async def speak(e=None):
            try:
                self.voice = await self.client.request(
                    "POST", f"/api/v1/conversations/{self.conversation['id']}/messages/{message_id}/speak"
                )
            except Exception:
                self.error = "Could not play speech. Check voice settings and unmute."
            self.render()

        return speak

    async def attach(self, e=None):
        path = ft.TextField(label="File path inside your configured workspace", hint_text="example.pdf")

        async def choose(e):
            value = (path.value or "").strip()
            if value:
                self.goal.value = ("summarize pdf " if value.lower().endswith(".pdf") else "read ") + value
                self.page.pop_dialog()
                self.render()

        self.page.show_dialog(
            ft.AlertDialog(
                title=ft.Text("Attach a workspace file"), content=path, actions=[ft.Button("Use file", on_click=choose)]
            )
        )

    async def rename_chat(self, e=None):
        if not self.conversation:
            return
        title = ft.TextField(label="Chat title", value=self.conversation["title"], max_length=80)

        async def save(e):
            try:
                self.conversation = await self.client.request(
                    "PATCH", f"/api/v1/conversations/{self.conversation['id']}", json={"text": title.value}
                )
                self.page.pop_dialog()
                await self.refresh()
            except Exception:
                self.error = "Could not rename. Finish the response and enter a title."
            self.render()

        self.page.show_dialog(
            ft.AlertDialog(title=ft.Text("Rename chat"), content=title, actions=[ft.Button("Save", on_click=save)])
        )

    def rename_chat_handler(self, chat_id: str, current_title: str):
        async def rename(e=None):
            title = ft.TextField(label="Chat title", value=current_title, max_length=80)

            async def save(event=None):
                try:
                    updated = await self.client.request(
                        "PATCH", f"/api/v1/conversations/{chat_id}", json={"text": title.value}
                    )
                    if self.conversation and self.conversation.get("id") == chat_id:
                        self.conversation = updated
                    self.page.pop_dialog()
                    await self.refresh()
                except Exception:
                    self.error = "Could not rename this conversation. Try again."
                self.render()

            self.page.show_dialog(
                ft.AlertDialog(title=ft.Text("Rename chat"), content=title, actions=[ft.Button("Save", on_click=save)])
            )

        return rename

    def delete_chat_handler(self, chat_id: str):
        async def confirm(e=None):
            async def remove(event=None):
                try:
                    await self.client.request("DELETE", f"/api/v1/conversations/{chat_id}")
                    self.page.pop_dialog()
                    if self.conversation and self.conversation.get("id") == chat_id:
                        await self.new_task()
                    await self.refresh()
                except Exception:
                    self.error = "Could not delete this conversation. Try again."
                self.render()

            self.page.show_dialog(
                ft.AlertDialog(
                    title=ft.Text("Delete this conversation?"),
                    content=ft.Text("Its saved messages will be removed."),
                    actions=[
                        ft.TextButton("Keep", on_click=lambda event: self.page.pop_dialog()),
                        ft.Button("Delete", on_click=remove),
                    ],
                )
            )

        return confirm

    async def delete_chat(self, e=None):
        if not self.conversation:
            return

        async def remove(e):
            await self.client.request("DELETE", f"/api/v1/conversations/{self.conversation['id']}")
            self.page.pop_dialog()
            await self.new_task()
            await self.refresh()
            self.render()

        self.page.show_dialog(
            ft.AlertDialog(
                title=ft.Text("Delete this conversation?"),
                content=ft.Text("Its saved messages will be removed."),
                actions=[
                    ft.TextButton("Keep", on_click=lambda e: self.page.pop_dialog()),
                    ft.Button("Delete", on_click=remove),
                ],
            )
        )

    async def welcome_dialog(self):
        self.state.preferences["welcomed"] = True
        self.notify(
            "NEXORA is ready. Press the microphone to record; the first transcription downloads local speech files."
        )

    def retry_handler(self, task):
        async def retry(e=None):
            self.goal.value = task["user_text"]
            await self.submit()

        return retry

    async def disconnect(self, e=None):
        self.disconnected = True
        await self.voice_action("cancel")

    async def poll(self):
        last_snapshot = None
        while not self.disconnected:
            await asyncio.sleep(0.75)
            if self.state.busy:
                continue
            try:
                await self.sync_chat()
                self.voice = await self.client.request("GET", "/api/v1/voice")
                transcript = self.voice.get("transcript", "")
                if transcript and transcript != self.transcript_seen and not self.editing:
                    self.goal.value = transcript
                    self.transcript_seen = transcript
                if self.conversation:
                    for message in self.conversation["messages"]:
                        if (
                            message["role"] == "assistant"
                            and message["status"] == "completed"
                            and message["id"] not in self.spoken
                        ):
                            self.spoken.add(message["id"])
                            if self.voice_mode and not self.voice.get("muted"):
                                await self.speak_handler(message["id"])()
                snapshot = json.dumps([self.conversation, self.voice, self.state.task, self.error], sort_keys=True)
                # Rebuilding the control tree remounts the input and steals its focus.
                # Keep the editor untouched while typing, and do not repaint idle polls.
                if not self.editing and snapshot != last_snapshot:
                    self.render()
                    last_snapshot = snapshot
            except Exception:
                self.error = "Connection lost. Reconnect to continue."
