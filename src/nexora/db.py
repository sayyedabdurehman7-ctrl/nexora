"""SQLAlchemy storage; task snapshot and audit event commit atomically."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import Integer, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from nexora.models import TaskRun, now


class Base(DeclarativeBase):
    pass


class TaskRecord(Base):
    __tablename__ = "tasks"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    snapshot: Mapped[str] = mapped_column(Text)
    schema_version: Mapped[int] = mapped_column(Integer, default=1)


class AuditRecord(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(String, index=True)
    timestamp: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)
    message: Mapped[str] = mapped_column(String)
    correlation_id: Mapped[str] = mapped_column(String)


class Store:
    def __init__(self, url: str):
        filename = url.removeprefix("sqlite:///")
        if filename != ":memory:":
            Path(filename).parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(url, connect_args={"check_same_thread": False})
        Base.metadata.create_all(self.engine)

    def save(self, task: TaskRun, message: str, correlation_id: str = "") -> None:
        # Only fixed event messages; file contents, goals and credentials are not logs.
        with Session(self.engine) as session, session.begin():
            session.merge(TaskRecord(id=task.id, snapshot=task.model_dump_json()))
            session.add(
                AuditRecord(
                    task_id=task.id,
                    timestamp=now().isoformat(),
                    status=task.status.value,
                    message=message,
                    correlation_id=correlation_id or task.id,
                )
            )

    def get(self, task_id: str) -> TaskRun:
        with Session(self.engine) as session:
            record = session.get(TaskRecord, task_id)
            if record is None:
                raise KeyError(task_id)
            return TaskRun.model_validate_json(record.snapshot)

    def list(self) -> list[TaskRun]:
        with Session(self.engine) as session:
            tasks = [
                TaskRun.model_validate_json(row.snapshot)
                for row in session.scalars(select(TaskRecord))
            ]
        return sorted(tasks, key=lambda task: task.created_at, reverse=True)

    def events(self, task_id: str) -> list[dict]:
        self.get(task_id)
        with Session(self.engine) as session:
            return [
                {
                    "id": row.id,
                    "timestamp": row.timestamp,
                    "status": row.status,
                    "message": row.message,
                    "correlation_id": row.correlation_id,
                }
                for row in session.scalars(
                    select(AuditRecord)
                    .where(AuditRecord.task_id == task_id)
                    .order_by(AuditRecord.id)
                )
            ]
