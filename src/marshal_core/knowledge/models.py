"""知识核持久模型 — schema 领域无关 (domain/severity 取值由领域包定义)。"""
from datetime import datetime, timezone
from sqlalchemy import String, Integer, JSON, DateTime, inspect, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


class InvariantRegistry(Base):
    __tablename__ = "invariant_registry"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    domain_pack: Mapped[str] = mapped_column(String, index=True)
    domain: Mapped[str] = mapped_column(String)
    spec_ref: Mapped[str] = mapped_column(String, default="")
    executor_kind: Mapped[str] = mapped_column(String)
    location_repo: Mapped[str] = mapped_column(String, index=True)
    location_path: Mapped[str] = mapped_column(String)
    location_test: Mapped[str] = mapped_column(String)
    severity: Mapped[str] = mapped_column(String, default="mid")
    status: Mapped[str] = mapped_column(String, default="active")
    origin: Mapped[str] = mapped_column(String, default="hand")
    escape_id: Mapped[str | None] = mapped_column(String, nullable=True)


class GateRun(Base):
    __tablename__ = "gate_run"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    change_ref: Mapped[str] = mapped_column(String, index=True)
    job_id: Mapped[str] = mapped_column(String, index=True)
    verdict: Mapped[str] = mapped_column(String)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=_now)
    event: Mapped[str] = mapped_column(String)
    actor: Mapped[str] = mapped_column(String, default="system")
    decision: Mapped[str] = mapped_column(String, default="")
    refs: Mapped[dict] = mapped_column(JSON, default=dict)


class EscapeRegistry(Base):
    __tablename__ = "escape_registry"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    domain_pack: Mapped[str] = mapped_column(String, index=True, default="cowboy")
    discovered_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    introduced_at: Mapped[str | None] = mapped_column(String, nullable=True)
    introduced_at_ts: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    root_cause_class: Mapped[str] = mapped_column(String, default="")
    change_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    description: Mapped[str] = mapped_column(String, default="")
    postmortem_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    spawned_check: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="open")


class Meta(Base):
    __tablename__ = "meta"
    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(String, default="")


class ReviewJob(Base):
    __tablename__ = "review_job"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    change_ref: Mapped[str] = mapped_column(String, index=True)
    repo: Mapped[str] = mapped_column(String, default="node")
    kind: Mapped[str] = mapped_column(String, default="mechanical")   # 'mechanical' | 'deep'
    status: Mapped[str] = mapped_column(String, default="pending")    # pending|running|done|failed
    requested_by: Mapped[str] = mapped_column(String, default="dashboard")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(String, nullable=True)


def ensure_schema(engine) -> None:
    """create_all + idempotent additive column migrations, so a DB created before a
    column was added to a model gets it on next startup instead of erroring on reads.
    Safe to call at every startup. The ALTER only ever fires against an older SQLite
    marshal.db (a fresh create_all — SQLite or Postgres — already includes the column,
    so the guard skips it)."""
    Base.metadata.create_all(engine)
    cols = {c["name"] for c in inspect(engine).get_columns("escape_registry")}
    if "introduced_at_ts" not in cols:
        with engine.begin() as conn:
            conn.execute(text(
                "ALTER TABLE escape_registry ADD COLUMN introduced_at_ts DATETIME"))
