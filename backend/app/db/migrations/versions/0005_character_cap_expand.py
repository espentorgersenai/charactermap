"""expand ck_jobs_character_cap to allow 100 and 150 (GoT-scale maps)

The geographic / very-large-ensemble feature added 100 and 150 to
VALID_CHARACTER_CAPS (Pydantic) and the frontend dropdown, but the CHECK
constraint was left at {10,20,30,40,50}. cap=100/150 INSERTs passed Pydantic
then hit CheckViolationError on commit (surfaced as JOB_CREATE_FAILED). This
realigns the DB with the code; keep all three layers (validator, frontend,
constraint) in sync going forward.

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-29 00:00:00.000000
"""
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

_NEW = "character_cap IN (10, 20, 30, 40, 50, 100, 150)"
_OLD = "character_cap IN (10, 20, 30, 40, 50)"


def upgrade() -> None:
    op.drop_constraint("ck_jobs_character_cap", "jobs", type_="check")
    op.create_check_constraint("ck_jobs_character_cap", "jobs", _NEW)


def downgrade() -> None:
    op.drop_constraint("ck_jobs_character_cap", "jobs", type_="check")
    op.create_check_constraint("ck_jobs_character_cap", "jobs", _OLD)
