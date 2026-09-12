"""Local-only FastAPI adapter. Business logic lives in Service."""

import json
import os
import sys
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

import uvicorn
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from starlette.middleware.trustedhost import TrustedHostMiddleware

from nexora.config import Settings, gemini_key_diagnostic, load_settings
from nexora.conversations import ConversationService
from nexora.core import Conflict, Service
from nexora.db import Store
from nexora.diagnostics import configure as configure_diagnostics
from nexora.diagnostics import safe_exception_category, safe_traceback
from nexora.feedback import FeedbackInput, save_feedback
from nexora.identity import normalize_creator_website
from nexora.models import GoalInput
from nexora.providers import GeminiProvider
from nexora.version import APP_VERSION
from nexora.voice import VoiceService


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or load_settings()
    diagnostic_log = configure_diagnostics(config.nexora_data_dir, config.nexora_build_profile)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        store = Store(config.database_url)
        stored_website = store.get_setting("creator_website")
        if stored_website is not None:
            config.creator_website = stored_website
        service = Service(config, store)
        service.recover_interrupted()
        app.state.service = service
        app.state.chat = ConversationService(service)
        app.state.voice = VoiceService(config)
        diagnostic_log.info("profile=%s stage=ready database=ready", config.nexora_build_profile)
        yield
        await app.state.voice.cancel()
        await app.state.chat.close()
        await service.close()
        service.store.engine.dispose()

    app = FastAPI(title="NEXORA", version=APP_VERSION, lifespan=lifespan)
    host_setting = os.getenv("NEXORA_ALLOWED_HOSTS", "127.0.0.1,localhost,testserver")
    hosts = [host.strip() for host in host_setting.split(",") if host.strip()]
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=hosts)

    @app.middleware("http")
    async def correlation(request: Request, call_next):
        request.state.correlation_id = str(uuid4())
        # No CORS: a browser page from another origin cannot mutate the local agent.
        origin = request.headers.get("origin")
        if origin and origin != str(request.base_url).rstrip("/"):
            return JSONResponse(
                status_code=403,
                content={
                    "error": {
                        "code": "ORIGIN_DENIED",
                        "message": "Cross-origin access is disabled.",
                        "correlation_id": request.state.correlation_id,
                    }
                },
            )
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.correlation_id
        return response

    def error(request: Request, status: int, code: str, message: str):
        return JSONResponse(
            status_code=status,
            content={
                "error": {
                    "code": code,
                    "message": message,
                    "correlation_id": request.state.correlation_id,
                }
            },
        )

    @app.exception_handler(KeyError)
    async def missing(request, exc):
        return error(request, 404, "NOT_FOUND", "Task or approval was not found.")

    @app.exception_handler(Conflict)
    async def conflict(request, exc):
        return error(request, 409, "STATE_CONFLICT", str(exc))

    @app.exception_handler(RequestValidationError)
    async def invalid(request, exc):
        return error(request, 422, "INVALID_INPUT", "Provide a non-empty goal up to 2000 characters.")

    @app.exception_handler(Exception)
    async def unexpected(request, exc):
        diagnostic_log.error(
            "profile=%s stage=request category=%s correlation_id=%s traceback=%s",
            config.nexora_build_profile,
            safe_exception_category(exc),
            request.state.correlation_id,
            safe_traceback(exc),
        )
        return error(request, 500, "INTERNAL_ERROR", "An internal error occurred.")

    @app.get("/health")
    async def health(request: Request):
        config = request.app.state.service.settings
        status = {
            "status": "ok",
            "version": APP_VERSION,
            "build_profile": config.nexora_build_profile,
            "mode": "demo" if config.llm_provider == "mock" else "online",
            "safe_mode": config.nexora_safe_mode,
        }
        if config.nexora_build_profile == "developer":
            status["provider"] = config.llm_provider
        return status

    @app.get("/api/v1/settings")
    async def public_settings(request: Request):
        config = request.app.state.service.settings
        # Explicit allowlist: never serialize the settings object or secret fields.
        result = {
            "build_profile": config.nexora_build_profile,
            "connection_status": "NEXORA is ready",
            "demo_mode": config.llm_provider == "mock",
            "creator_website": config.creator_website,
            "voice_mode": config.voice_mode,
            "assistant_voice_enabled": config.assistant_voice_enabled,
            "wake_phrase": config.wake_phrase,
            "safe_mode": config.nexora_safe_mode,
            "max_plan_steps": config.max_plan_steps,
            "max_tool_retries": config.max_tool_retries,
            "max_task_seconds": config.max_task_seconds,
            "workspace": str(config.nexora_workspace_dir.resolve()),
        }
        if config.nexora_build_profile == "developer":
            result.update(
                provider=config.llm_provider,
                gemini_key_status=(
                    "Configured" if config.gemini_api_key.get_secret_value() else "Not Configured"
                ),
                gemini_model=config.gemini_model,
            )
        return result

    if config.nexora_build_profile == "developer":

        @app.get("/api/v1/settings/gemini/diagnostic")
        async def gemini_diagnostic(request: Request):
            active = request.app.state.service.settings
            return {"message": gemini_key_diagnostic(active)}

        class ProviderInput(BaseModel):
            provider: Literal["gemini", "mock"]
            gemini_model: str | None = Field(default=None, max_length=100)

        @app.patch("/api/v1/settings/provider")
        async def select_provider(body: ProviderInput, request: Request):
            selected = request.app.state.chat.select_provider(body.provider, body.gemini_model)
            active = request.app.state.service.settings
            return {
                "provider": selected,
                "gemini_model": active.gemini_model,
                "gemini_key_status": (
                    "Configured" if active.gemini_api_key.get_secret_value() else "Not Configured"
                ),
            }

        class GeminiTestInput(BaseModel):
            model: str = Field(default="", max_length=100)

        @app.post("/api/v1/settings/gemini/test")
        async def test_gemini(body: GeminiTestInput, request: Request):
            active = request.app.state.service.settings
            provider = GeminiProvider(
                active.gemini_api_key.get_secret_value(), body.model.strip() or active.gemini_model
            )
            return await provider.test_connection()

    class AboutSettingsInput(BaseModel):
        creator_website: str = Field(default="", max_length=500)

        @field_validator("creator_website")
        @classmethod
        def valid_website(cls, value: str) -> str:
            return normalize_creator_website(value)

    @app.patch("/api/v1/settings/about")
    async def save_about_settings(body: AboutSettingsInput, request: Request):
        config = request.app.state.service.settings
        config.creator_website = body.creator_website
        request.app.state.service.store.set_setting("creator_website", body.creator_website)
        return {"creator_website": body.creator_website}

    @app.post("/api/v1/feedback")
    async def tester_feedback(body: FeedbackInput, request: Request):
        config = request.app.state.service.settings
        return {"saved": True, "filename": save_feedback(config.nexora_data_dir, body)}

    @app.post("/api/v1/data/export")
    async def export_local_data(request: Request):
        service = request.app.state.service
        chat_store = request.app.state.chat.store
        chats = [chat_store.get(item["id"]).model_dump(mode="json") for item in chat_store.list()]
        payload = {
            "exported_at": datetime.now(UTC).isoformat(),
            "version": APP_VERSION,
            "conversations": chats,
            "tasks": [task.model_dump(mode="json") for task in service.store.list()],
            "memory": service.store.memory_list(include_disabled=True),
        }
        folder = config.nexora_data_dir / "exports"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"NEXORA-Export-{datetime.now(UTC):%Y%m%d-%H%M%S}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"saved": True, "filename": path.name}

    @app.delete("/api/v1/data", status_code=204)
    async def clear_local_data(request: Request):
        await request.app.state.chat.close()
        request.app.state.service.store.clear_user_data()

    @app.post("/api/v1/tasks", status_code=201)
    async def create_goal(body: GoalInput, request: Request):
        return request.app.state.service.create(body.user_text, request.state.correlation_id)

    @app.get("/api/v1/tasks")
    async def history(request: Request):
        return request.app.state.service.store.list()

    @app.get("/api/v1/tasks/{task_id}")
    async def get_task(task_id: str, request: Request):
        return request.app.state.service.store.get(task_id)

    @app.post("/api/v1/tasks/{task_id}/run")
    async def run(task_id: str, request: Request):
        return request.app.state.service.start(task_id)

    @app.post("/api/v1/tasks/{task_id}/cancel")
    async def cancel(task_id: str, request: Request):
        return request.app.state.service.cancel(task_id)

    @app.get("/api/v1/tasks/{task_id}/events")
    async def events(task_id: str, request: Request):
        return request.app.state.service.store.events(task_id)

    @app.post("/api/v1/approvals/{approval_id}/approve")
    async def approve(approval_id: str, request: Request):
        return request.app.state.service.decide(approval_id, True)

    @app.post("/api/v1/approvals/{approval_id}/reject")
    async def reject(approval_id: str, request: Request):
        return request.app.state.service.decide(approval_id, False)

    @app.get("/api/v1/tools")
    async def tools(request: Request):
        service = request.app.state.service
        return service.registry.metadata(service.settings.tool_timeout_seconds)

    class MemoryInput(BaseModel):
        category: str = Field(min_length=1, max_length=40)
        content: str = Field(min_length=1, max_length=5000)
        enabled: bool = True

    @app.get("/api/v1/memory")
    async def memory_list(request: Request, include_disabled: bool = False):
        return request.app.state.service.store.memory_list(include_disabled)

    @app.post("/api/v1/memory", status_code=201)
    async def memory_create(body: MemoryInput, request: Request):
        return request.app.state.service.store.memory_save(
            str(uuid4()), body.category, body.content, enabled=body.enabled
        )

    @app.patch("/api/v1/memory/{memory_id}")
    async def memory_update(memory_id: str, body: MemoryInput, request: Request):
        existing = request.app.state.service.store.memory_get(memory_id)
        return request.app.state.service.store.memory_save(
            memory_id, body.category, body.content, source=existing["source"], enabled=body.enabled
        )

    @app.delete("/api/v1/memory/{memory_id}", status_code=204)
    async def memory_delete(memory_id: str, request: Request):
        request.app.state.service.store.memory_delete(memory_id)

    from nexora.api.conversation_routes import router

    app.include_router(router)
    return app


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "speech-worker":
        from nexora.speech_worker import main as speech_worker_main

        sys.argv = [sys.argv[0], *sys.argv[2:]]
        speech_worker_main()
        return
    uvicorn.run(
        create_app(),
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8000")),
        access_log=False,
    )


if __name__ == "__main__":
    main()
