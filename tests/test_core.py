import asyncio

import pytest
from pydantic import ValidationError

from nexora.config import Settings
from nexora.core import Conflict
from nexora.db import Store
from nexora.models import ApprovalState, RequestType, Risk, Status, TaskRun, ToolResult
from nexora.policies import risk_decision, transition
from nexora.providers import MockLLMProvider
from nexora.tools import Calculator, CalculatorInput, FileInput, Registry, ToolError, calculate


async def finish(service, task_id):
    service.start(task_id)
    await service.running[task_id]
    return service.store.get(task_id)


@pytest.mark.parametrize(("expression", "value"), [("2+3*4", 14), ("(2+3)/2", 2.5), ("-2**2", -4), ("10%3", 1)])
def test_calculator(expression, value):
    assert calculate(expression) == value


@pytest.mark.parametrize("expression", ["__import__('os')", "True", "2**999", "1/0", "[1]", "1e999", "(-1)**0.5"])
def test_reject_unsafe_arithmetic(expression):
    with pytest.raises(ToolError):
        calculate(expression)


def test_config_validation():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, max_tool_retries=-1)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, llm_provider="openai")
    with pytest.raises(ValidationError):
        Settings(_env_file=None, nexora_safe_mode=False)


@pytest.mark.parametrize(
    ("goal", "kind"),
    [
        ("calculate 2+2", RequestType.READ_ONLY),
        ("approval demo", RequestType.CHANGE),
        ("delete folder", RequestType.SENSITIVE),
        ("What is AI?", RequestType.QUESTION),
        ("pay money", RequestType.UNSUPPORTED),
    ],
)
def test_classification(goal, kind):
    assert MockLLMProvider().classify_goal(goal) == kind


def test_plan_order_and_dependencies(service):
    task = service.create("calculate 2+2 then list files")
    assert [step.order for step in task.plan.steps] == [1, 2]
    assert task.plan.steps[1].dependencies == [task.plan.steps[0].id]


def test_invalid_state_transition():
    task = TaskRun(user_text="x", normalized_text="x")
    with pytest.raises(ValueError):
        transition(task, Status.COMPLETED)
    transition(task, Status.CANCELLED)
    with pytest.raises(ValueError):
        transition(task, Status.CLASSIFIED)


def test_registry_and_strict_schema():
    registry = Registry()
    registry.register(Calculator())
    with pytest.raises(ValueError):
        registry.register(Calculator())
    with pytest.raises(ValidationError):
        CalculatorInput(expression="2+2", unexpected=True)
    with pytest.raises(ToolError):
        registry.get("shell")


@pytest.mark.parametrize(
    "path",
    ["../secret.txt", "a/../../secret.txt", "C:/secret.txt", "/secret.txt", "notes.txt:stream"],
)
async def test_path_traversal(service, path):
    tool = service.registry.get("files")
    with pytest.raises(ToolError):
        await tool.execute(FileInput(action="read", path=path))


async def test_symlink_escape(service, tmp_path):
    outside = tmp_path / "outside.txt"
    outside.write_text("private")
    link = service.settings.nexora_workspace_dir / "link.txt"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("Host does not permit symlink creation")
    with pytest.raises(ToolError):
        await service.registry.get("files").execute(FileInput(action="read", path="link.txt"))


async def test_file_read_search_and_verify(service):
    (service.settings.nexora_workspace_dir / "notes.txt").write_bytes(b"hello\nworld")
    task = service.create("read notes.txt then search hello in notes.txt")
    task = await finish(service, task.id)
    assert task.status == Status.COMPLETED
    assert task.plan.steps[0].result.evidence["bytes"] == 11
    assert task.plan.steps[1].result.data["matches"] == [{"line": 1, "text": "hello"}]


async def test_file_size_and_type(service):
    tool = service.registry.get("files")
    (tool.workspace / "large.txt").write_bytes(b"x" * (tool.max_bytes + 1))
    for path in ("large.txt", "secret.env"):
        with pytest.raises(ToolError):
            await tool.execute(FileInput(action="read", path=path))


@pytest.mark.parametrize(
    ("risk", "expected"),
    [
        (Risk.LOW, "execute"),
        (Risk.MEDIUM, "approve"),
        (Risk.HIGH, "approve"),
        (Risk.CRITICAL, "block"),
    ],
)
def test_risk_policy(risk, expected):
    assert risk_decision(risk) == expected


async def test_approval_and_one_use(service):
    task = service.create("approval demo")
    task = service.start(task.id)
    assert task.status == Status.AWAITING_APPROVAL
    with pytest.raises(Conflict):
        service.start(task.id)
    service.decide(task.approval.id, True)
    task = await finish(service, task.id)
    assert task.status == Status.COMPLETED
    assert task.approval.status == ApprovalState.USED
    assert task.plan.steps[0].result.evidence["simulated"]
    with pytest.raises(Conflict):
        service.decide(task.approval.id, True)


def test_changed_plan_invalidates_approval(service):
    task = service.start(service.create("approval demo").id)
    task.plan.version += 1
    service.store.save(task, "Test plan change")
    with pytest.raises(Conflict):
        service.decide(task.approval.id, True)
    assert service.store.get(task.id).approval.status == ApprovalState.EXPIRED


def test_reject_approval(service):
    task = service.start(service.create("approval demo").id)
    assert service.decide(task.approval.id, False).status == Status.BLOCKED
    with pytest.raises(Conflict):
        service.start(task.id)


async def test_history_reopens(service):
    task = await finish(service, service.create("calculate 2+2").id)
    reopened = Store(service.settings.database_url)
    assert reopened.get(task.id).plan.steps[0].result.data == {"value": 4}
    assert reopened.events(task.id)[-1]["message"] == "Run finished"
    reopened.engine.dispose()


async def test_cancel_running(service, monkeypatch):
    entered = asyncio.Event()

    async def slow(inputs):
        entered.set()
        await asyncio.sleep(10)

    monkeypatch.setattr(service.registry.get("calculator"), "execute", slow)
    task = service.start(service.create("calculate 2+2 then list files").id)
    runner = service.running[task.id]
    await entered.wait()
    service.cancel(task.id)
    await runner
    saved = service.store.get(task.id)
    assert saved.status == Status.CANCELLED
    assert saved.plan.steps[1].status == Status.PLANNED


def test_cancel_planned(service):
    task = service.create("calculate 2+2")
    assert service.cancel(task.id).status == Status.CANCELLED


async def test_timeout(service, monkeypatch):
    service.settings.tool_timeout_seconds = 0.01

    async def slow(inputs):
        await asyncio.sleep(1)

    monkeypatch.setattr(service.registry.get("calculator"), "execute", slow)
    task = await finish(service, service.create("calculate 2+2").id)
    assert task.status == Status.TIMED_OUT


async def test_retry_then_recovery(service, monkeypatch):
    tool = service.registry.get("calculator")
    original = tool.execute
    calls = 0

    async def transient(inputs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError("transient")
        return await original(inputs)

    monkeypatch.setattr(tool, "execute", transient)
    task = await finish(service, service.create("calculate 2+2").id)
    assert task.status == Status.COMPLETED
    assert calls == 2 and task.plan.steps[0].retry_count == 1
    assert "RECOVERING" in [event["status"] for event in service.store.events(task.id)]


async def test_retry_limit(service, monkeypatch):
    calls = 0

    async def broken(inputs):
        nonlocal calls
        calls += 1
        raise OSError("secret-test-token")

    monkeypatch.setattr(service.registry.get("calculator"), "execute", broken)
    task = await finish(service, service.create("calculate 2+2").id)
    assert task.status == Status.FAILED
    assert calls == service.settings.max_tool_retries + 1
    assert "secret-test-token" not in str(service.store.events(task.id))
    assert "secret-test-token" not in task.model_dump_json()


async def test_forged_evidence_fails_closed(service, monkeypatch):
    async def forged(inputs):
        return ToolResult(success=True, data={"value": 999}, evidence={"value": 999})

    monkeypatch.setattr(service.registry.get("calculator"), "execute", forged)
    task = await finish(service, service.create("calculate 2+2").id)
    assert task.status == Status.FAILED
    assert task.plan.steps[0].result.error_code == "VERIFICATION_FAILED"
    assert task.plan.steps[0].retry_count == 0


def test_max_steps(service):
    service.settings.max_plan_steps = 1
    assert service.create("calculate 1 then calculate 2").status == Status.BLOCKED


def test_restart_marks_interrupted_failed(service):
    task = service.create("calculate 1")
    task.status = Status.EXECUTING
    service.store.save(task, "Interrupted test")
    service.recover_interrupted()
    assert service.store.get(task.id).status == Status.FAILED


def test_no_shared_mutable_defaults():
    one = TaskRun(user_text="one", normalized_text="one")
    two = TaskRun(user_text="two", normalized_text="two")
    assert one.plan.id != two.plan.id
    assert one.plan.steps is not two.plan.steps
    assert one.created_at.utcoffset().total_seconds() == 0
