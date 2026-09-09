"""Local-only FastAPI adapter. Business logic lives in Service."""

from contextlib import asynccontextmanager
from uuid import uuid4

import uvicorn
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from nexora.config import Settings
from nexora.core import Conflict, Service
from nexora.db import Store
from nexora.models import GoalInput


def create_app(settings: Settings | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        config = settings or Settings()
        service = Service(config, Store(config.database_url))
        service.recover_interrupted()
        app.state.service = service
        yield
        await service.close()
        service.store.engine.dispose()

    app = FastAPI(title="NEXORA (mock, Phase 1)", lifespan=lifespan)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"])

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
        return error(request, 500, "INTERNAL_ERROR", "An internal error occurred.")

    @app.get("/health")
    async def health():
        return {"status": "ok", "provider": "mock", "safe_mode": True}

    @app.get("/api/v1/settings")
    async def public_settings(request: Request):
        config = request.app.state.service.settings
        # Explicit allowlist: never serialize the settings object or secret fields.
        return {
            "provider": config.llm_provider,
            "safe_mode": config.nexora_safe_mode,
            "max_plan_steps": config.max_plan_steps,
            "max_tool_retries": config.max_tool_retries,
            "max_task_seconds": config.max_task_seconds,
            "workspace": str(config.nexora_workspace_dir.resolve()),
        }

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

    return app


def main() -> None:
    uvicorn.run("nexora.api.app:create_app", factory=True, host="127.0.0.1", port=8000, access_log=False)


if __name__ == "__main__":
    main()
