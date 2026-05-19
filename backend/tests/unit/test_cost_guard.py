"""Unit tests for the daily cost guard.

The guard is the financial kill-switch — see SPEC §8.3 + the CLAUDE.md
'critical rules' section. It MUST NOT be bypassed, even in tests.
"""
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.cost import get_today_cost, record_cost
from app.db.session import get_db
from app.db.tables import DailyCost
from app.main import app


# --- cost module -----------------------------------------------------


@pytest.mark.asyncio
async def test_get_today_cost_returns_zero_when_no_row():
    """No row in daily_costs for today → 0.00 (not None, not crash)."""
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=result)

    cost = await get_today_cost(session)

    assert cost == Decimal("0")


@pytest.mark.asyncio
async def test_get_today_cost_returns_row_total():
    """Existing row → its total_cost_usd."""
    session = AsyncMock()
    row = DailyCost(date=date.today(), total_cost_usd=Decimal("3.14"), job_count=7)
    result = MagicMock()
    result.scalar_one_or_none.return_value = row
    session.execute = AsyncMock(return_value=result)

    cost = await get_today_cost(session)

    assert cost == Decimal("3.14")


@pytest.mark.asyncio
async def test_record_cost_creates_row_when_missing():
    """First debit of the day → INSERT a new daily_costs row."""
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=result)
    session.add = MagicMock()
    session.flush = AsyncMock()

    await record_cost(session, Decimal("0.06"))

    session.add.assert_called_once()
    added = session.add.call_args.args[0]
    assert isinstance(added, DailyCost)
    assert added.date == date.today()
    assert added.total_cost_usd == Decimal("0.06")
    assert added.job_count == 1


@pytest.mark.asyncio
async def test_record_cost_updates_existing_row():
    """Subsequent debits → UPDATE the existing row, accumulating cost + count."""
    session = AsyncMock()
    row = DailyCost(date=date.today(), total_cost_usd=Decimal("1.00"), job_count=3)
    result = MagicMock()
    result.scalar_one_or_none.return_value = row
    session.execute = AsyncMock(return_value=result)
    session.add = MagicMock()
    session.flush = AsyncMock()

    await record_cost(session, Decimal("0.25"))

    session.add.assert_not_called()
    assert row.total_cost_usd == Decimal("1.25")
    assert row.job_count == 4


@pytest.mark.asyncio
async def test_record_cost_zero_is_a_noop():
    """Zero-cost debits (cache hits) shouldn't bump job_count or touch the row."""
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=result)
    session.add = MagicMock()

    await record_cost(session, Decimal("0"))

    session.add.assert_not_called()


# --- jobs route gate -------------------------------------------------

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


def _override_session(session: AsyncMock):
    async def override():
        yield session

    app.dependency_overrides[get_db] = override


def _empty_cache_session(today_cost: Decimal) -> AsyncMock:
    """A mock session where the cache-lookup returns no rows AND the
    cost-guard lookup returns the given total."""
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()

    # The route fires two SELECTs: cache lookup (scalars().all()) and cost
    # lookup (scalar_one_or_none()). We need the same `execute` AsyncMock to
    # return a result that satisfies both interfaces.
    result = MagicMock()
    result.scalars.return_value.all.return_value = []  # cache miss
    if today_cost > 0:
        row = DailyCost(
            date=date.today(),
            total_cost_usd=today_cost,
            job_count=42,
        )
        result.scalar_one_or_none.return_value = row
    else:
        result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=result)
    return session


@pytest.mark.asyncio
async def test_post_jobs_under_budget_returns_202():
    """Under-budget request goes through the normal path."""
    session = _empty_cache_session(Decimal("2.50"))
    _override_session(session)
    try:
        with patch("app.routes.jobs.get_queue") as mock_q:
            mock_q.return_value = MagicMock()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post("/api/jobs", json=VALID_JOB_BODY)
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 202


@pytest.mark.asyncio
async def test_post_jobs_at_budget_returns_503():
    """Exactly at the limit → 503 with DAILY_BUDGET_EXHAUSTED code."""
    session = _empty_cache_session(Decimal("5.00"))
    _override_session(session)
    try:
        with patch("app.routes.jobs.get_queue") as mock_q:
            mock_q.return_value = MagicMock()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post("/api/jobs", json=VALID_JOB_BODY)
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "DAILY_BUDGET_EXHAUSTED"


@pytest.mark.asyncio
async def test_post_jobs_over_budget_returns_503():
    """Past the limit → 503 (limit is inclusive, but extra-defensive)."""
    session = _empty_cache_session(Decimal("9.99"))
    _override_session(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/api/jobs", json=VALID_JOB_BODY)
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 503


@pytest.mark.asyncio
async def test_post_jobs_cache_hit_bypasses_cost_guard():
    """Cache hits cost $0 — should serve even when over the daily budget."""
    from app.db.tables import Job

    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()

    cached_job = Job(
        id=__import__("uuid").uuid4(),
        resolved_id="OL12345W",
        model="claude-opus-4-7",
        character_map={"work": {"title": "Congo"}, "characters": [], "relationships": [], "factions": []},
        character_cap=20,
        spoiler_mode="full",
        status="done",
    )

    cache_result = MagicMock()
    cache_result.scalars.return_value.all.return_value = [cached_job]
    session.execute = AsyncMock(return_value=cache_result)

    _override_session(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/api/jobs", json=VALID_JOB_BODY)
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 202, response.json()
