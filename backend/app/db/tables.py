import uuid
from datetime import datetime
from sqlalchemy import (
    BigInteger, CheckConstraint, Column, Date, DateTime, ForeignKey,
    Index, Integer, Numeric, String, Text, ARRAY, text,
)
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class Job(Base):
    __tablename__ = "jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime(timezone=True))

    work_type = Column(String, nullable=False)
    title_query = Column(Text, nullable=False)
    resolved_id = Column(Text, nullable=False)
    resolved_title = Column(Text, nullable=False)
    resolved_year = Column(Integer)
    resolved_meta = Column(JSONB, nullable=False, default=dict)

    model = Column(Text, nullable=False)
    spoiler_mode = Column(Text, nullable=False, default="full")
    formats = Column(ARRAY(Text), nullable=False)
    email = Column(Text)
    acknowledgement_at = Column(DateTime(timezone=True), nullable=False)

    adaptation_tmdb_id = Column(Integer)
    adaptation_title = Column(Text)
    adaptation_rating = Column(Numeric(3, 1))

    character_cap = Column(Integer, nullable=False, server_default="20")

    status = Column(Text, nullable=False, default="queued")
    # Fine-grained sub-stage within status='generating', for UX progress display.
    # Codes: searching | structuring | enriching | rendering | (null when not generating)
    progress_stage = Column(Text)
    error_code = Column(Text)
    error_message = Column(Text)
    character_map = Column(JSONB)
    manual_overrides = Column(JSONB)

    llm_input_tokens = Column(Integer)
    llm_output_tokens = Column(Integer)
    estimated_cost_usd = Column(Numeric(6, 4))

    requester_ip = Column(INET, nullable=False)
    user_agent = Column(Text)
    deleted_at = Column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("work_type IN ('book', 'film_tv')", name="ck_jobs_work_type"),
        CheckConstraint("spoiler_mode IN ('full', 'safe')", name="ck_jobs_spoiler_mode"),
        CheckConstraint(
            "status IN ('queued','resolving','generating','rendering','done','failed','refused')",
            name="ck_jobs_status",
        ),
        CheckConstraint(
            "character_cap IN (10, 20, 30, 40, 50)",
            name="ck_jobs_character_cap",
        ),
        Index("idx_jobs_created_at", "created_at"),
        Index("idx_jobs_requester_ip", "requester_ip", "created_at"),
        Index(
            "idx_jobs_status",
            "status",
            postgresql_where=text("status IN ('queued','resolving','generating','rendering')"),
        ),
    )


class Artifact(Base):
    __tablename__ = "artifacts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    format = Column(Text, nullable=False)
    file_path = Column(Text, nullable=False)
    file_size = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_artifacts_job_id", "job_id"),
    )


class DailyCost(Base):
    __tablename__ = "daily_costs"

    date = Column(Date, primary_key=True)
    total_cost_usd = Column(Numeric(8, 4), nullable=False, default=0)
    job_count = Column(Integer, nullable=False, default=0)


class AnalyticsEvent(Base):
    __tablename__ = "analytics_events"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    occurred_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    event_type = Column(Text, nullable=False)
    job_id = Column(UUID(as_uuid=True))
    properties = Column(JSONB, nullable=False, default=dict)

    __table_args__ = (
        Index("idx_analytics_events_occurred", "occurred_at"),
        Index("idx_analytics_events_type", "event_type", "occurred_at"),
    )
