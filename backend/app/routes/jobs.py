import asyncio
import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import uuid4

import redis as redis_sync
import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from rq import Queue
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import async_session_factory, get_db
from app.db.tables import Job
from app.models.job import JobCreateRequest, JobCreateResponse, JobStatusResponse
from app.worker.tasks import generate_character_map_task

log = structlog.get_logger()
router = APIRouter()

_MODEL_QUALITY_ORDER = [
    "claude-opus-4-7",
    "claude-sonnet-4-6",
    "gpt-5.5",
    "gemini-2.5-pro",
    "claude-haiku-4-5-20251001",
]


async def find_best_cached_job(
    session: AsyncSession,
    resolved_id: str,
    spoiler_mode: str,
) -> Optional[Job]:
    result = await session.execute(
        select(Job).where(
            Job.resolved_id == resolved_id,
            Job.spoiler_mode == spoiler_mode,
            Job.status == "done",
            Job.deleted_at.is_(None),
            Job.character_map.is_not(None),
        )
    )
    jobs = result.scalars().all()
    if not jobs:
        return None
    jobs.sort(
        key=lambda j: _MODEL_QUALITY_ORDER.index(j.model)
        if j.model in _MODEL_QUALITY_ORDER else 99
    )
    return jobs[0]


def get_queue() -> Queue:
    conn = redis_sync.from_url(settings.redis_url)
    return Queue("character-maps", connection=conn)


@router.post("/api/jobs", response_model=JobCreateResponse, status_code=202)
async def create_job(
    body: JobCreateRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> JobCreateResponse:
    if not body.acknowledged_spoilers:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "acknowledged_spoilers must be true",
                "code": "SPOILERS_NOT_ACKNOWLEDGED",
            },
        )

    resolved = body.resolved
    work_type = "book" if resolved.source == "openlibrary" else "film_tv"
    resolved_meta = {
        "author": resolved.author,
        "director": resolved.director,
        "cover_url": resolved.cover_url,
        "source": resolved.source,
        # Stored for post-LLM credits lookup (Phase 4). film_tv: from the work
        # itself; book: from the adaptation if available.
        "media_type": (
            resolved.media_type
            or (resolved.adaptation.media_type if resolved.adaptation else None)
        ),
        "adaptation_tmdb_id": resolved.adaptation.tmdb_id if resolved.adaptation else None,
    }

    # Cache check: reuse the best existing result for this work
    cached = await find_best_cached_job(session, resolved.id, "full")
    if cached:
        cached_job = Job(
            id=uuid4(),
            work_type=work_type,
            title_query=body.title_query,
            resolved_id=resolved.id,
            resolved_title=resolved.title,
            resolved_year=resolved.year,
            resolved_meta=resolved_meta,
            model=cached.model,
            formats=body.formats,
            email=body.email,
            acknowledgement_at=datetime.now(tz=timezone.utc),
            status="done",
            completed_at=datetime.now(tz=timezone.utc),
            character_map=cached.character_map,
            estimated_cost_usd=Decimal("0"),
            requester_ip=request.client.host if request.client else "127.0.0.1",
            user_agent=request.headers.get("user-agent"),
        )
        session.add(cached_job)
        await session.commit()
        log.info("job_cache_hit", job_id=str(cached_job.id), source_model=cached.model)
        return JobCreateResponse(job_id=str(cached_job.id))

    job = Job(
        id=uuid4(),
        work_type=work_type,
        title_query=body.title_query,
        resolved_id=resolved.id,
        resolved_title=resolved.title,
        resolved_year=resolved.year,
        resolved_meta=resolved_meta,
        model=body.model,
        formats=body.formats,
        email=body.email,
        acknowledgement_at=datetime.now(tz=timezone.utc),
        status="queued",
        requester_ip=request.client.host if request.client else "127.0.0.1",
        user_agent=request.headers.get("user-agent"),
    )
    session.add(job)
    await session.commit()

    job_id = str(job.id)
    queue = get_queue()
    queue.enqueue(generate_character_map_task, job_id)
    log.info("job_created", job_id=job_id, model=body.model, work_type=work_type)

    return JobCreateResponse(job_id=job_id)


@router.get("/api/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job(job_id: str, session: AsyncSession = Depends(get_db)) -> JobStatusResponse:
    from uuid import UUID
    job = await session.get(Job, UUID(job_id))
    if not job:
        raise HTTPException(status_code=404, detail={"error": "job not found", "code": "NOT_FOUND"})
    return JobStatusResponse(
        job_id=str(job.id),
        status=job.status,
        character_map=job.character_map,
        error_code=job.error_code,
        error_message=job.error_message,
    )


_STATUS_TO_PROGRESS = {
    "queued": 0.05,
    "generating": 0.4,
    "done": 1.0,
    "refused": 1.0,
    "failed": 1.0,
}


@router.get("/api/jobs/{job_id}/stream")
async def stream_job(job_id: str) -> StreamingResponse:
    from uuid import UUID

    async def generate():
        last_status = None
        try:
            uid = UUID(job_id)
        except ValueError:
            yield f"event: error\ndata: {json.dumps({'error': 'invalid_job_id'})}\n\n"
            return

        while True:
            async with async_session_factory() as session:
                job = await session.get(Job, uid)

            if not job:
                yield f"event: error\ndata: {json.dumps({'error': 'not_found'})}\n\n"
                return

            if job.status != last_status:
                progress = _STATUS_TO_PROGRESS.get(job.status, 0.05)
                yield (
                    f"event: status\n"
                    f"data: {json.dumps({'status': job.status, 'progress': progress})}\n\n"
                )
                last_status = job.status

            if job.status in ("done", "refused", "failed"):
                if job.status == "done":
                    yield f"event: done\ndata: {json.dumps({'status': 'done'})}\n\n"
                else:
                    yield (
                        f"event: error\n"
                        f"data: {json.dumps({'error': job.error_code, 'message': job.error_message})}\n\n"
                    )
                return

            await asyncio.sleep(1.0)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
