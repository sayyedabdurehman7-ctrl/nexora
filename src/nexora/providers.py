"""Free command-based mock provider. This is not natural-language AI."""

from typing import Protocol

from nexora.models import PlanStep, RequestType, Risk


class LLMProvider(Protocol):
    def classify_goal(self, goal: str) -> RequestType: ...
    def create_plan(self, goal: str) -> list[PlanStep]: ...


class MockLLMProvider:
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
                description=f"Run {tool} (mock plan)",
                selected_tool=tool,
                inputs=inputs,
                expected_evidence=expected,
                risk_level=Risk.MEDIUM if tool == "approval_demo" else Risk.LOW,
                dependencies=[steps[-1].id] if steps else [],
            )
            steps.append(step)
        return steps


class OpenAIProvider:
    """Optional adapter loaded only when an API key is explicitly configured."""

    def __init__(self, api_key: str, model: str):
        self.api_key, self.model = api_key, model

    def classify_goal(self, goal: str) -> RequestType:
        raise NotImplementedError("OpenAI structured adapter is scheduled after local MVP verification")

    def create_plan(self, goal: str) -> list[PlanStep]:
        raise NotImplementedError("OpenAI structured adapter is scheduled after local MVP verification")


class OllamaProvider:
    """Optional local adapter placeholder with an explicit safe failure."""

    def __init__(self, model: str, host: str = "http://127.0.0.1:11434"):
        self.model, self.host = model, host

    def classify_goal(self, goal: str) -> RequestType:
        raise NotImplementedError("Ollama structured adapter is scheduled after local MVP verification")

    def create_plan(self, goal: str) -> list[PlanStep]:
        raise NotImplementedError("Ollama structured adapter is scheduled after local MVP verification")
