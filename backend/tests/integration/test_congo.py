"""Integration test: POST /api/jobs → run_pipeline directly → status=done for Congo.

Skipped automatically if ANTHROPIC_API_KEY is not set or has no credits.
Requires a running PostgreSQL + Redis (docker compose up -d postgres redis).
"""

import asyncio
import os
import time

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set",
)

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


@pytest.mark.asyncio
async def test_post_job_and_run_to_done():
    """Full round-trip: create job → run pipeline directly → job is done with valid character_map."""
    from httpx import AsyncClient, ASGITransport
    from app.main import app
    from app.worker.pipeline import run_pipeline

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Create the job
        response = await client.post("/api/jobs", json=VALID_JOB_BODY)
        assert response.status_code == 202, response.text
        job_id = response.json()["job_id"]
        assert len(job_id) == 36

        # 2. Run the pipeline directly (bypasses RQ — no worker needed in tests)
        await run_pipeline(job_id)

        # 3. Poll until done (pipeline ran synchronously so should be immediate)
        deadline = time.monotonic() + 10
        job = None
        while time.monotonic() < deadline:
            r = await client.get(f"/api/jobs/{job_id}")
            assert r.status_code == 200
            job = r.json()
            if job["status"] in ("done", "refused", "failed"):
                break
            await asyncio.sleep(0.5)

        assert job is not None
        assert job["status"] == "done", (
            f"Expected done, got {job['status']}: {job.get('error_message')}"
        )

        # 4. Validate character_map structure
        cm = job["character_map"]
        assert cm is not None
        assert "characters" in cm
        assert len(cm["characters"]) >= 5, "Expected at least 5 characters for Congo"
        assert "factions" in cm
        assert len(cm["factions"]) >= 2

        # 5. All characters must have spoiler_level (swept to 3 if missing)
        for char in cm["characters"]:
            assert char.get("spoiler_level") is not None, (
                f"Missing spoiler_level on {char['name']}"
            )
            assert char["spoiler_level"] in (0, 1, 2, 3)

        # 6. All relationships must have spoiler_level
        for rel in cm["relationships"]:
            assert rel.get("spoiler_level") is not None
            assert rel["spoiler_level"] in (0, 1, 2, 3)
