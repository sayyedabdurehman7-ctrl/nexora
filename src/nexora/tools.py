"""Two bounded, read-only tools and their evidence verifiers."""

import ast
import hashlib
import math
import operator
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, Protocol

from pydantic import Field

from nexora.models import Risk, StrictModel, ToolResult


class ToolError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class CalculatorInput(StrictModel):
    expression: str = Field(min_length=1, max_length=200, strict=True)


def calculate(expression: str) -> float:
    """Only numeric constants and bounded arithmetic, never eval or function calls."""
    operations = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
    }
    try:
        tree = ast.parse(expression, mode="eval")
        if len(list(ast.walk(tree))) > 60:
            raise ValueError("Too complex")

        def visit(node: ast.AST) -> float:
            if isinstance(node, ast.Constant) and type(node.value) in (int, float):
                value = float(node.value)
            elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
                value = visit(node.operand) * (-1 if isinstance(node.op, ast.USub) else 1)
            elif isinstance(node, ast.BinOp) and type(node.op) in operations:
                left, right = visit(node.left), visit(node.right)
                if isinstance(node.op, ast.Pow) and abs(right) > 12:
                    raise ValueError("Exponent limit")
                value = operations[type(node.op)](left, right)
            else:
                raise ValueError("Unsupported expression")
            if not isinstance(value, (int, float)) or not math.isfinite(value) or abs(value) > 1e12:
                raise ValueError("Numeric limit")
            return value

        return visit(tree.body)
    except (SyntaxError, ValueError, OverflowError, ZeroDivisionError, TypeError, RecursionError):
        raise ToolError("INVALID_EXPRESSION", "Use bounded arithmetic with numbers only.") from None


class Tool(Protocol):
    name: str
    input_model: type[StrictModel]
    risk: Risk

    async def execute(self, inputs: StrictModel) -> ToolResult: ...
    async def verify(self, inputs: StrictModel, result: ToolResult) -> bool: ...


class Calculator:
    name = "calculator"
    input_model = CalculatorInput
    risk = Risk.LOW

    async def execute(self, inputs: CalculatorInput) -> ToolResult:
        value = calculate(inputs.expression)
        return ToolResult(
            success=True,
            data={"value": value},
            evidence={
                "expression": inputs.expression,
                "value": value,
            },
        )

    async def verify(self, inputs: CalculatorInput, result: ToolResult) -> bool:
        value = calculate(inputs.expression)
        return (
            result.success
            and result.data == {"value": value}
            and result.evidence
            == {
                "expression": inputs.expression,
                "value": value,
            }
        )


class FileInput(StrictModel):
    action: Literal["list", "read", "search"]
    path: str = Field(min_length=1, max_length=500, strict=True)
    query: str = Field(default="", max_length=200, strict=True)


class Files:
    name = "files"
    input_model = FileInput
    risk = Risk.LOW
    suffixes = {".txt", ".md", ".csv", ".json", ".log"}
    max_bytes = 262144
    max_entries = 500

    def __init__(self, workspace: Path):
        workspace.mkdir(parents=True, exist_ok=True)
        self.workspace = workspace.resolve()

    def resolve(self, relative: str) -> Path:
        path = Path(relative)
        if path.is_absolute() or path.drive or ".." in path.parts or ":" in relative:
            raise ToolError("PATH_DENIED", "Only relative paths inside the workspace are allowed.")
        resolved = (self.workspace / path).resolve()
        if not resolved.is_relative_to(self.workspace):
            raise ToolError("PATH_DENIED", "Path escapes the approved workspace.")
        return resolved

    def snapshot(self, inputs: FileInput) -> ToolResult:
        path = self.resolve(inputs.path)
        if inputs.action == "list":
            entries = []
            for child in path.iterdir():
                if len(entries) >= self.max_entries:
                    raise ToolError("TOO_MANY_FILES", "Folder exceeds the 500-entry limit.")
                if child.is_symlink() or not child.resolve().is_relative_to(self.workspace):
                    continue
                entries.append(child.name)
            entries.sort()
            return ToolResult(
                success=True,
                data={"entries": entries},
                evidence={
                    "path": str(path),
                    "entry_count": len(entries),
                    "entries": entries,
                },
            )
        if path.suffix.lower() not in self.suffixes:
            raise ToolError("TYPE_DENIED", "Only .txt, .md, .csv, .json and .log files are supported.")
        with path.open("rb") as handle:
            raw = handle.read(self.max_bytes + 1)
        if len(raw) > self.max_bytes:
            raise ToolError("FILE_TOO_LARGE", "File exceeds the 256 KiB limit.")
        content = raw.decode("utf-8")
        data = (
            {"text": content}
            if inputs.action == "read"
            else {
                "matches": [
                    {"line": index, "text": line}
                    for index, line in enumerate(content.splitlines(), 1)
                    if inputs.query in line
                ]
            }
        )
        return ToolResult(
            success=True,
            data=data,
            evidence={
                "path": str(path),
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            },
        )

    async def execute(self, inputs: FileInput) -> ToolResult:
        return self.snapshot(inputs)

    async def verify(self, inputs: FileInput, result: ToolResult) -> bool:
        fresh = self.snapshot(inputs)
        return result.success and fresh.data == result.data and fresh.evidence == result.evidence


class PDFInput(StrictModel):
    path: str = Field(min_length=1, max_length=500, strict=True)


class PDFReader:
    name = "pdf"
    input_model = PDFInput
    risk = Risk.LOW

    def __init__(self, workspace: Path):
        self.workspace = workspace.resolve()

    def resolve(self, relative: str) -> Path:
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts or ":" in relative:
            raise ToolError("PATH_DENIED", "Only relative PDF paths inside the workspace are allowed.")
        resolved = (self.workspace / path).resolve()
        if not resolved.is_relative_to(self.workspace) or resolved.suffix.lower() != ".pdf":
            raise ToolError("PDF_DENIED", "Only approved local PDF files are supported.")
        return resolved

    async def execute(self, inputs: PDFInput) -> ToolResult:
        path = self.resolve(inputs.path)
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise ToolError(
                "PDF_DEPENDENCY_MISSING",
                "Install the optional PDF dependency with: pip install -e '.[mvp]'",
            ) from exc
        try:
            reader = PdfReader(str(path))
            text = "\n\n".join((page.extract_text() or "") for page in reader.pages)
            metadata = {str(key).lstrip("/"): str(value) for key, value in (reader.metadata or {}).items()}
            raw = path.read_bytes()
            return ToolResult(
                success=True,
                data={"text": text, "metadata": metadata, "page_count": len(reader.pages)},
                evidence={
                    "path": str(path),
                    "bytes": len(raw),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "page_count": len(reader.pages),
                    "extracted_chars": len(text),
                    "retrieved_at": datetime.now(UTC).isoformat(),
                },
            )
        except (OSError, ValueError, IndexError) as exc:
            raise ToolError("PDF_READ_FAILED", "The approved PDF could not be read safely.") from exc

    async def verify(self, inputs: PDFInput, result: ToolResult) -> bool:
        fresh = await self.execute(inputs)
        return (
            result.success
            and fresh.data == result.data
            and all(
                fresh.evidence.get(key) == result.evidence.get(key)
                for key in ("path", "bytes", "sha256", "page_count", "extracted_chars")
            )
        )


class ResearchInput(StrictModel):
    query: str = Field(min_length=2, max_length=300, strict=True)


class MockResearch:
    name = "research"
    input_model = ResearchInput
    risk = Risk.LOW

    async def execute(self, inputs: ResearchInput) -> ToolResult:
        retrieved = datetime.now(UTC).isoformat()
        source = {
            "title": f"Mock research overview: {inputs.query}",
            "url": "mock://nexora/research",
            "retrieved_at": retrieved,
            "claim": f"This is deterministic placeholder evidence for: {inputs.query}.",
        }
        return ToolResult(
            success=True,
            data={"summary": source["claim"], "sources": [source]},
            evidence={"source_count": 1, "sources": [source]},
        )

    async def verify(self, inputs: ResearchInput, result: ToolResult) -> bool:
        return (
            result.success
            and len(result.data.get("sources", [])) > 0
            and all(source.get("url", "").startswith("mock://") for source in result.data["sources"])
        )


class Registry:
    def __init__(self):
        self.tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self.tools:
            raise ValueError("Duplicate tool name")
        self.tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        if name not in self.tools:
            raise ToolError("UNKNOWN_TOOL", "Tool is not registered.")
        return self.tools[name]

    def metadata(self, timeout: float) -> list[dict]:
        return [
            {
                "name": tool.name,
                "risk": tool.risk,
                "timeout_seconds": timeout,
                "input_schema": tool.input_model.model_json_schema(),
                "verification": "independent recomputation or file read-back",
            }
            for tool in self.tools.values()
        ]
