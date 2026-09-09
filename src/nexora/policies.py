"""Risk policy, legal state transitions and exact approval binding."""

import hashlib
import json

from nexora.models import TERMINAL, Risk, Status, TaskRun

TRANSITIONS = {
    Status.RECEIVED: {Status.CLASSIFIED},
    Status.CLASSIFIED: {Status.PLANNED, Status.BLOCKED},
    Status.PLANNED: {Status.AWAITING_APPROVAL, Status.EXECUTING},
    Status.AWAITING_APPROVAL: {Status.EXECUTING, Status.BLOCKED},
    Status.EXECUTING: {Status.VERIFYING, Status.RECOVERING},
    Status.VERIFYING: {Status.EXECUTING, Status.COMPLETED, Status.RECOVERING},
    Status.RECOVERING: {Status.REPLANNED},
    Status.REPLANNED: {Status.EXECUTING},
}


def transition(task: TaskRun, target: Status) -> None:
    if task.status in TERMINAL or (
        target not in TRANSITIONS.get(task.status, set())
        and target not in {Status.CANCELLED, Status.FAILED, Status.TIMED_OUT}
    ):
        raise ValueError(f"Invalid transition: {task.status} -> {target}")
    task.status = target


def risk_decision(risk: Risk) -> str:
    if risk == Risk.CRITICAL:
        return "block"
    return "execute" if risk == Risk.LOW else "approve"


def approval_binding(task: TaskRun) -> str:
    payload = {"task": task.id, "plan": task.plan.model_dump(mode="json")}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
