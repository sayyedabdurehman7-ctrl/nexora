import asyncio
from types import SimpleNamespace

import flet as ft
import pytest
from fastapi.testclient import TestClient

from nexora.api.app import create_app
from nexora.conversations import ConversationService, merge_stream_text
from nexora.providers import NO_LIVE_SOURCES
from nexora.voice import VoiceService


@pytest.mark.asyncio
@pytest.mark.parametrize("focused,expected_renders", [(True, 0), (False, 2)])
async def test_poll_preserves_typing(monkeypatch, focused, expected_renders):
    from types import SimpleNamespace
    from unittest.mock import Mock

    from test_ui import PageStub

    from nexora.ui.conversation_workspace import ConversationWorkspace
    from nexora.ui.state import UIState

    class Client:
        async def request(self, *args):
            return {"phase": "idle"}

    ui = ConversationWorkspace(PageStub(), client=Client(), state=UIState(preference_path=None))
    ui.render = Mock()
    if focused:
        await ui.input_focus()
    await ui.input_change(SimpleNamespace(control=SimpleNamespace(value="My unfinished message")))
    ticks = 0

    async def tick(seconds):
        nonlocal ticks
        ticks += 1
        if ticks == 3:
            ui.disconnected = True

    monkeypatch.setattr("nexora.ui.conversation_workspace.asyncio.sleep", tick)
    await ui.poll()
    assert ui.render.call_count == expected_renders
    assert ui.goal.value == "My unfinished message"


@pytest.mark.asyncio
async def test_old_backend_shows_recoverable_error():
    from test_ui import PageStub

    from nexora.ui.conversation_workspace import ConversationWorkspace
    from nexora.ui.state import UIState

    class OldBackend:
        async def request(self, method, path, **kwargs):
            if path.endswith("/conversations"):
                raise ValueError("Request failed")
            return {} if path.endswith("/settings") else []

    ui = ConversationWorkspace(PageStub(), client=OldBackend(), state=UIState(preference_path=None))
    await ui.start()
    assert not ui.state.connected
    assert ui.connection_state == "Reconnecting"
    assert ui.root.content is not None


@pytest.mark.asyncio
async def test_multiturn_persistence_and_cancel(service):
    chat = ConversationService(service)
    item = chat.create()
    chat.send(item.id, "hello")
    await chat.running[item.id]
    chat.send(item.id, "what did I say previously?")
    await chat.running[item.id]
    result = chat.store.get(item.id)
    assert len(result.messages) == 4
    assert "hello" in result.messages[-1].content.lower()
    assert chat.rename(item.id, "My chat").title == "My chat"
    chat.send(item.id, "another question")
    await chat.cancel(item.id)
    assert chat.store.get(item.id).messages[-1].status == "cancelled"
    assert not chat.running
    await chat.delete(item.id)
    assert chat.store.list() == []


@pytest.mark.asyncio
async def test_answer_modes_are_persisted_and_strong_is_honest(service):
    chat = ConversationService(service)
    item = chat.create()
    chat.send(item.id, "Explain testing", "strong")
    await chat.running[item.id]
    saved = chat.store.get(item.id)
    assert [message.answer_mode for message in saved.messages] == ["strong", "strong"]
    assert saved.messages[-1].content.count(NO_LIVE_SOURCES) == 0
    assert "This question needs NEXORA" in saved.messages[-1].content

    light = chat.create()
    chat.send(light.id, "hello", "light")
    await chat.running[light.id]
    light_saved = chat.store.get(light.id)
    assert light_saved.messages[-1].answer_mode == "light"
    assert len(light_saved.messages[-1].content) < len(saved.messages[-1].content)


def test_stream_chunk_merge_avoids_cumulative_duplication():
    text = merge_stream_text("A sufficiently long first sentence.", "A sufficiently long first sentence. More.")
    assert text == "A sufficiently long first sentence. More."
    text = merge_stream_text(text, "sentence. More. And the conclusion.")
    assert text == "A sufficiently long first sentence. More. And the conclusion."


@pytest.mark.asyncio
async def test_reply_uses_one_stable_placeholder_then_one_final_update(service):
    class CumulativeProvider:
        async def stream_chat(self, messages, answer_mode="medium"):
            yield "A sufficiently long answer"
            await asyncio.sleep(0)
            yield "A sufficiently long answer with one ending."

    chat = ConversationService(service, CumulativeProvider())
    item = chat.create()
    initial = chat.send(item.id, "Give me a long reply", "medium")
    assert len(initial.messages) == 2
    assert initial.messages[-1].status == "responding"
    assert initial.messages[-1].content == ""

    await chat.running[item.id]
    final = chat.store.get(item.id)
    assert len(final.messages) == 2
    assert final.messages[-1].status == "completed"
    assert final.messages[-1].content == "A sufficiently long answer with one ending."


class Recorder:
    started = False

    def start(self):
        self.started = True

    def stop(self):
        self.started = False
        return b"mock-audio"

    def discard(self):
        self.started = False


class Playback:
    state = "idle"

    def play(self, data):
        assert data == b"mock-wav"
        self.state = "playing"

    def stop(self):
        self.state = "idle"

    def pause(self):
        self.state = "paused"


class Speech:
    async def transcribe(self, data):
        assert data == b"mock-audio"
        return "editable transcript"

    async def synthesize(self, text):
        return b"mock-wav"


@pytest.mark.asyncio
async def test_push_to_talk_and_playback(settings):
    recorder = Recorder()
    voice = VoiceService(settings, recorder, Playback(), Speech(), Speech())
    assert not recorder.started
    await voice.start()
    assert recorder.started
    await voice.stop_recording()
    await voice.job
    assert not recorder.started
    assert voice.transcript == "editable transcript"
    await voice.speak("hello")
    await voice.job
    assert voice.playback.state == "playing"
    voice.playback.pause()
    assert voice.playback.state == "paused"
    await voice.cancel()
    assert voice.transcript == "" and voice.playback.state == "idle"


@pytest.mark.asyncio
async def test_voice_settings_and_safe_microphone_test(settings):
    voice = VoiceService(settings, Recorder(), Playback(), Speech(), Speech())
    status = voice.configure("off", True, "  Hey NEXORA  ")
    assert status["voice_mode"] == "off"
    assert status["assistant_voice_enabled"] is True
    assert status["wake_phrase"] == "Hey NEXORA"
    assert status["wake_word_status"] == "Experimental - setup required"
    assert status["microphone_active"] is False
    assert (await voice.test_microphone())["microphone_permission"] == "Allowed"


@pytest.mark.asyncio
async def test_cancel_during_device_start(settings):
    import time

    class SlowRecorder(Recorder):
        def start(self):
            time.sleep(0.05)
            super().start()

    recorder = SlowRecorder()
    voice = VoiceService(settings, recorder, Playback(), Speech(), Speech())
    operation = asyncio.create_task(voice.start())
    await asyncio.sleep(0.01)
    await voice.cancel()
    await operation
    assert not recorder.started
    assert voice.phase == "idle"


def test_conversation_api(settings):
    with TestClient(create_app(settings)) as client:
        assert client.patch("/api/v1/settings/provider", json={"provider": "mock"}).json()["provider"] == "mock"
        assert client.patch("/api/v1/settings/provider", json={"provider": "openai"}).status_code == 422
        item = client.post("/api/v1/conversations").json()
        path = "/api/v1/conversations/" + item["id"]
        assert client.post(path + "/messages", json={"text": "hello"}).status_code == 200
        assert client.post(path + "/cancel").status_code == 200
        assert client.patch(path, json={"text": "Saved title"}).json()["title"] == "Saved title"
        assert client.get("/api/v1/voice").json()["phase"] == "idle"
        voice = client.patch(
            "/api/v1/voice/settings",
            json={"voice_mode": "wake_word", "assistant_voice_enabled": True, "wake_phrase": "Hey NEXORA"},
        ).json()
        assert voice["wake_word_status"] == "Experimental - setup required"
        assert voice["microphone_active"] is False
        assert client.delete(path).status_code == 200
        assert client.get(path).status_code == 404


@pytest.mark.asyncio
async def test_conversation_ui(settings, monkeypatch):
    import httpx
    from test_ui import PageStub

    from nexora.ui.conversation_workspace import ConversationWorkspace
    from nexora.ui.state import UIState

    api = create_app(settings)
    real_client = httpx.AsyncClient

    def local_client(**kwargs):
        kwargs["transport"] = httpx.ASGITransport(app=api)
        return real_client(**kwargs)

    monkeypatch.setattr("nexora.ui.client.httpx.AsyncClient", local_client)
    async with api.router.lifespan_context(api):
        api.state.voice = VoiceService(settings, Recorder(), Playback(), Speech(), Speech())
        ui = ConversationWorkspace(PageStub(), state=UIState(preference_path=None))
        await ui.start()
        assert ui.state.panel_open is False
        from nexora.ui.components.chat_composer import composer

        rendered_composer = composer(ui)
        action_row = rendered_composer.content.controls[1]
        assert isinstance(action_row.controls[0], ft.IconButton)
        assert isinstance(action_row.controls[1], ft.IconButton)
        assert isinstance(action_row.controls[2], ft.PopupMenuButton)
        assert [item.content.value for item in action_row.controls[2].items] == [
            "Low",
            "Medium",
            "Strong / Deep Reply",
        ]
        await ui.answer_mode_handler("strong")()
        assert ui.answer_mode == "strong"
        ui.goal.value = "hello"
        await ui.submit()
        await asyncio.gather(*list(api.state.chat.running.values()))
        await ui.sync_chat()
        assert len(ui.conversation["messages"]) == 2
        assert all(message["answer_mode"] == "strong" for message in ui.conversation["messages"])
        for width, height in [(1440, 900), (900, 650), (640, 550)]:
            ui.page.width, ui.page.height = width, height
            ui.render()
        await ui.microphone()
        assert ui.voice["phase"] == "recording"
        await ui.microphone()
        await api.state.voice.job
        assert api.state.voice.transcript == "editable transcript"
        ui.goal.value = "approval demo"
        await ui.submit()
        assert ui.state.task["status"] == "AWAITING_APPROVAL"
        assert ui.state.panel_open is False
        assert ui.page.dialogs[-1].modal
        ui.page.width = 1440
        await ui.open_plan()
        assert ui.state.panel_open is True
        assert ui.state.plan_expanded is True
        await ui.stop()
        assert api.state.service.store.get(ui.state.task["id"]).status == "CANCELLED"
        await ui.new_task()
        assert ui.conversation is None


@pytest.mark.asyncio
async def test_five_message_layout_uses_stable_keys(settings, monkeypatch):
    import httpx
    from test_ui import PageStub

    from nexora.ui.components.sidebar import sidebar
    from nexora.ui.conversation_workspace import ConversationWorkspace
    from nexora.ui.pages.chat import chat
    from nexora.ui.state import UIState

    api = create_app(settings)
    real_client = httpx.AsyncClient

    def local_client(**kwargs):
        kwargs["transport"] = httpx.ASGITransport(app=api)
        return real_client(**kwargs)

    monkeypatch.setattr("nexora.ui.client.httpx.AsyncClient", local_client)
    async with api.router.lifespan_context(api):
        ui = ConversationWorkspace(PageStub(), state=UIState(preference_path=None))
        await ui.start()
        for number in range(5):
            ui.goal.value = f"message {number + 1}"
            await ui.submit()
            await asyncio.gather(*list(api.state.chat.running.values()))
            await ui.sync_chat()
        assert len(ui.conversation["messages"]) == 10
        message_list = chat(ui).controls[0]
        keys = [item.key for item in message_list.controls]
        assert len(keys) == len(set(keys)) == 10
        recent_list = sidebar(ui, compact=False).content.controls[4]
        assert recent_list.key == "recent-chats"
        assert recent_list.scroll == ft.ScrollMode.AUTO


@pytest.mark.asyncio
async def test_large_chat_keeps_stable_shell_and_scroll_policy(settings, monkeypatch):
    import httpx
    from test_ui import PageStub

    from nexora.ui.conversation_workspace import ConversationWorkspace
    from nexora.ui.pages.chat import chat
    from nexora.ui.state import UIState

    api = create_app(settings)
    real_client = httpx.AsyncClient

    def local_client(**kwargs):
        kwargs["transport"] = httpx.ASGITransport(app=api)
        return real_client(**kwargs)

    monkeypatch.setattr("nexora.ui.client.httpx.AsyncClient", local_client)
    async with api.router.lifespan_context(api):
        ui = ConversationWorkspace(PageStub(), state=UIState(preference_path=None))
        await ui.start()
        ui.conversation = {
            "id": "large-chat",
            "title": "Long conversation",
            "messages": [
                {
                    "id": f"message-{number}",
                    "role": "user" if number % 2 == 0 else "assistant",
                    "content": ("A long response paragraph. " * 30) if number == 59 else f"Message {number}",
                    "status": "completed",
                    "answer_mode": "medium",
                }
                for number in range(60)
            ],
        }
        ui.chat_at_bottom = False
        rendered = chat(ui)
        message_list, rendered_composer = rendered.controls
        keys = [item.key for item in message_list.controls]
        assert len(keys) == len(set(keys)) == 60
        assert message_list.auto_scroll is False
        assert rendered_composer is rendered.controls[-1]

        ui.render()
        stable_sidebar = ui._sidebar_control
        ui.render()
        assert ui._sidebar_control is stable_sidebar

        await ui.chat_scroll(SimpleNamespace(pixels=890, max_scroll_extent=1000))
        assert ui.chat_at_bottom is False
        await ui.chat_scroll(SimpleNamespace(pixels=901, max_scroll_extent=1000))
        assert ui.chat_at_bottom is True
