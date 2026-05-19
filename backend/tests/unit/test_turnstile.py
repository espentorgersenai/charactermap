"""Server-side Cloudflare Turnstile verification (SPEC §10.1).

Token comes from the frontend Turnstile widget and is verified against
Cloudflare's siteverify endpoint. Missing or invalid → 403 TURNSTILE_FAILED.
When the secret key isn't configured (dev), verification is skipped.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.session import get_db
from app.main import app
from app.security.turnstile import verify_token


@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    exec_result = MagicMock()
    exec_result.scalars.return_value.all.return_value = []
    exec_result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=exec_result)

    async def override():
        yield session

    app.dependency_overrides[get_db] = override
    yield session
    app.dependency_overrides.clear()


VALID_JOB_BODY = {
    "title_query": "Congo",
    "resolved": {
        "source": "openlibrary",
        "id": "OL12345W",
        "title": "Congo",
        "year": 1980,
        "author": "Michael Crichton",
        "cover_url": None,
        "confidence_score": 0.95,
    },
    "model": "claude-sonnet-4-6",
    "formats": ["interactive"],
    "acknowledged_spoilers": True,
}


# --- core verifier ---------------------------------------------------


@pytest.mark.asyncio
async def test_verify_valid_token_returns_true(httpx_mock):
    httpx_mock.add_response(
        url="https://challenges.cloudflare.com/turnstile/v0/siteverify",
        json={"success": True},
    )
    ok = await verify_token("good-token", "secret-key", "1.2.3.4")
    assert ok is True


@pytest.mark.asyncio
async def test_verify_invalid_token_returns_false(httpx_mock):
    httpx_mock.add_response(
        url="https://challenges.cloudflare.com/turnstile/v0/siteverify",
        json={"success": False, "error-codes": ["invalid-input-response"]},
    )
    ok = await verify_token("bad-token", "secret-key", "1.2.3.4")
    assert ok is False


@pytest.mark.asyncio
async def test_verify_empty_token_returns_false_without_calling_cf():
    """Empty/None token should short-circuit — no HTTP call."""
    ok = await verify_token("", "secret-key", "1.2.3.4")
    assert ok is False


# --- route wiring ----------------------------------------------------


@pytest.mark.asyncio
async def test_post_jobs_without_secret_key_skips_verification(mock_session, monkeypatch):
    """Dev mode (no secret configured) → verification is skipped."""
    monkeypatch.setattr("app.routes.jobs.settings.turnstile_secret_key", "")
    with patch("app.routes.jobs.get_queue") as mq:
        mq.return_value = MagicMock()
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.post("/api/jobs", json=VALID_JOB_BODY)
    assert r.status_code == 202


@pytest.mark.asyncio
async def test_post_jobs_missing_token_returns_403(mock_session, monkeypatch):
    monkeypatch.setattr("app.routes.jobs.settings.turnstile_secret_key", "secret")
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.post("/api/jobs", json=VALID_JOB_BODY)
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "TURNSTILE_FAILED"


@pytest.mark.asyncio
async def test_post_jobs_invalid_token_returns_403(mock_session, monkeypatch):
    monkeypatch.setattr("app.routes.jobs.settings.turnstile_secret_key", "secret")
    body = {**VALID_JOB_BODY, "turnstile_token": "bad-token"}
    with patch("app.security.turnstile.verify_token", AsyncMock(return_value=False)):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.post("/api/jobs", json=body)
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "TURNSTILE_FAILED"


@pytest.mark.asyncio
async def test_post_jobs_valid_token_passes(mock_session, monkeypatch):
    monkeypatch.setattr("app.routes.jobs.settings.turnstile_secret_key", "secret")
    body = {**VALID_JOB_BODY, "turnstile_token": "good-token"}
    with patch("app.security.turnstile.verify_token", AsyncMock(return_value=True)), \
         patch("app.routes.jobs.get_queue") as mq:
        mq.return_value = MagicMock()
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.post("/api/jobs", json=body)
    assert r.status_code == 202
