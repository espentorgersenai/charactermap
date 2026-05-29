import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from app.routes.jobs import find_best_cached_job, PIPELINE_VERSION
from app.db.tables import Job

MODEL_QUALITY_ORDER = [
    "claude-opus-4-8",
    "claude-opus-4-7",
    "claude-sonnet-4-6",
    "gpt-5.5",
    "gemini-2.5-pro",
    "claude-haiku-4-5-20251001",
]


def _make_job(
    model: str,
    character_map: dict | None = None,
    deleted: bool = False,
    season: int | None = None,
    adaptation_tmdb_id: int | None = None,
    pipeline_version: str | None = PIPELINE_VERSION,
) -> Job:
    j = MagicMock(spec=Job)
    j.model = model
    j.status = "done"
    j.character_map = character_map or {"title": "Congo"}
    j.deleted_at = datetime.now(tz=timezone.utc) if deleted else None
    j.resolved_meta = {
        "season": season,
        "adaptation_tmdb_id": adaptation_tmdb_id,
        "pipeline_version": pipeline_version,
    }
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


@pytest.mark.asyncio
async def test_season_pinned_lookup_skips_aggregate_cache():
    """A request pinned to S2 must not pull an All-Seasons cached map."""
    all_seasons = _make_job("claude-opus-4-7", season=None)
    s2 = _make_job("claude-sonnet-4-6", season=2)
    session = _make_session([all_seasons, s2])

    result = await find_best_cached_job(session, "61859", "full", 20, season=2)
    assert result is s2


@pytest.mark.asyncio
async def test_no_season_lookup_skips_pinned_cache():
    """An All-Seasons request must not pull a S2-pinned cached map."""
    s2 = _make_job("claude-opus-4-7", season=2)
    session = _make_session([s2])

    result = await find_best_cached_job(session, "61859", "full", 20, season=None)
    assert result is None


@pytest.mark.asyncio
async def test_cleared_adaptation_skips_linked_cache():
    """Book request with adaptation_tmdb_id=None must not reuse a cached
    book-with-adaptation map (the maps will materially differ)."""
    with_adaptation = _make_job("claude-opus-4-7", adaptation_tmdb_id=12345)
    session = _make_session([with_adaptation])

    result = await find_best_cached_job(
        session, "OLBookW", "full", 20, adaptation_tmdb_id=None
    )
    assert result is None


@pytest.mark.asyncio
async def test_stale_pipeline_version_skipped():
    """A map from an older pipeline version (or pre-versioning) must not be
    served — the next request regenerates with the current pipeline."""
    old = _make_job("claude-opus-4-8", pipeline_version="1")
    none_version = _make_job("claude-opus-4-8", pipeline_version=None)
    session = _make_session([old, none_version])

    result = await find_best_cached_job(session, "OL12345W", "full", 20)
    assert result is None


@pytest.mark.asyncio
async def test_current_version_served_over_stale():
    """Among mixed versions, only the current-version map is eligible."""
    stale = _make_job("claude-opus-4-8", pipeline_version="1")
    current = _make_job("claude-sonnet-4-6")  # defaults to current version
    session = _make_session([stale, current])

    result = await find_best_cached_job(session, "OL12345W", "full", 20)
    assert result is current


@pytest.mark.asyncio
async def test_matching_adaptation_returns_cache():
    j = _make_job("claude-opus-4-7", adaptation_tmdb_id=12345)
    session = _make_session([j])

    result = await find_best_cached_job(
        session, "OLBookW", "full", 20, adaptation_tmdb_id=12345
    )
    assert result is j
