"""Gemini and deterministic Mock providers behind one chat interface."""

import asyncio
import re
from collections.abc import AsyncIterator
from typing import Literal, Protocol

import httpx

from nexora.identity import (
    NEXORA_IDENTITY_POLICY,
    NEXORA_INTRODUCTION,
    NEXORA_PROJECT_DESCRIPTION,
    identity_response,
    is_identity_question,
)
from nexora.models import PlanStep, RequestType, Risk

AnswerMode = Literal["light", "medium", "strong"]

MODE_INSTRUCTIONS: dict[AnswerMode, str] = {
    "light": "Give a short, direct answer in simple language. Omit unnecessary explanation.",
    "medium": "Give a helpful answer with a clear explanation and small examples when useful.",
    "strong": (
        "Give a detailed, structured analysis with headings for the answer, key points, useful examples, and a "
        "conclusion. "
        "Show sources only when real sources were retrieved. Never invent citations or claim live research was done."
    ),
}

NO_LIVE_SOURCES = "Detailed analysis completed. Live web sources are not available in this mode."
ONLINE_UNAVAILABLE = "NEXORA's intelligent replies are temporarily unavailable. Please try again when NEXORA is ready."
DEMO_UNSUPPORTED = (
    "This feature needs NEXORA’s online service. You can still test planning, local files, PDFs, "
    "calculations and the application interface in Demo mode."
)


class LLMProvider(Protocol):
    def classify_goal(self, goal: str) -> RequestType: ...
    def create_plan(self, goal: str) -> list[PlanStep]: ...
    def stream_chat(self, messages: list[dict], answer_mode: AnswerMode = "medium") -> AsyncIterator[str]: ...
    async def health_check(self) -> dict: ...


class ProviderError(RuntimeError):
    def __init__(self, status: str, message: str):
        super().__init__(message)
        self.status = status


class FallbackProvider:
    def __init__(self, primary: LLMProvider):
        self.primary = primary
        self.mode = "online"

    def classify_goal(self, goal: str) -> RequestType:
        return MockLLMProvider().classify_goal(goal)

    def create_plan(self, goal: str) -> list[PlanStep]:
        return MockLLMProvider().create_plan(goal)

    async def health_check(self) -> dict:
        result = await self.primary.health_check()
        self.mode = "online" if result.get("status") == "Connected" else "offline"
        return result

    async def stream_chat(self, messages: list[dict], answer_mode: AnswerMode = "medium") -> AsyncIterator[str]:
        try:
            async for delta in self.primary.stream_chat(messages, answer_mode):
                self.mode = "online"
                yield delta
        except ProviderError:
            self.mode = "offline"
            yield ONLINE_UNAVAILABLE


class MockLLMProvider:
    mode = "demo"

    async def health_check(self) -> dict:
        return {"status": "Connected", "mode": "demo"}

    async def stream_chat(self, messages: list[dict], answer_mode: AnswerMode = "medium") -> AsyncIterator[str]:
        goal = messages[-1]["content"]
        lowered = goal.lower()
        normalized = " ".join(re.sub(r"[^a-z0-9 ]+", " ", lowered).split())
        local_identity = identity_response(goal)
        if local_identity:
            answer = local_identity
        elif normalized in {"what is nexora", "tell me about this platform", "tell me about nexora"}:
            answer = NEXORA_PROJECT_DESCRIPTION
        elif normalized in {"are you gemini", "are you chatgpt", "are you a chatbot"}:
            answer = "No. " + NEXORA_INTRODUCTION
        elif normalized in {"what ai service does nexora use", "which ai service does nexora use"}:
            answer = (
                "NEXORA can use the Gemini API as a backend service and a local testing fallback. "
                "NEXORA itself is your personal AI workspace."
            )
        elif any(word in lowered for word in ("worried", "overwhelmed", "stressed", "anxious")):
            answer = (
                "It sounds like you have a lot on your mind. We can break it into smaller pieces. "
                "What is the one part that feels most difficult right now?\n\n"
                "For your FYP, choose one small step for today, such as writing the project objective. "
                "You do not have to solve the whole project at once.\n\n"
                "*This offline response follows a built-in example and is not a personalised assessment.*"
            )
        elif "plan" in lowered and any(word in lowered for word in ("fyp", "project", "complet")):
            answer = (
                "## A practical FYP plan\n1. Define the question and acceptance criteria.\n"
                "2. Build one working feature.\n3. Test it and record the evidence.\n"
                "4. Write the results and limitations.\n5. Rehearse a short demonstration.\n\n"
                "*These are proposed steps; no external action was performed.*"
            )
        elif "previous" in lowered or "what did i" in lowered:
            previous = [item["content"] for item in messages[:-1] if item["role"] == "user"]
            answer = "Your previous message was: " + previous[-1] if previous else "This is our first message."
        elif lowered in ("hello", "hi", "hey"):
            answer = "Hello! We can talk about your project or work on a goal. What would you like to do?"
        elif normalized in {"help", "show me help", "how do i use nexora", "how to use nexora"}:
            answer = (
                "You can chat, create a task plan, calculate, list approved local files, extract PDF text, "
                "review saved conversations, and send tester feedback. Use the left sidebar to move between sections."
            )
        elif any(word in normalized for word in ("privacy", "private", "data safety")):
            answer = (
                "Demo conversations and settings stay on this computer in NEXORA’s local data folder. "
                "Audio is not saved by default, and sensitive actions require approval."
            )
        elif "feedback" in normalized:
            answer = (
                "Open Settings, find Tester Feedback, describe what worked or felt confusing, "
                "then save the report."
            )
        elif any(word in normalized for word in ("navigate", "navigation", "sidebar", "settings", "history")):
            answer = (
                "Use the left sidebar for a new chat, recent conversations, projects, tasks, files, memory, "
                "and Settings. "
                "Use NEXORA Workspace at the top to view a task plan and activity."
            )
        elif normalized in {"features", "supported features", "what features are available"}:
            answer = (
                "In Demo mode you can test conversations, planning, calculations, approved local files, PDF text "
                "extraction, voice controls, saved history, privacy controls, and tester feedback."
            )
        else:
            answer = DEMO_UNSUPPORTED
        if is_identity_question(goal) or answer == DEMO_UNSUPPORTED:
            pass
        elif answer_mode == "light":
            answer = answer.split("\n\n", 1)[0]
        elif answer_mode == "strong":
            answer = (
                f"## Answer\n\n{answer}\n\n"
                "## Key points\n\n- Review the main answer above.\n- Check important details before acting.\n\n"
                "## Example\n\nTry the smallest useful next step, then review the result.\n\n"
                f"## Conclusion\n\n{NO_LIVE_SOURCES}"
            )
        for offset in range(0, len(answer), 36):
            await asyncio.sleep(0.01)
            yield answer[offset : offset + 36]


class NexoraServiceProvider(MockLLMProvider):
    """Authenticated adapter for a developer-operated NEXORA service."""

    def __init__(self, base_url: str, token: str, client=None):
        self.base_url = base_url.rstrip("/")
        self._token = token
        self._client = client
        self.mode = "online" if self.base_url and self._token else "demo"

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}", "User-Agent": "NEXORA-Desktop"}

    async def health_check(self) -> dict:
        if not self.base_url or not self._token:
            self.mode = "demo"
            return {"status": "Not configured", "mode": "demo"}
        owned = self._client is None
        client = self._client or httpx.AsyncClient(timeout=httpx.Timeout(4.0))
        try:
            response = await client.get(f"{self.base_url}/health", headers=self._headers())
            response.raise_for_status()
            self.mode = "online"
            return {"status": "Connected", "mode": "online"}
        except Exception:
            self.mode = "offline"
            return {"status": "Offline", "mode": "offline"}
        finally:
            if owned:
                await client.aclose()

    async def stream_chat(self, messages: list[dict], answer_mode: AnswerMode = "medium") -> AsyncIterator[str]:
        if not self.base_url or not self._token:
            self.mode = "demo"
            raise ProviderError("Not configured", "NEXORA online service is not configured.")
        owned = self._client is None
        client = self._client or httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=5.0))
        try:
            for attempt in range(2):
                try:
                    response = await client.post(
                        f"{self.base_url}/v1/chat",
                        headers=self._headers(),
                        json={"messages": messages, "answer_mode": answer_mode},
                    )
                    response.raise_for_status()
                    payload = response.json()
                    reply = payload.get("reply") or payload.get("text")
                    if not isinstance(reply, str) or not reply.strip():
                        raise ProviderError("Provider error", "NEXORA service returned an invalid response.")
                    self.mode = "online"
                    yield reply.strip()
                    return
                except ProviderError:
                    raise
                except Exception as exc:
                    retryable = isinstance(exc, (httpx.TimeoutException, httpx.NetworkError)) or getattr(
                        getattr(exc, "response", None), "status_code", 0
                    ) >= 500
                    if retryable and attempt == 0:
                        self.mode = "reconnecting"
                        await asyncio.sleep(0.25)
                        continue
                    self.mode = "offline"
                    raise ProviderError("Offline", "NEXORA service is temporarily unavailable.") from None
        finally:
            if owned:
                await client.aclose()

    def classify_goal(self, goal: str) -> RequestType:
        lowered = goal.lower().strip()
        if any(word in lowered.split() for word in ("delete", "overwrite", "send")):
            return RequestType.SENSITIVE
        if lowered == "approval demo":
            return RequestType.CHANGE
        if lowered.endswith("?"):
            return RequestType.QUESTION
        try:
            self.create_plan(goal)
            return RequestType.READ_ONLY
        except ValueError:
            return RequestType.UNSUPPORTED

    def create_plan(self, goal: str) -> list[PlanStep]:
        steps = []
        for command in goal.split(" then "):
            command = command.strip()
            lower = command.lower()
            if lower.startswith("calculate "):
                tool, inputs, expected = (
                    "calculator",
                    {"expression": command[10:].strip()},
                    "expression and result",
                )
            elif lower == "list files":
                tool, inputs, expected = "files", {"action": "list", "path": "."}, "entries"
            elif lower.startswith("read "):
                tool, inputs, expected = (
                    "files",
                    {"action": "read", "path": command[5:].strip()},
                    "checksum and text",
                )
            elif lower.startswith("search ") and " in " in command:
                query, path = command[7:].split(" in ", 1)
                tool, inputs, expected = (
                    "files",
                    {"action": "search", "path": path, "query": query},
                    "matched lines",
                )
            elif lower.startswith("research "):
                tool, inputs, expected = (
                    "research",
                    {"query": command[9:].strip()},
                    "source title and URL",
                )
            elif lower.startswith("summarize pdf "):
                tool, inputs, expected = (
                    "pdf",
                    {"path": command[14:].strip()},
                    "page count and extracted text",
                )
            elif lower == "approval demo" and len(goal.split(" then ")) == 1:
                tool, inputs, expected = (
                    "approval_demo",
                    {},
                    "task-local simulated action acknowledgement",
                )
            else:
                raise ValueError("Unsupported mock command")
            step = PlanStep(
                order=len(steps) + 1,
                description=f"Run {tool}",
                selected_tool=tool,
                inputs=inputs,
                expected_evidence=expected,
                risk_level=Risk.MEDIUM if tool == "approval_demo" else Risk.LOW,
                dependencies=[steps[-1].id] if steps else [],
            )
            steps.append(step)
        return steps


# The service adapter reuses the same safe local task grammar as Mock mode.
MockLLMProvider.classify_goal = NexoraServiceProvider.classify_goal
MockLLMProvider.create_plan = NexoraServiceProvider.create_plan


class GeminiProvider(MockLLMProvider):
    """Google Gen AI SDK adapter for multi-turn streaming text chat."""

    def __init__(self, api_key: str, model: str, client=None):
        self._api_key, self.model, self._client = api_key, self.validate_model(model), client

    @staticmethod
    def validate_model(model: str) -> str:
        value = (model or "").strip()
        if value and (len(value) > 100 or not re.fullmatch(r"[A-Za-z0-9._:/-]+", value)):
            raise ProviderError("Invalid model", "The configured model name is invalid.")
        return value

    async def stream_chat(self, messages: list[dict], answer_mode: AnswerMode = "medium") -> AsyncIterator[str]:
        if not self._api_key:
            raise ProviderError("API key missing", "Add GEMINI_API_KEY to the local .env file and restart NEXORA.")
        if not self.model:
            raise ProviderError("Invalid model", "Enter a Gemini model in Settings or GEMINI_MODEL in .env.")
        client = self._client
        if client is None:
            from google import genai

            client = genai.Client(api_key=self._api_key)
        contents = [
            {
                "role": "model" if message["role"] == "assistant" else "user",
                "parts": [{"text": message["content"]}],
            }
            for message in messages
        ]
        try:
            stream = None
            for attempt in range(2):
                try:
                    stream = await client.aio.models.generate_content_stream(
                        model=self.model,
                        contents=contents,
                        config={
                            "system_instruction": NEXORA_IDENTITY_POLICY
                            + "\n\nResponse style for this message: "
                            + MODE_INSTRUCTIONS[answer_mode]
                        },
                    )
                    break
                except Exception as exc:
                    mapped = self.map_error(exc)
                    if mapped.status != "Offline" or attempt == 1:
                        raise mapped from None
                    await asyncio.sleep(0.25)
            if stream is None:
                raise ProviderError("Provider error", "NEXORA could not complete that request. Please try again.")
            found_text = False
            async for chunk in stream:
                text = getattr(chunk, "text", "") or ""
                if text:
                    found_text = True
                    yield text
            if not found_text:
                raise ProviderError("Provider error", "Gemini returned no text. Try changing the prompt or model.")
        except ProviderError:
            raise
        except Exception as exc:
            raise self.map_error(exc) from None
        finally:
            if self._client is None:
                await client.aio.aclose()

    async def test_connection(self) -> dict:
        if not self._api_key:
            return {
                "status": "API key missing",
                "message": "Gemini API key: Not configured",
            }
        if not self.model:
            return {"status": "Provider error", "message": "Choose a Gemini model first."}
        try:
            async for _ in self.stream_chat([{"role": "user", "content": "Reply with OK."}], "light"):
                break
            return {"status": "Connected", "message": "Gemini API: Connected"}
        except ProviderError as exc:
            return {"status": exc.status, "message": str(exc)}

    async def health_check(self) -> dict:
        return await self.test_connection()

    @staticmethod
    def map_error(exc: Exception) -> ProviderError:
        code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
        text = str(exc).lower()
        if code == 429 or "resource_exhausted" in text or "quota" in text:
            return ProviderError(
                "Quota limit reached", "The Gemini free quota is exhausted. Try again after it resets."
            )
        if code == 404 or "not found" in text or "model" in text and "invalid" in text:
            return ProviderError("Provider error", "The Gemini model is invalid or unavailable. Check GEMINI_MODEL.")
        if code == 400 and any(word in text for word in ("unsupported", "unknown field", "unexpected keyword")):
            return ProviderError("Provider error", "The selected AI service does not support this request option.")
        if any(word in text for word in ("connect", "network", "offline", "timed out", "timeout")):
            return ProviderError("Offline", "Gemini could not be reached. Check your internet connection.")
        if code in (400, 401, 403) or "api key" in text:
            return ProviderError("Provider error", "Gemini rejected the credentials or request. Check your API key.")
        return ProviderError("Provider error", "Gemini could not answer. Try again or select Mock AI.")
