"""add progress_stage column to jobs for grounded-pipeline substage UX

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-19 15:30:00.000000
"""
import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "jobs",
        sa.Column("progress_stage", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("jobs", "progress_stage")
