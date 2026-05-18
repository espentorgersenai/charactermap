"""add character_cap column to jobs (Phase 4+ user-tunable cap)

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-18 18:30:00.000000
"""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "jobs",
        sa.Column(
            "character_cap",
            sa.Integer(),
            nullable=False,
            server_default="20",
        ),
    )
    op.create_check_constraint(
        "ck_jobs_character_cap",
        "jobs",
        "character_cap IN (10, 20, 30, 40, 50)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_jobs_character_cap", "jobs", type_="check")
    op.drop_column("jobs", "character_cap")
