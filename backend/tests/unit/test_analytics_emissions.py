"""Verifies the per-event-type emission paths (SPEC §14.2)."""
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from app.db.session import get_db
from app.db.tables import AnalyticsEvent
from app.main import app


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


def _added_events(session) -> list[AnalyticsEvent]:
    return [c.args[0] for c in session.add.call_args_list
            if isinstance(c.args[0], AnalyticsEvent)]


@pytest.mark.asyncio
async def test_post_jobs_emits_form_submit(mock_session):
    """Every successful POST /api/jobs writes a `form_submit` event."""
    with patch("app.routes.jobs.get_queue") as mq:
        mq.return_value = MagicMock()
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.post("/api/jobs", json=VALID_JOB_BODY)
    assert r.status_code == 202
    events = _added_events(mock_session)
    assert len(events) == 1
    ev = events[0]
    assert ev.event_type == "form_submit"
    assert ev.properties["model"] == "claude-sonnet-4-6"
    assert ev.properties["work_type"] == "book"
    assert ev.properties["formats"] == ["interactive"]
    assert ev.properties["has_email"] is False


@pytest.mark.asyncio
async def test_pipeline_done_emits_job_done(tmp_path, monkeypatch):
    """run_pipeline on success emits job_done with model + character_count."""
    from app.db.tables import Job
    from app.llm.base import LLMResult
    from app.worker import pipeline

    monkeypatch.setattr(pipeline.settings, "artifact_storage_path", str(tmp_path))

    job = Job(
        id=UUID("22222222-2222-2222-2222-222222222222"),
        work_type="book",
        title_query="Congo",
        resolved_id="OL1",
        resolved_title="Congo",
        resolved_year=1980,
        resolved_meta={"author": "Michael Crichton", "source": "openlibrary"},
        model="claude-sonnet-4-6",
        formats=["interactive"],
        acknowledgement_at=datetime.now(tz=timezone.utc),
        requester_ip="127.0.0.1",
        character_cap=20,
        status="queued",
    )

    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.get = AsyncMock(return_value=job)
    exec_result = MagicMock()
    exec_result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=exec_result)
    session.flush = AsyncMock()

    class _Ctx:
        async def __aenter__(_self):
            return session

        async def __aexit__(_self, *a):
            return False

    monkeypatch.setattr(pipeline, "async_session_factory", lambda: _Ctx())

    VALID_MAP_JSON = json.dumps({
        "title": "Congo",
        "subtitle": "X",
        "blurb": "Y",
        "spoiler_mode": "full",
        "factions": [{"id": "f", "label": "F", "description": "f", "color_hint": "blue"}],
        "characters": [{
            "id": "p", "name": "P", "role": "R", "description": "d",
            "faction_id": "f", "importance": "protagonist",
            "is_deceased_in_work": False, "spoiler_level": 0,
        }],
        "relationships": [], "notes": "",
    })

    fake_client = AsyncMock()
    fake_client.generate_character_map = AsyncMock(return_value=LLMResult(
        text=VALID_MAP_JSON, input_tokens=100, output_tokens=200, cost_usd=0.06,
    ))
    monkeypatch.setattr(pipeline, "get_llm_client", lambda model: fake_client)
    monkeypatch.setattr(pipeline, "_enrich_with_credits", AsyncMock())
    monkeypatch.setattr(pipeline, "render_markdown", lambda cm: "# X")
    monkeypatch.setattr(pipeline, "render_pdf", lambda md, jid, d: tmp_path / "x.pdf")

    await pipeline.run_pipeline(str(job.id))

    events = _added_events(session)
    types = [e.event_type for e in events]
    assert "job_done" in types
    done_ev = next(e for e in events if e.event_type == "job_done")
    assert done_ev.properties["model"] == "claude-sonnet-4-6"
    assert done_ev.properties["character_count"] == 1
    assert done_ev.properties["has_adaptation"] is False
    assert "duration_ms" in done_ev.properties
