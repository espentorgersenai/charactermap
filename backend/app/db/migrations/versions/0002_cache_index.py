"""cache index on resolved_id + spoiler_mode for done jobs

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-18 00:00:00.000000
"""
from alembic import op
from sqlalchemy import text

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "idx_jobs_cache",
        "jobs",
        ["resolved_id", "spoiler_mode"],
        postgresql_where=text("status = 'done' AND deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_jobs_cache", table_name="jobs")
