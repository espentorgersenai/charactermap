import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.db.session import get_db

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
def mock_db_session():
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    # Return empty list from execute() so find_best_cached_job finds no cache hit
    execute_result = MagicMock()
    execute_result.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(return_value=execute_result)

    async def override():
        yield session

    app.dependency_overrides[get_db] = override
    yield session
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_acknowledged_spoilers_false_returns_400(mock_db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/jobs", json={**VALID_JOB_BODY, "acknowledged_spoilers": False})
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "SPOILERS_NOT_ACKNOWLEDGED"


@pytest.mark.asyncio
async def test_missing_acknowledged_spoilers_returns_422(mock_db_session):
    body = {k: v for k, v in VALID_JOB_BODY.items() if k != "acknowledged_spoilers"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/jobs", json=body)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_valid_request_returns_202_with_job_id(mock_db_session):
    with patch("app.routes.jobs.get_queue") as mock_get_queue:
        mock_queue = MagicMock()
        mock_get_queue.return_value = mock_queue

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/jobs", json=VALID_JOB_BODY)

    assert response.status_code == 202
    data = response.json()
    assert "job_id" in data
    assert len(data["job_id"]) == 36  # UUID format


@pytest.mark.asyncio
async def test_valid_request_enqueues_task(mock_db_session):
    with patch("app.routes.jobs.get_queue") as mock_get_queue:
        mock_queue = MagicMock()
        mock_get_queue.return_value = mock_queue

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/jobs", json=VALID_JOB_BODY)

    assert response.status_code == 202
    mock_queue.enqueue.assert_called_once()
    from app.worker.tasks import generate_character_map_task
    assert mock_queue.enqueue.call_args.args[0] is generate_character_map_task
