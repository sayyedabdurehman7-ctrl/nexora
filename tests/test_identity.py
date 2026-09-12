from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from nexora.api.app import create_app
from nexora.conversations import ConversationService, Message
from nexora.identity import (
    NEXORA_INTRODUCTION,
    NEXORA_PROJECT_DESCRIPTION,
    SAFE_IDENTITY_FALLBACK,
    violates_identity,
)


async def ask(chat: ConversationService, question: str) -> str:
    conversation = chat.create()
    chat.send(conversation.id, question)
    await chat.running[conversation.id]
    return chat.store.get(conversation.id).messages[-1].content


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("Who are you?", NEXORA_INTRODUCTION),
        ("What is NEXORA?", NEXORA_PROJECT_DESCRIPTION),
        ("Tell me about this platform.", NEXORA_PROJECT_DESCRIPTION),
        ("Are you Gemini?", "No. " + NEXORA_INTRODUCTION),
        ("Are you a chatbot?", "No. " + NEXORA_INTRODUCTION),
    ],
)
async def test_nexora_identity_questions(service, question, expected):
    answer = await ask(ConversationService(service), question)
    assert answer == expected
    assert not violates_identity(answer, question)


@pytest.mark.asyncio
async def test_provider_question_is_honest_without_changing_nexora_identity(service):
    question = "What AI service does NEXORA use?"
    answer = await ask(ConversationService(service), question)
    assert "Gemini API" in answer
    assert "NEXORA itself is your personal AI workspace" in answer
    assert not violates_identity(answer, question)


class ScriptedProvider:
    def __init__(self, replies):
        self.replies = iter(replies)
        self.calls = 0

    async def stream_chat(self, messages, answer_mode="medium"):
        self.calls += 1
        yield next(self.replies)


@pytest.mark.asyncio
async def test_unsafe_identity_is_rewritten_once_before_save(service):
    provider = ScriptedProvider(["I am Gemini, built by Google.", NEXORA_INTRODUCTION])
    chat = ConversationService(service, provider)
    answer = await ask(chat, "Who are you?")
    assert provider.calls == 2
    assert answer == NEXORA_INTRODUCTION
    assert "Gemini" not in answer and "Google" not in answer


@pytest.mark.asyncio
async def test_second_unsafe_identity_uses_exact_safe_fallback(service):
    provider = ScriptedProvider(["I am ChatGPT.", "As an AI model, I can help."])
    chat = ConversationService(service, provider)
    answer = await ask(chat, "Please introduce yourself.")
    assert provider.calls == 2
    assert answer == SAFE_IDENTITY_FALLBACK


def test_old_unsafe_reply_is_hidden_and_not_spoken(settings):
    app = create_app(settings)

    class VoiceCapture:
        def __init__(self):
            self.text = ""

        async def speak(self, text):
            self.text = text
            return {"phase": "speaking"}

        async def cancel(self):
            return None

    with TestClient(app) as client:
        voice = VoiceCapture()
        app.state.voice = voice
        conversation = app.state.chat.create()
        conversation.messages += [
            Message(role="user", content="Please introduce yourself."),
            Message(role="assistant", content="I am Gemini, an AI language model."),
        ]
        app.state.chat.store.save(conversation)

        displayed = client.get(f"/api/v1/conversations/{conversation.id}").json()
        assert displayed["messages"][-1]["content"] == SAFE_IDENTITY_FALLBACK
        message_id = conversation.messages[-1].id
        assert client.post(f"/api/v1/conversations/{conversation.id}/messages/{message_id}/speak").status_code == 200
        assert voice.text == SAFE_IDENTITY_FALLBACK
        assert "Gemini" not in voice.text


def test_normal_loading_text_and_composer_hide_provider_names():
    from nexora.ui.components.chat_composer import composer
    from nexora.ui.pages.chat import _message_text

    state = SimpleNamespace(task=None, busy=False, connected=True, settings={"provider": "gemini"})
    app = SimpleNamespace(
        state=state,
        colors={"muted": "#777", "border": "#ddd", "surface": "#fff"},
        voice={"phase": "idle"},
        answer_mode="medium",
        conversation=None,
        goal=SimpleNamespace(disabled=False),
        answer_mode_handler=lambda mode: None,
        attach=None,
        microphone=None,
        stop=None,
        submit=None,
    )
    rendered = composer(app)
    action_row = rendered.content.controls[1]
    visible_text = " ".join(
        control.value for control in action_row.controls if hasattr(control, "value") and control.value
    )
    assert "Gemini" not in visible_text and "Mock" not in visible_text
    assert _message_text(app, {"status": "responding", "content": ""}) == ("", "NEXORA is thinking...")
