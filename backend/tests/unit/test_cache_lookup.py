import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from app.routes.jobs import find_best_cached_job
from app.db.tables import Job

MODEL_QUALITY_ORDER = [
    "claude-opus-4-7",
    "claude-sonnet-4-6",
    "gpt-5.5",
    "gemini-2.5-pro",
    "claude-haiku-4-5-20251001",
]


def _make_job(model: str, character_map: dict | None = None, deleted: bool = False) -> Job:
    j = MagicMock(spec=Job)
    j.model = model
    j.status = "done"
    j.character_map = character_map or {"title": "Congo"}
    j.deleted_at = datetime.now(tz=timezone.utc) if deleted else None
    return j


def _make_session(jobs: list) -> AsyncMock:
    """Build an AsyncMock session whose execute() returns a sync-chainable result."""
    execute_result = MagicMock()
    execute_result.scalars.return_value.all.return_value = jobs
    session = AsyncMock()
    session.execute = AsyncMock(return_value=execute_result)
    return session


@pytest.mark.asyncio
async def test_opus_job_returned_when_available():
    sonnet_job = _make_job("claude-sonnet-4-6")
    opus_job = _make_job("claude-opus-4-7")
    session = _make_session([sonnet_job, opus_job])

    result = await find_best_cached_job(session, "OL12345W", "full", 20)
    assert result is opus_job


@pytest.mark.asyncio
async def test_sonnet_returned_when_no_opus():
    haiku_job = _make_job("claude-haiku-4-5-20251001")
    sonnet_job = _make_job("claude-sonnet-4-6")
    session = _make_session([haiku_job, sonnet_job])

    result = await find_best_cached_job(session, "OL12345W", "full", 20)
    assert result is sonnet_job


@pytest.mark.asyncio
async def test_no_cached_jobs_returns_none():
    session = _make_session([])

    result = await find_best_cached_job(session, "OL12345W", "full", 20)
    assert result is None


@pytest.mark.asyncio
async def test_unknown_model_ranked_last():
    unknown_job = _make_job("gpt-99")
    haiku_job = _make_job("claude-haiku-4-5-20251001")
    session = _make_session([unknown_job, haiku_job])

    result = await find_best_cached_job(session, "OL12345W", "full", 20)
    assert result is haiku_job
