from datetime import datetime, timezone
from uuid import uuid4

import redis as redis_sync
import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from rq import Queue
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_db
from app.db.tables import Job
from app.models.job import JobCreateRequest, JobCreateResponse, JobStatusResponse
from app.worker.tasks import generate_character_map_task

log = structlog.get_logger()
router = APIRouter()


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
    }

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
