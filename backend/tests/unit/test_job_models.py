import re

import pytest
from pydantic import ValidationError
from app.db.tables import Job
from app.models.job import VALID_CHARACTER_CAPS, JobCreateRequest
from app.models.api import ResolveCandidate

VALID_CANDIDATE = {
    "source": "openlibrary",
    "id": "OL12345W",
    "title": "Congo",
    "year": 1980,
    "author": "Michael Crichton",
    "cover_url": None,
    "confidence_score": 0.95,
}

VALID_REQUEST = {
    "title_query": "Congo",
    "resolved": VALID_CANDIDATE,
    "model": "claude-sonnet-4-6",
    "formats": ["interactive"],
    "acknowledged_spoilers": True,
}


def test_valid_request_parses():
    req = JobCreateRequest.model_validate(VALID_REQUEST)
    assert req.acknowledged_spoilers is True
    assert req.model == "claude-sonnet-4-6"


def test_acknowledged_spoilers_false_parses_as_false():
    """Route handler checks this and returns 400; Pydantic allows false."""
    req = JobCreateRequest.model_validate({**VALID_REQUEST, "acknowledged_spoilers": False})
    assert req.acknowledged_spoilers is False


def test_missing_acknowledged_spoilers_raises():
    bad = {k: v for k, v in VALID_REQUEST.items() if k != "acknowledged_spoilers"}
    with pytest.raises(ValidationError):
        JobCreateRequest.model_validate(bad)


def test_invalid_model_raises():
    with pytest.raises(ValidationError):
        JobCreateRequest.model_validate({**VALID_REQUEST, "model": "gpt-3"})


def test_empty_formats_raises():
    with pytest.raises(ValidationError):
        JobCreateRequest.model_validate({**VALID_REQUEST, "formats": []})


def test_email_optional():
    req = JobCreateRequest.model_validate(VALID_REQUEST)
    assert req.email is None


def test_turnstile_optional():
    req = JobCreateRequest.model_validate(VALID_REQUEST)
    assert req.turnstile_token is None


def _db_cap_constraint_values() -> set[int]:
    """The integers enumerated by the ck_jobs_character_cap CHECK constraint."""
    from sqlalchemy import CheckConstraint

    for c in Job.__table__.constraints:
        if isinstance(c, CheckConstraint) and c.name == "ck_jobs_character_cap":
            return {int(n) for n in re.findall(r"\d+", str(c.sqltext))}
    raise AssertionError("ck_jobs_character_cap constraint not found on Job table")


def test_db_cap_constraint_matches_valid_caps():
    """All three cap layers must agree: Pydantic validator, frontend dropdown,
    and the DB CHECK constraint.

    Regression for JOB_CREATE_FAILED — the cap was expanded to include 100/150
    in VALID_CHARACTER_CAPS and the frontend, but the CHECK constraint (and its
    migration) were left at {10,20,30,40,50}, so cap=100/150 INSERTs raised
    CheckViolationError on commit. If you change VALID_CHARACTER_CAPS, ship a
    migration and update tables.py in the same change.
    """
    assert _db_cap_constraint_values() == VALID_CHARACTER_CAPS
