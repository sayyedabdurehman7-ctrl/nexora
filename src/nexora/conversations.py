"""Durable multi-turn conversations and asynchronous responses beside the task engine."""

import asyncio
from typing import Literal

from pydantic import Field
from sqlalchemy import String, Text, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from nexora.core import Conflict
from nexora.db import Base, Store
from nexora.identity import (
    IDENTITY_REWRITE_REQUEST,
    SAFE_IDENTITY_FALLBACK,
    is_identity_question,
    violates_identity,
)
from nexora.models import StrictModel, new_id, now
from nexora.providers import (
    NO_LIVE_SOURCES,
    AnswerMode,
    LLMProvider,
    NexoraServiceProvider,
    ProviderError,
)


class Message(StrictModel):
    id: str = Field(default_factory=new_id)
    role: Literal["user", "assistant"]
    content: str = ""
    status: str = "completed"
    task_id: str | None = None
    answer_mode: AnswerMode = "medium"
    created_at: str = Field(default_factory=lambda: now().isoformat())


class Conversation(StrictModel):
    id: str = Field(default_factory=new_id)
    title: str = "New chat"
    created_at: str = Field(default_factory=lambda: now().isoformat())
    updated_at: str = Field(default_factory=lambda: now().isoformat())
    messages: list[Message] = Field(default_factory=list)


class ConversationRecord(Base):
    __tablename__ = "conversations"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    snapshot: Mapped[str] = mapped_column(Text)


class ConversationStore:
    def __init__(self, store: Store):
        self.store = store

    def save(self, conversation: Conversation) -> None:
        conversation.updated_at = now().isoformat()
        with Session(self.store.engine) as session, session.begin():
            session.merge(ConversationRecord(id=conversation.id, snapshot=conversation.model_dump_json()))

    def get(self, conversation_id: str) -> Conversation:
        with Session(self.store.engine) as session:
            record = session.get(ConversationRecord, conversation_id)
            if record is None:
                raise KeyError(conversation_id)
            return Conversation.model_validate_json(record.snapshot)

    def list(self) -> list[dict]:
        with Session(self.store.engine) as session:
            records = [
                Conversation.model_validate_json(row.snapshot) for row in session.scalars(select(ConversationRecord))
            ]
        return [
            {"id": item.id, "title": item.title, "updated_at": item.updated_at, "message_count": len(item.messages)}
            for item in sorted(records, key=lambda item: item.updated_at, reverse=True)
        ]

    def delete(self, conversation_id: str) -> None:
        with Session(self.store.engine) as session, session.begin():
            record = session.get(ConversationRecord, conversation_id)
            if record is None:
                raise KeyError(conversation_id)
            session.delete(record)


class ConversationService:
    def __init__(self, task_service, provider: LLMProvider | None = None):
        self.tasks = task_service
        self.store = ConversationStore(task_service.store)
        self.provider = provider or self.make_provider(task_service.settings.llm_provider)
        self.running: dict[str, asyncio.Task] = {}
        for entry in self.store.list():
            conversation = self.store.get(entry["id"])
            changed = False
            for message in conversation.messages:
                if message.status == "responding":
                    message.status = "failed"
                    message.content += "\n\nResponse interrupted by restart. Please retry."
                    changed = True
            if changed:
                self.store.save(conversation)

    def make_provider(self, name: str) -> LLMProvider:
        config = self.tasks.settings
        if config.nexora_build_profile == "developer" and config.llm_provider == "gemini":
            from nexora.providers import FallbackProvider, GeminiProvider

            return FallbackProvider(GeminiProvider(config.gemini_api_key.get_secret_value(), config.gemini_model))
        return NexoraServiceProvider(
            config.nexora_service_url,
            config.nexora_service_token.get_secret_value(),
        )

    @property
    def mode(self) -> str:
        return getattr(self.provider, "mode", "offline")

    @property
    def connection_status(self) -> str:
        return {
            "online": "NEXORA is ready",
            "reconnecting": "Reconnecting…",
            "offline": "NEXORA is temporarily offline",
        }.get(self.mode, "NEXORA is temporarily offline")

    async def initialize(self) -> None:
        await self.provider.health_check()

    def select_provider(self, name: str, gemini_model: str | None = None) -> str:
        if self.running:
            raise Conflict("Stop the current response before changing providers.")
        if gemini_model is not None:
            self.tasks.settings.gemini_model = gemini_model.strip()
        self.provider = self.make_provider(name)
        self.tasks.settings.llm_provider = name
        return name

    def create(self) -> Conversation:
        conversation = Conversation()
        self.store.save(conversation)
        return conversation

    def rename(self, conversation_id: str, title: str) -> Conversation:
        if conversation_id in self.running:
            raise Conflict("Wait for the response to finish before renaming.")
        conversation = self.store.get(conversation_id)
        conversation.title = title.strip()
        if not conversation.title:
            raise Conflict("Give the chat a title.")
        self.store.save(conversation)
        return conversation

    async def delete(self, conversation_id: str) -> None:
        await self.cancel(conversation_id)
        self.store.delete(conversation_id)

    def send(self, conversation_id: str, text: str, answer_mode: AnswerMode = "medium") -> Conversation:
        conversation = self.store.get(conversation_id)
        if conversation_id in self.running:
            raise Conflict("Stop or finish the current response first.")
        if any(
            message.task_id
            and self.tasks.store.get(message.task_id).status
            not in {"COMPLETED", "FAILED", "BLOCKED", "CANCELLED", "TIMED_OUT"}
            for message in conversation.messages
        ):
            raise Conflict("Stop or finish the current task first.")
        text = text.strip()
        if not text:
            raise Conflict("Enter a message first.")
        if not conversation.messages:
            conversation.title = text[:60]
        conversation.messages.append(Message(role="user", content=text, answer_mode=answer_mode))
        lower = text.lower()
        action = lower.startswith(
            (
                "calculate ",
                "list files",
                "read ",
                "search ",
                "research ",
                "summarize pdf ",
                "approval demo",
                "delete ",
                "overwrite ",
            )
        )
        if action:
            task = self.tasks.create(text)
            if task.status == "PLANNED":
                task = self.tasks.start(task.id)
            conversation.messages.append(
                Message(
                    role="assistant",
                    task_id=task.id,
                    content=task.final_result,
                    status="task",
                    answer_mode=answer_mode,
                )
            )
            self.store.save(conversation)
        else:
            conversation.messages.append(Message(role="assistant", status="responding", answer_mode=answer_mode))
            self.store.save(conversation)
            self.running[conversation_id] = asyncio.create_task(self._respond(conversation, answer_mode))
        return conversation

    async def _respond(self, conversation: Conversation, answer_mode: AnswerMode) -> None:
        message = conversation.messages[-1]
        context = [
            {"role": item.role, "content": item.content}
            for item in conversation.messages[:-1][-20:]
            if item.status == "completed"
        ]
        try:
            async with asyncio.timeout(self.tasks.settings.max_task_seconds):
                response = await self._collect_response(context, answer_mode)
                user_text = context[-1]["content"]
                if (
                    answer_mode == "strong"
                    and not is_identity_question(user_text)
                    and NO_LIVE_SOURCES not in response
                ):
                    response = response.rstrip() + "\n\n" + NO_LIVE_SOURCES
                if violates_identity(response, user_text):
                    try:
                        rewrite_context = [
                            *context,
                            {"role": "assistant", "content": response},
                            {"role": "user", "content": IDENTITY_REWRITE_REQUEST},
                        ]
                        rewritten = await self._collect_response(rewrite_context, answer_mode)
                        if (
                            answer_mode == "strong"
                            and not is_identity_question(user_text)
                            and NO_LIVE_SOURCES not in rewritten
                        ):
                            rewritten = rewritten.rstrip() + "\n\n" + NO_LIVE_SOURCES
                        response = (
                            SAFE_IDENTITY_FALLBACK
                            if violates_identity(rewritten, user_text)
                            else rewritten
                        )
                    except Exception:
                        response = SAFE_IDENTITY_FALLBACK
                message.content = response
            if not message.content.strip():
                raise ValueError("Empty response")
            message.status = "completed"
        except asyncio.CancelledError:
            message.status = "cancelled"
            message.content += "\n\nResponse stopped."
        except ProviderError:
            message.status = "failed"
            message.content = "NEXORA is temporarily unable to connect to its online service. Please try again."
        except Exception:
            message.status = "failed"
            message.content = "Something went wrong. Try again."
        finally:
            self.store.save(conversation)
            self.running.pop(conversation.id, None)

    async def _collect_response(self, context: list[dict], answer_mode: AnswerMode) -> str:
        response = ""
        async for delta in self.provider.stream_chat(context, answer_mode):
            response = merge_stream_text(response, delta)
            if len(response) > 40000:
                raise ValueError("Response exceeded limit")
        return response

    async def cancel(self, conversation_id: str) -> Conversation:
        conversation = self.store.get(conversation_id)
        runner = self.running.get(conversation_id)
        if runner:
            runner.cancel()
            await asyncio.gather(runner, return_exceptions=True)
            self.running.pop(conversation_id, None)
            conversation = self.store.get(conversation_id)
            for message in conversation.messages:
                if message.status == "responding":
                    message.status = "cancelled"
                    message.content += "\n\nResponse stopped."
            self.store.save(conversation)
        for message in conversation.messages:
            if message.task_id:
                self.tasks.cancel(message.task_id)
        return self.store.get(conversation_id)

    async def close(self):
        for conversation_id in list(self.running):
            await self.cancel(conversation_id)


def merge_stream_text(existing: str, incoming: str) -> str:
    """Merge incremental or cumulative provider chunks without repeating long text."""
    if not incoming:
        return existing
    if existing and incoming.startswith(existing):
        return incoming
    if len(incoming) >= 12 and existing.endswith(incoming):
        return existing
    max_overlap = min(len(existing), len(incoming))
    for size in range(max_overlap, 11, -1):
        if existing.endswith(incoming[:size]):
            return existing + incoming[size:]
    return existing + incoming
