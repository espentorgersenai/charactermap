"""GET /api/limits exposes remaining quota for the calling IP (SPEC §10.2)."""
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.session import get_db
from app.main import app
from app.security import rate_limit as rl


@pytest.fixture
def db_session_with_cost(today_cost: Decimal | None = None):
    """Hook tests use this via parametrize; default no-cost session."""
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
async def test_limits_fresh_returns_full_quota(db_session_with_cost):
    """No prior activity → all three windows show max remaining."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/limits")
    assert response.status_code == 200
    data = response.json()
    assert data["jobs"]["per_minute"] == 2
    assert data["jobs"]["per_hour"] == 5
    assert data["jobs"]["per_day"] == 15
    assert data["cost"]["limit_usd"] == 5.0
    assert data["cost"]["spent_usd"] == 0.0
    assert data["cost"]["remaining_usd"] == 5.0


@pytest.mark.asyncio
async def test_limits_counts_prior_jobs(db_session_with_cost, _isolated_redis):
    """After two jobs this minute, per-minute remaining drops to 0."""
    fake = _isolated_redis
    # Two simulated successful records
    await rl.check_and_record(fake, "rl:jobs:127.0.0.1", rl.JOBS_WINDOWS)
    await rl.check_and_record(fake, "rl:jobs:127.0.0.1", rl.JOBS_WINDOWS)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/limits")
    assert response.status_code == 200
    data = response.json()
    assert data["jobs"]["per_minute"] == 0
    assert data["jobs"]["per_hour"] == 3  # 5 - 2
    assert data["jobs"]["per_day"] == 13


@pytest.mark.asyncio
async def test_limits_reflects_today_cost(_isolated_redis):
    """If daily_costs has a row, the response should reflect it."""
    from datetime import date

    from app.db.tables import DailyCost

    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    row = DailyCost(date=date.today(), total_cost_usd=Decimal("3.20"), job_count=8)
    exec_result = MagicMock()
    exec_result.scalars.return_value.all.return_value = []
    exec_result.scalar_one_or_none.return_value = row
    session.execute = AsyncMock(return_value=exec_result)

    async def override():
        yield session

    app.dependency_overrides[get_db] = override
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/limits")
    finally:
        app.dependency_overrides.clear()
    data = response.json()
    assert data["cost"]["spent_usd"] == 3.2
    assert data["cost"]["remaining_usd"] == pytest.approx(1.8)
