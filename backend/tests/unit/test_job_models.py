import pytest
from pydantic import ValidationError
from app.models.job import JobCreateRequest
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
