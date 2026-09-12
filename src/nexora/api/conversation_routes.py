"""Conversation and explicit voice controls for the local UI."""

from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from nexora.core import Conflict
from nexora.identity import SAFE_IDENTITY_FALLBACK, violates_identity

router = APIRouter(prefix="/api/v1")


class TextInput(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


class MessageInput(TextInput):
    answer_mode: Literal["light", "medium", "strong"] = "medium"


class VoiceSettingsInput(BaseModel):
    voice_mode: Literal["off", "push_to_talk", "wake_word"]
    assistant_voice_enabled: bool = False
    wake_phrase: str = Field(default="Hey NEXORA", min_length=1, max_length=40)


@router.get("/conversations")
async def conversations(request: Request):
    return request.app.state.chat.store.list()


@router.post("/conversations", status_code=201)
async def create(request: Request):
    return request.app.state.chat.create()


@router.get("/conversations/{chat_id}")
async def get(chat_id: str, request: Request):
    chat = request.app.state.chat.store.get(chat_id)
    last_user_text = ""
    for message in chat.messages:
        if message.role == "user":
            last_user_text = message.content
            continue
        if message.task_id:
            task = request.app.state.service.store.get(message.task_id)
            message.content = task.final_result
            for step in task.plan.steps:
                if step.result and step.result.success:
                    data = step.result.data
                    if "text" in data:
                        message.content += "\n\n" + str(data["text"])[:12000]
                    elif "value" in data:
                        message.content += "\n\nResult: " + str(data["value"])
                    elif "entries" in data:
                        message.content += "\n\n" + "\n".join(str(item) for item in data["entries"])
        elif violates_identity(message.content, last_user_text):
            message.content = SAFE_IDENTITY_FALLBACK
    return chat


@router.patch("/conversations/{chat_id}")
async def rename(chat_id: str, body: TextInput, request: Request):
    return request.app.state.chat.rename(chat_id, body.text[:80])


@router.delete("/conversations/{chat_id}")
async def delete(chat_id: str, request: Request):
    await request.app.state.chat.delete(chat_id)
    return {"deleted": True}


@router.post("/conversations/{chat_id}/messages")
async def send(chat_id: str, body: MessageInput, request: Request):
    return request.app.state.chat.send(chat_id, body.text, body.answer_mode)


@router.post("/conversations/{chat_id}/cancel")
async def cancel(chat_id: str, request: Request):
    await request.app.state.voice.cancel()
    return await request.app.state.chat.cancel(chat_id)


@router.post("/conversations/{chat_id}/messages/{message_id}/speak")
async def speak(chat_id: str, message_id: str, request: Request):
    chat = request.app.state.chat.store.get(chat_id)
    message = next((m for m in chat.messages if m.id == message_id), None)
    if not message or message.role != "assistant" or message.status != "completed":
        raise Conflict("Only completed assistant responses can be played.")
    message_index = chat.messages.index(message)
    user_text = next(
        (item.content for item in reversed(chat.messages[:message_index]) if item.role == "user"),
        "",
    )
    speech_text = SAFE_IDENTITY_FALLBACK if violates_identity(message.content, user_text) else message.content
    return await request.app.state.voice.speak(speech_text)


@router.get("/voice")
async def voice(request: Request):
    return request.app.state.voice.status()


@router.patch("/voice/settings")
async def voice_settings(body: VoiceSettingsInput, request: Request):
    return request.app.state.voice.configure(
        body.voice_mode,
        body.assistant_voice_enabled,
        body.wake_phrase,
    )


@router.post("/voice/test-microphone")
async def test_microphone(request: Request):
    return await request.app.state.voice.test_microphone()


@router.post("/voice/test-voice")
async def test_voice(request: Request):
    return await request.app.state.voice.speak("Hello, this is NEXORA.")


@router.post("/voice/{action}")
async def voice_action(action: str, request: Request):
    service = request.app.state.voice
    if action == "start":
        return await service.start()
    if action == "stop":
        return await service.stop_recording()
    if action == "cancel":
        return await service.cancel()
    if action == "pause":
        service.playback.pause()
    elif action == "mute":
        service.muted = not service.muted
        if service.muted:
            await service.cancel()
    else:
        raise Conflict("Unknown voice control.")
    return service.status()
