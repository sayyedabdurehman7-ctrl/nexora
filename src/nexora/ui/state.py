"""Presentation state and plain helpers, independent of Flet controls."""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

TERMINAL = {"COMPLETED", "FAILED", "BLOCKED", "CANCELLED", "TIMED_OUT"}
LABELS = {
    "RECEIVED": "Received",
    "CLASSIFIED": "Understanding goal",
    "PLANNED": "Ready",
    "EXECUTING": "Running",
    "VERIFYING": "Verifying",
    "COMPLETED": "Completed",
    "FAILED": "Failed",
    "AWAITING_APPROVAL": "Waiting for approval",
    "CANCELLED": "Cancelled",
    "BLOCKED": "Blocked",
    "TIMED_OUT": "Time limit reached",
    "RECOVERING": "Retrying safely",
    "REPLANNED": "Retry ready",
}


def label(status: str) -> str:
    return LABELS.get(status, status.title())


def timestamp(value: str | None) -> str:
    return datetime.fromisoformat(value).astimezone().strftime("%b %d, %H:%M") if value else "—"


def duration(task: dict) -> str:
    if not task.get("started_at"):
        return "—"
    start = datetime.fromisoformat(task["started_at"])
    end = datetime.fromisoformat(task["ended_at"]) if task.get("ended_at") else datetime.now(start.tzinfo)
    return f"{(end - start).total_seconds():.1f}s"


def response_text(task: dict) -> str:
    parts = [task["final_result"]]
    for step in task["plan"]["steps"]:
        result = step.get("result")
        if not result:
            continue
        data = result["data"]
        if not result["success"]:
            parts.append(f"**{step['selected_tool'].title()}**: {result.get('safe_error', 'Failed')}")
        elif "value" in data:
            parts.append(f"### Result: {data['value']:g}")
        elif "text" in data:
            parts.append("### File contents\n\n" + data["text"][:12000])
        elif "entries" in data:
            parts.append("### Files\n\n" + ("\n".join(f"- {x}" for x in data["entries"]) or "No files found."))
        elif "matches" in data:
            parts.append(
                "### Matching lines\n\n"
                + ("\n".join(f"- Line {x['line']}: {x['text']}" for x in data["matches"]) or "No matches found.")
            )
        elif "acknowledged" in data:
            parts.append("The approval demonstration was acknowledged. No external action was taken.")
    return "\n\n".join(parts)


@dataclass
class UIState:
    screen: str = "Chat"
    tasks: list[dict] = field(default_factory=list)
    task: dict | None = None
    events: list[dict] = field(default_factory=list)
    tools: list[dict] = field(default_factory=list)
    settings: dict = field(default_factory=dict)
    connected: bool = False
    busy: bool = False
    collapsed: bool = False
    panel_open: bool = True
    panel_tab: str = "Plan"
    search: str = ""
    status_filter: str = "All"
    date_filter: str = ""
    preferences: dict = field(
        default_factory=lambda: {
            "theme": "system",
            "density": "Comfortable",
            "text_size": 14,
            "welcomed": False,
        }
    )
    preference_path: Path | None = Path("data/ui_preferences.json")

    def load_preferences(self) -> None:
        try:
            values = json.loads(self.preference_path.read_text()) if self.preference_path else {}
            for key in self.preferences:
                if key in values:
                    self.preferences[key] = values[key]
        except (OSError, ValueError, TypeError):
            pass

    def save_preferences(self) -> None:
        if self.preference_path:
            self.preference_path.parent.mkdir(parents=True, exist_ok=True)
            self.preference_path.write_text(json.dumps(self.preferences), encoding="utf-8")

    def filtered_tasks(self) -> list[dict]:
        return [
            task
            for task in self.tasks
            if self.search.lower() in task["user_text"].lower()
            and (self.status_filter == "All" or task["status"] == self.status_filter)
            and (not self.date_filter or task["created_at"].startswith(self.date_filter))
        ]
