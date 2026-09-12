"""SQLAlchemy storage; task snapshot and audit event commit atomically."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import Boolean, Integer, String, Text, create_engine, select
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


class MemoryRecord(Base):
    __tablename__ = "memories"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    category: Mapped[str] = mapped_column(String)
    content: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String, default="user")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[str] = mapped_column(String)
    updated_at: Mapped[str] = mapped_column(String)


class SettingRecord(Base):
    __tablename__ = "app_settings"
    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(Text)


class Store:
    def __init__(self, url: str):
        filename = url.removeprefix("sqlite:///")
        if filename != ":memory:":
            Path(filename).parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(url, connect_args={"check_same_thread": False})
        Base.metadata.create_all(self.engine)

    def get_setting(self, key: str) -> str | None:
        with Session(self.engine) as session:
            record = session.get(SettingRecord, key)
            return record.value if record else None

    def set_setting(self, key: str, value: str) -> None:
        with Session(self.engine) as session, session.begin():
            session.merge(SettingRecord(key=key, value=value))

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
            tasks = [TaskRun.model_validate_json(row.snapshot) for row in session.scalars(select(TaskRecord))]
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
                    select(AuditRecord).where(AuditRecord.task_id == task_id).order_by(AuditRecord.id)
                )
            ]

    def memory_list(self, include_disabled: bool = False) -> list[dict]:
        with Session(self.engine) as session:
            query = select(MemoryRecord).order_by(MemoryRecord.updated_at.desc())
            if not include_disabled:
                query = query.where(MemoryRecord.enabled.is_(True))
            return [self._memory_dict(row) for row in session.scalars(query)]

    def memory_get(self, memory_id: str) -> dict:
        with Session(self.engine) as session:
            row = session.get(MemoryRecord, memory_id)
            if row is None:
                raise KeyError(memory_id)
            return self._memory_dict(row)

    def memory_save(
        self,
        memory_id: str,
        category: str,
        content: str,
        source: str = "user",
        enabled: bool = True,
    ) -> dict:
        stamp = now().isoformat()
        with Session(self.engine) as session, session.begin():
            row = session.get(MemoryRecord, memory_id) or MemoryRecord(id=memory_id, created_at=stamp)
            row.category, row.content, row.source, row.enabled, row.updated_at = (
                category,
                content,
                source,
                enabled,
                stamp,
            )
            session.add(row)
        return self.memory_get(memory_id)

    def memory_delete(self, memory_id: str) -> None:
        with Session(self.engine) as session, session.begin():
            row = session.get(MemoryRecord, memory_id)
            if row is None:
                raise KeyError(memory_id)
            session.delete(row)

    @staticmethod
    def _memory_dict(row: MemoryRecord) -> dict:
        return {
            "id": row.id,
            "category": row.category,
            "content": row.content,
            "source": row.source,
            "enabled": row.enabled,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }
