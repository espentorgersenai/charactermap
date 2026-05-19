"""POST /api/analytics persists a row in analytics_events (SPEC §14.2)."""
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.session import get_db
from app.db.tables import AnalyticsEvent
from app.main import app


@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()

    async def override():
        yield session

    app.dependency_overrides[get_db] = override
    yield session
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_post_analytics_records_event(mock_session):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/analytics",
            json={
                "event_type": "form_submit",
                "properties": {
                    "model": "claude-sonnet-4-6",
                    "work_type": "book",
                    "formats": ["interactive", "pdf"],
                    "has_email": True,
                },
            },
        )
    assert response.status_code == 204
    mock_session.add.assert_called_once()
    row = mock_session.add.call_args.args[0]
    assert isinstance(row, AnalyticsEvent)
    assert row.event_type == "form_submit"
    assert row.properties == {
        "model": "claude-sonnet-4-6",
        "work_type": "book",
        "formats": ["interactive", "pdf"],
        "has_email": True,
    }


@pytest.mark.asyncio
async def test_post_analytics_with_job_id(mock_session):
    job_id = str(uuid4())
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/analytics",
            json={
                "event_type": "job_done",
                "job_id": job_id,
                "properties": {"model": "claude-opus-4-7", "character_count": 12},
            },
        )
    assert response.status_code == 204
    row = mock_session.add.call_args.args[0]
    assert str(row.job_id) == job_id


@pytest.mark.asyncio
async def test_post_analytics_rejects_unknown_event_type(mock_session):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/analytics",
            json={"event_type": "rm_rf_root", "properties": {}},
        )
    assert response.status_code == 422
    mock_session.add.assert_not_called()


@pytest.mark.asyncio
async def test_post_analytics_empty_properties_ok(mock_session):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/analytics",
            json={"event_type": "resolve_no_results"},
        )
    assert response.status_code == 204
    row = mock_session.add.call_args.args[0]
    assert row.properties == {}
