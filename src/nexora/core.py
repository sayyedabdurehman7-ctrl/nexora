"""Single-process planner/executor/verifier with durable checkpoints."""

import asyncio
from time import monotonic

from pydantic import ValidationError

from nexora.config import Settings
from nexora.db import Store
from nexora.models import (
    TERMINAL,
    ApprovalRequest,
    ApprovalState,
    RequestType,
    Risk,
    Status,
    TaskRun,
    ToolResult,
    now,
)
from nexora.policies import approval_binding, risk_decision, transition
from nexora.providers import LLMProvider, MockLLMProvider
from nexora.tools import Calculator, Files, Registry, ToolError


class Conflict(Exception):
    """The requested operation is not valid for this task state."""


class Service:
    def __init__(self, settings: Settings, store: Store, provider: LLMProvider | None = None):
        self.settings, self.store = settings, store
        self.provider = provider or MockLLMProvider()
        self.registry = Registry()
        self.registry.register(Calculator())
        self.registry.register(Files(settings.nexora_workspace_dir))
        self.running: dict[str, asyncio.Task] = {}
        self.stop_flags: dict[str, asyncio.Event] = {}

    def recover_interrupted(self) -> None:
        for task in self.store.list():
            if task.status in {
                Status.EXECUTING,
                Status.VERIFYING,
                Status.RECOVERING,
                Status.REPLANNED,
            }:
                transition(task, Status.FAILED)
                task.final_result = "Interrupted by service shutdown; create a new task to retry."
                task.ended_at = now()
                self.store.save(task, "Interrupted run recovered as failed")

    def create(self, text: str, correlation_id: str = "") -> TaskRun:
        task = TaskRun(user_text=text, normalized_text=" ".join(text.split()))
        task.request_type = self.provider.classify_goal(text)
        transition(task, Status.CLASSIFIED)
        self.store.save(task, "Goal classified", correlation_id)
        try:
            if task.request_type in {
                RequestType.SENSITIVE,
                RequestType.UNSUPPORTED,
                RequestType.QUESTION,
            }:
                raise ValueError("Unsupported")
            task.plan.steps = self.provider.create_plan(text)
            if not 1 <= len(task.plan.steps) <= self.settings.max_plan_steps:
                raise ValueError("Plan limit")
            for step in task.plan.steps:
                step.max_retries = self.settings.max_tool_retries
                if step.selected_tool != "approval_demo":
                    tool = self.registry.get(step.selected_tool)
                    tool.input_model.model_validate(step.inputs)
                    step.risk_level = tool.risk
            transition(task, Status.PLANNED)
            task.final_result = "Plan ready. Run it when ready."
        except (ValueError, ToolError):
            transition(task, Status.BLOCKED)
            task.final_result = (
                "Unsupported goal or plan limit. Try: calculate 2 + 3; list files; "
                "read notes.txt; search hello in notes.txt; approval demo. "
                "Join steps with ' then '."
            )
            task.ended_at = now()
        self.store.save(task, "Planning finished", correlation_id)
        return task

    def start(self, task_id: str) -> TaskRun:
        task = self.store.get(task_id)
        if task_id in self.running or task.status not in {Status.PLANNED, Status.AWAITING_APPROVAL}:
            raise Conflict("Task cannot run in its current state.")
        risk = max(
            (step.risk_level for step in task.plan.steps), key=lambda value: list(Risk).index(value)
        )
        decision = risk_decision(risk)
        if decision == "block":
            raise Conflict("Critical actions are blocked.")
        if decision == "approve":
            if task.approval is None:
                task.approval = ApprovalRequest(
                    action="Record approval demo acknowledgement",
                    target=f"task:{task.id}",
                    risk=risk,
                    consequence="Only this task result is updated. No external action.",
                    binding=approval_binding(task),
                )
                transition(task, Status.AWAITING_APPROVAL)
                self.store.save(task, "Exact approval requested")
                return task
            if task.approval.binding != approval_binding(task):
                task.approval.status = ApprovalState.EXPIRED
                self.store.save(task, "Approval expired after plan change")
                raise Conflict("Plan changed; create a new task for a fresh approval.")
            if task.approval.status != ApprovalState.APPROVED:
                raise Conflict("Exact approval is required.")
            task.approval.status = ApprovalState.USED
        transition(task, Status.EXECUTING)
        task.started_at = now()
        self.store.save(task, "Execution started")
        self.stop_flags[task_id] = asyncio.Event()
        self.running[task_id] = asyncio.create_task(self._execute(task))
        return task

    def decide(self, approval_id: str, approve: bool) -> TaskRun:
        task = next(
            (
                task
                for task in self.store.list()
                if task.approval and task.approval.id == approval_id
            ),
            None,
        )
        if task is None:
            raise KeyError(approval_id)
        approval = task.approval
        if task.status != Status.AWAITING_APPROVAL or approval.status != ApprovalState.PENDING:
            raise Conflict("Approval is no longer pending.")
        if approval.binding != approval_binding(task):
            approval.status = ApprovalState.EXPIRED
            self.store.save(task, "Approval expired after plan change")
            raise Conflict("Approval does not match the current plan.")
        approval.status = ApprovalState.APPROVED if approve else ApprovalState.REJECTED
        approval.decided_at = now()
        task.interventions += 1
        if not approve:
            transition(task, Status.BLOCKED)
            task.final_result = "Approval rejected; no action taken."
            task.ended_at = now()
        self.store.save(task, "Approval decision recorded")
        return task

    def cancel(self, task_id: str) -> TaskRun:
        task = self.store.get(task_id)
        if task.status in TERMINAL:
            return task
        if task_id in self.stop_flags:
            self.stop_flags[task_id].set()
            return task
        transition(task, Status.CANCELLED)
        task.final_result = "Cancelled."
        task.ended_at = now()
        if task.approval:
            task.approval.status = ApprovalState.EXPIRED
        self.store.save(task, "Task cancelled")
        return task

    async def _step(self, step) -> ToolResult:
        tool = self.registry.get(step.selected_tool)
        inputs = tool.input_model.model_validate(step.inputs)
        result = await tool.execute(inputs)
        return result

    async def _verify(self, step, result: ToolResult) -> bool:
        tool = self.registry.get(step.selected_tool)
        return await tool.verify(tool.input_model.model_validate(step.inputs), result)

    async def _interruptible(self, awaitable, stop: asyncio.Event, timeout: float):
        action = asyncio.create_task(awaitable)
        cancelled = asyncio.create_task(stop.wait())
        try:
            done, _ = await asyncio.wait(
                {action, cancelled}, timeout=timeout, return_when=asyncio.FIRST_COMPLETED
            )
            if cancelled in done:
                raise asyncio.CancelledError
            if action not in done:
                raise TimeoutError
            return action.result()
        finally:
            for pending in (action, cancelled):
                if not pending.done():
                    pending.cancel()
            await asyncio.gather(action, cancelled, return_exceptions=True)

    async def _execute(self, task: TaskRun) -> None:
        deadline = monotonic() + self.settings.max_task_seconds
        stop = self.stop_flags[task.id]
        try:
            for step in task.plan.steps:
                for attempt in range(step.max_retries + 1):
                    await asyncio.sleep(0)
                    if stop.is_set():
                        raise asyncio.CancelledError
                    remaining = deadline - monotonic()
                    if remaining <= 0:
                        raise TimeoutError
                    step.status = Status.EXECUTING
                    self.store.save(task, "Step started")
                    started = monotonic()
                    try:
                        if step.selected_tool == "approval_demo":
                            result = ToolResult(
                                success=True,
                                data={"acknowledged": True},
                                evidence={"task_id": task.id, "simulated": True},
                            )
                        else:
                            result = await self._interruptible(
                                self._step(step),
                                stop,
                                min(remaining, self.settings.tool_timeout_seconds),
                            )
                        result.duration_ms = (monotonic() - started) * 1000
                        step.result = result
                        transition(task, Status.VERIFYING)
                        step.status = Status.VERIFYING
                        self.store.save(task, "Verifying step evidence")
                        if step.selected_tool == "approval_demo":
                            saved = self.store.get(task.id)
                            verified = saved.plan.steps[0].result == result and (
                                saved.approval.status == ApprovalState.USED
                            )
                        else:
                            verified = await self._interruptible(
                                self._verify(step, result),
                                stop,
                                min(
                                    self.settings.tool_timeout_seconds,
                                    max(0, deadline - monotonic()),
                                ),
                            )
                        if not verified:
                            raise ToolError("VERIFICATION_FAILED", "Evidence did not verify.")
                        step.status = Status.COMPLETED
                        self.store.save(task, "Step verified")
                        break
                    except TimeoutError:
                        raise
                    except (OSError, UnicodeError, ValidationError, ToolError) as error:
                        code = error.code if isinstance(error, ToolError) else "FILE_OR_INPUT_ERROR"
                        # Retry transient I/O only. Verification mismatches fail closed.
                        recoverable = isinstance(error, OSError) and not isinstance(
                            error, (FileNotFoundError, PermissionError, IsADirectoryError)
                        )
                        step.result = ToolResult(
                            success=False,
                            error_code=code,
                            safe_error="Step failed; check inputs and access.",
                        )
                        if not recoverable or attempt >= step.max_retries:
                            step.status = Status.FAILED
                            raise ToolError(
                                code, "Step failed safely; see step error code."
                            ) from None
                        transition(task, Status.RECOVERING)
                        step.retry_count += 1
                        self.store.save(task, "Transient failure; bounded retry")
                        await self._interruptible(
                            asyncio.sleep(0.05 * (attempt + 1)),
                            stop,
                            max(0, deadline - monotonic()),
                        )
                        transition(task, Status.REPLANNED)
                        self.store.save(task, "Retry scheduled with backoff")
                        transition(task, Status.EXECUTING)
                if step is not task.plan.steps[-1]:
                    transition(task, Status.EXECUTING)
            if stop.is_set():
                raise asyncio.CancelledError
            if monotonic() >= deadline:
                raise TimeoutError
            transition(task, Status.COMPLETED)
            task.final_result = "All steps completed and evidence verified."
        except asyncio.CancelledError:
            transition(task, Status.CANCELLED)
            task.final_result = "Cancelled; no further steps will execute."
        except TimeoutError:
            transition(task, Status.TIMED_OUT)
            task.final_result = "Time limit reached; no further steps will execute."
        except Exception:
            transition(task, Status.FAILED)
            task.final_result = "Task failed safely. Inspect the step error and audit events."
        finally:
            for step in task.plan.steps:
                if step.status in {Status.EXECUTING, Status.VERIFYING}:
                    step.status = task.status
            task.ended_at = now()
            self.store.save(task, "Run finished")
            self.running.pop(task.id, None)
            self.stop_flags.pop(task.id, None)

    async def close(self) -> None:
        active = list(self.running.values())
        for stop in self.stop_flags.values():
            stop.set()
        if active:
            await asyncio.gather(*active, return_exceptions=True)
