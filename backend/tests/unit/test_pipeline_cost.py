"""run_pipeline must debit daily_costs after a successful generation."""
import json
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.llm.base import LLMResult

VALID_MAP_JSON = json.dumps({
    "title": "Congo",
    "subtitle": "Michael Crichton, 1980",
    "blurb": "An expedition into the Congo.",
    "spoiler_mode": "full",
    "factions": [{"id": "erts", "label": "ERTS", "description": "Expedition.", "color_hint": "blue"}],
    "characters": [{
        "id": "peter",
        "name": "Peter Elliot",
        "role": "Primatologist",
        "description": "UC Berkeley professor.",
        "faction_id": "erts",
        "importance": "protagonist",
        "is_deceased_in_work": False,
        "spoiler_level": 0,
    }],
    "relationships": [],
    "notes": "Generated.",
})


def _fake_job():
    from app.db.tables import Job
    j = Job(
        id=__import__("uuid").UUID("11111111-1111-1111-1111-111111111111"),
        work_type="book",
        title_query="Congo",
        resolved_id="OL12345W",
        resolved_title="Congo",
        resolved_year=1980,
        resolved_meta={"author": "Michael Crichton", "source": "openlibrary"},
        model="claude-sonnet-4-6",
        formats=["interactive"],
        acknowledgement_at=__import__("datetime").datetime.now(),
        requester_ip="127.0.0.1",
        character_cap=20,
        status="queued",
    )
    return j


@pytest.mark.asyncio
async def test_run_pipeline_records_cost_on_success(tmp_path, monkeypatch):
    """After a successful LLM call, daily_costs is debited via record_cost."""
    from app.worker import pipeline

    monkeypatch.setattr(pipeline.settings, "artifact_storage_path", str(tmp_path))

    job = _fake_job()
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.get = AsyncMock(return_value=job)

    # Make _fetch_today (inside record_cost) return None so it creates a row.
    exec_result = MagicMock()
    exec_result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=exec_result)
    session.flush = AsyncMock()

    @pipeline.async_session_factory.__class__
    class _Maker:  # noqa: N801
        def __call__(self):
            class _Ctx:
                async def __aenter__(_self):
                    return session
                async def __aexit__(_self, *a):
                    return False
            return _Ctx()

    # Patch the factory so run_pipeline gets our session.
    monkeypatch.setattr(pipeline, "async_session_factory", lambda: _AsyncCtx(session))

    # Stub LLM client
    fake_client = AsyncMock()
    fake_client.generate_character_map = AsyncMock(return_value=LLMResult(
        text=VALID_MAP_JSON, input_tokens=100, output_tokens=200, cost_usd=0.07,
    ))
    monkeypatch.setattr(pipeline, "get_llm_client", lambda model: fake_client)

    # Skip enrichment + rendering side-effects
    monkeypatch.setattr(pipeline, "_enrich_with_credits", AsyncMock())
    monkeypatch.setattr(pipeline, "render_markdown", lambda cm: "# Congo")
    monkeypatch.setattr(pipeline, "render_pdf", lambda md, jid, d: tmp_path / "x.pdf")

    with patch("app.worker.pipeline.record_cost", new=AsyncMock()) as record:
        await pipeline.run_pipeline(str(job.id))
        assert record.await_count == 1
        called_with = record.await_args.args[1]
        assert called_with == Decimal("0.07")

    assert job.status == "done"


class _AsyncCtx:
    def __init__(self, session):
        self.session = session
    async def __aenter__(self):
        return self.session
    async def __aexit__(self, *a):
        return False
