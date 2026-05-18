"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-18 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # jobs table
    op.create_table(
        "jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),

        # Input
        sa.Column("work_type", sa.Text(), nullable=False),
        sa.Column("title_query", sa.Text(), nullable=False),
        sa.Column("resolved_id", sa.Text(), nullable=False),
        sa.Column("resolved_title", sa.Text(), nullable=False),
        sa.Column("resolved_year", sa.Integer(), nullable=True),
        sa.Column("resolved_meta", postgresql.JSONB(astext_type=sa.Text()), nullable=False,
                  server_default=sa.text("'{}'::jsonb")),

        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("spoiler_mode", sa.Text(), nullable=False, server_default="'full'"),
        sa.Column("formats", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("acknowledgement_at", sa.DateTime(timezone=True), nullable=False),

        # Adaptation info
        sa.Column("adaptation_tmdb_id", sa.Integer(), nullable=True),
        sa.Column("adaptation_title", sa.Text(), nullable=True),
        sa.Column("adaptation_rating", sa.Numeric(3, 1), nullable=True),

        # Output
        sa.Column("status", sa.Text(), nullable=False, server_default="'queued'"),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("character_map", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("manual_overrides", postgresql.JSONB(astext_type=sa.Text()), nullable=True),

        # Cost tracking
        sa.Column("llm_input_tokens", sa.Integer(), nullable=True),
        sa.Column("llm_output_tokens", sa.Integer(), nullable=True),
        sa.Column("estimated_cost_usd", sa.Numeric(6, 4), nullable=True),

        # Network / abuse
        sa.Column("requester_ip", postgresql.INET(), nullable=False),
        sa.Column("user_agent", sa.Text(), nullable=True),

        # Retention (GDPR)
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),

        # CHECK constraints
        sa.CheckConstraint("work_type IN ('book', 'film_tv')", name="ck_jobs_work_type"),
        sa.CheckConstraint("spoiler_mode IN ('full', 'safe')", name="ck_jobs_spoiler_mode"),
        sa.CheckConstraint(
            "status IN ('queued','resolving','generating','rendering','done','failed','refused')",
            name="ck_jobs_status",
        ),
    )

    op.create_index("idx_jobs_created_at", "jobs", ["created_at"])
    op.create_index("idx_jobs_requester_ip", "jobs", ["requester_ip", "created_at"])
    op.create_index(
        "idx_jobs_status",
        "jobs",
        ["status"],
        postgresql_where=sa.text("status IN ('queued','resolving','generating','rendering')"),
    )

    # artifacts table
    op.create_table(
        "artifacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("format", sa.Text(), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
    )

    op.create_index("idx_artifacts_job_id", "artifacts", ["job_id"])

    # daily_costs table
    op.create_table(
        "daily_costs",
        sa.Column("date", sa.Date(), primary_key=True),
        sa.Column("total_cost_usd", sa.Numeric(8, 4), nullable=False, server_default="0"),
        sa.Column("job_count", sa.Integer(), nullable=False, server_default="0"),
    )

    # analytics_events table
    op.create_table(
        "analytics_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("properties", postgresql.JSONB(astext_type=sa.Text()), nullable=False,
                  server_default=sa.text("'{}'::jsonb")),
    )

    op.create_index("idx_analytics_events_occurred", "analytics_events", ["occurred_at"])
    op.create_index(
        "idx_analytics_events_type", "analytics_events", ["event_type", "occurred_at"]
    )


def downgrade() -> None:
    op.drop_table("analytics_events")
    op.drop_table("daily_costs")
    op.drop_table("artifacts")
    op.drop_table("jobs")
