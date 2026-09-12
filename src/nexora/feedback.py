"""Local tester feedback storage with optional sanitized startup diagnostics."""

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field


class FeedbackInput(BaseModel):
    overall_experience: int = Field(ge=1, le=5)
    confusing: str = Field(default="", max_length=1000)
    error_seen: str = Field(default="", max_length=1000)
    liked_feature: str = Field(default="", max_length=1000)
    add_next: str = Field(default="", max_length=1000)
    attach_diagnostic: bool = False


_SECRET = re.compile(
    r"(?i)(gemini_api_key|api[_ -]?key|authorization|token|password)\s*[:=]\s*\S+|"
    r"\b(?:sk|AIza)[A-Za-z0-9_-]{12,}\b"
)


def _safe_text(value: str) -> str:
    return _SECRET.sub("[redacted]", value or "")


def format_feedback(feedback: FeedbackInput) -> str:
    """Create a simple shareable feedback report."""
    stars = "★" * feedback.overall_experience + "☆" * (5 - feedback.overall_experience)
    return "\n".join(
        [
            "NEXORA Tester Feedback",
            f"Overall experience: {stars} ({feedback.overall_experience}/5)",
            f"Was anything confusing? {_safe_text(feedback.confusing) or 'No response'}",
            f"Did you see an error? {_safe_text(feedback.error_seen) or 'No response'}",
            f"Feature you liked: {_safe_text(feedback.liked_feature) or 'No response'}",
            f"What should NEXORA add next? {_safe_text(feedback.add_next) or 'No response'}",
        ]
    )


def save_feedback(data_dir: Path, feedback: FeedbackInput) -> str:
    """Save feedback under the user's writable NEXORA data directory."""
    folder = data_dir.resolve() / "feedback"
    folder.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    filename = f"NEXORA-Feedback-{timestamp}-{uuid4().hex[:8]}.json"
    payload = feedback.model_dump(exclude={"attach_diagnostic"})
    for field in ("confusing", "error_seen", "liked_feature", "add_next"):
        payload[field] = _safe_text(payload[field])
    payload["created_at"] = datetime.now(UTC).isoformat()
    payload["shareable_text"] = format_feedback(feedback)
    if feedback.attach_diagnostic:
        log_path = data_dir.resolve() / "logs" / "nexora.log"
        diagnostic = log_path.read_text(encoding="utf-8", errors="replace")[-20000:] if log_path.exists() else ""
        payload["diagnostic_report"] = _SECRET.sub("[redacted]", diagnostic)
    (folder / filename).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return filename
