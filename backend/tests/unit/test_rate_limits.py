"""Unit tests for the Redis sliding-window rate limiter (SPEC §10.2).

We use a fakeredis instance so tests are deterministic + don't require Redis
to be running. The limiter operates on async-Redis-compatible duck typing,
which fakeredis honours.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import fakeredis.aioredis
import pytest
from httpx import ASGITransport, AsyncClient

from app.db.session import get_db
from app.main import app
from app.security.rate_limit import (
    JOBS_WINDOWS,
    RESOLVE_WINDOWS,
    RateLimitDecision,
    check_and_record,
)


@pytest.fixture
async def redis(_isolated_redis):
    """Reuses the conftest-provided fakeredis; named local fixture so the
    parameter name in tests stays readable."""
    return _isolated_redis


# --- core limiter ----------------------------------------------------


@pytest.mark.asyncio
async def test_under_all_limits_allows(redis):
    d: RateLimitDecision = await check_and_record(redis, "rl:test:1.2.3.4", JOBS_WINDOWS)
    assert d.allowed is True
    assert d.retry_after_seconds == 0


@pytest.mark.asyncio
async def test_first_minute_limit_blocks_at_third_request(redis):
    """JOBS_WINDOWS allows 2/min — the 3rd within the same minute must fail."""
    key = "rl:jobs:1.2.3.4"
    await check_and_record(redis, key, JOBS_WINDOWS)
    await check_and_record(redis, key, JOBS_WINDOWS)
    d = await check_and_record(redis, key, JOBS_WINDOWS)
    assert d.allowed is False
    assert d.retry_after_seconds > 0
    assert d.retry_after_seconds <= 60  # within the 60s window
    assert d.window_label == "per_minute"


@pytest.mark.asyncio
async def test_different_ips_are_independent(redis):
    await check_and_record(redis, "rl:jobs:a", JOBS_WINDOWS)
    await check_and_record(redis, "rl:jobs:a", JOBS_WINDOWS)
    d_blocked = await check_and_record(redis, "rl:jobs:a", JOBS_WINDOWS)
    assert d_blocked.allowed is False

    d_other = await check_and_record(redis, "rl:jobs:b", JOBS_WINDOWS)
    assert d_other.allowed is True


@pytest.mark.asyncio
async def test_resolve_uses_lighter_window(redis):
    """30/min for /api/resolve — let's make sure we don't accidentally cap at 2."""
    key = "rl:resolve:x"
    for _ in range(29):
        d = await check_and_record(redis, key, RESOLVE_WINDOWS)
        assert d.allowed
    d_29 = await check_and_record(redis, key, RESOLVE_WINDOWS)
    assert d_29.allowed
    d_30 = await check_and_record(redis, key, RESOLVE_WINDOWS)
    assert d_30.allowed is False


@pytest.mark.asyncio
async def test_record_is_skipped_when_blocked(redis):
    """Blocked attempts should NOT add to the sliding window (otherwise
    spammers extend their own block indefinitely)."""
    key = "rl:jobs:y"
    await check_and_record(redis, key, JOBS_WINDOWS)
    await check_and_record(redis, key, JOBS_WINDOWS)
    d_block = await check_and_record(redis, key, JOBS_WINDOWS)
    assert d_block.allowed is False
    count_before = await redis.zcard(key)
    await check_and_record(redis, key, JOBS_WINDOWS)
    count_after = await redis.zcard(key)
    assert count_after == count_before


# --- route wiring ----------------------------------------------------

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


@pytest.mark.asyncio
async def test_post_jobs_returns_429_when_rate_limited(mock_session):
    """Third request in a minute returns 429 with Retry-After header."""
    with patch("app.routes.jobs.get_queue") as mock_q:
        mock_q.return_value = MagicMock()
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r1 = await client.post("/api/jobs", json=VALID_JOB_BODY)
            r2 = await client.post("/api/jobs", json=VALID_JOB_BODY)
            r3 = await client.post("/api/jobs", json=VALID_JOB_BODY)
    assert r1.status_code == 202
    assert r2.status_code == 202
    assert r3.status_code == 429
    assert r3.json()["detail"]["code"] == "RATE_LIMITED"
    assert "retry-after" in {k.lower() for k in r3.headers.keys()}
    assert int(r3.headers["retry-after"]) > 0
