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

from app.analytics import record_event
from app.config import settings
from app.cost import get_today_cost
from app.db.session import async_session_factory, get_db
from app.db.tables import Job
from app.models.job import JobCreateRequest, JobCreateResponse, JobStatusResponse
from app.security import rate_limit as rl
from app.security import turnstile
from app.worker.tasks import generate_character_map_task

log = structlog.get_logger()
router = APIRouter()

_MODEL_QUALITY_ORDER = [
    "claude-opus-4-8",
    "claude-opus-4-7",
    "claude-sonnet-4-6",
    "gpt-5.5",
    "gemini-2.5-pro",
    "claude-haiku-4-5-20251001",
]

# Cache identity also includes the pipeline/prompt-schema version. Bump this
# whenever a prompt, the output schema, or the grounding pipeline changes in a
# way that should invalidate previously-generated maps. Maps stamped with an
# older version (or none) won't be served from cache — the next request
# regenerates with the current pipeline. Old rows are kept (never deleted),
# they just stop matching. Stamped into resolved_meta (JSONB, no migration).
# v2: GoT-scale completeness + is_pov POV stars (2026-05-29).
PIPELINE_VERSION = "2"


async def find_best_cached_job(
    session: AsyncSession,
    resolved_id: str,
    spoiler_mode: str,
    character_cap: int,
    season: Optional[int] = None,
    adaptation_tmdb_id: Optional[int] = None,
) -> Optional[Job]:
    # Cap is part of the cache identity — a cap=10 map can't be served to a
    # cap=50 request and vice versa, since they're materially different maps.
    # Season (TV) and adaptation_tmdb_id (book → linked or unlinked film/TV)
    # are also identity-bearing: Night Manager S1 ≠ S2, and a book with
    # adaptation cleared ≠ a book matched to its (correct or wrong) film.
    result = await session.execute(
        select(Job).where(
            Job.resolved_id == resolved_id,
            Job.spoiler_mode == spoiler_mode,
            Job.character_cap == character_cap,
            Job.status == "done",
            Job.deleted_at.is_(None),
            Job.character_map.is_not(None),
        )
    )
    jobs = result.scalars().all()
    # Filter on JSONB fields in Python (small N — typical user has <5 cached
    # rows for the same resolved_id, and we only run the cache lookup once
    # per create_job).
    def _matches(j: Job) -> bool:
        meta = j.resolved_meta or {}
        j_season = meta.get("season")
        j_adapt = meta.get("adaptation_tmdb_id")
        # Only serve maps from the current pipeline/prompt version. Maps from an
        # older pipeline (or pre-versioning, where the key is absent) are skipped
        # so the next request regenerates with the current pipeline.
        if meta.get("pipeline_version") != PIPELINE_VERSION:
            return False
        return j_season == season and j_adapt == adaptation_tmdb_id

    jobs = [j for j in jobs if _matches(j)]
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

    ip = rl.client_ip(request)

    if settings.turnstile_secret_key:
        ok = await turnstile.verify_token(
            body.turnstile_token or "",
            settings.turnstile_secret_key,
            ip,
        )
        if not ok:
            log.warning("turnstile_failed", ip=ip)
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "Captcha verification failed. Please refresh and try again.",
                    "code": "TURNSTILE_FAILED",
                },
            )
    decision = await rl.check_and_record(rl.get_redis(), f"rl:jobs:{ip}", rl.JOBS_WINDOWS)
    if not decision.allowed:
        log.warning(
            "job_rate_limited",
            ip=ip,
            window=decision.window_label,
            retry_after=decision.retry_after_seconds,
        )
        raise HTTPException(
            status_code=429,
            detail={
                "error": "You're sending requests too quickly. Try again shortly.",
                "code": "RATE_LIMITED",
                "window": decision.window_label,
            },
            headers={"Retry-After": str(decision.retry_after_seconds)},
        )

    resolved = body.resolved
    work_type = "book" if resolved.source == "openlibrary" else "film_tv"
    # Only honor `season` when the work (or its adaptation) is TV. For movies
    # and book→movie linkages the field is meaningless and would pollute the
    # cache key.
    work_media_type = (
        resolved.media_type
        or (resolved.adaptation.media_type if resolved.adaptation else None)
    )
    effective_season = body.season if work_media_type == "tv" else None
    resolved_meta = {
        "author": resolved.author,
        "director": resolved.director,
        "cover_url": resolved.cover_url,
        "source": resolved.source,
        # Stored for post-LLM credits lookup (Phase 4). film_tv: from the work
        # itself; book: from the adaptation if available.
        "media_type": work_media_type,
        "adaptation_tmdb_id": resolved.adaptation.tmdb_id if resolved.adaptation else None,
        "season": effective_season,
        # Stamps which pipeline/prompt version produced (or will produce) this
        # map, so a version bump auto-invalidates stale cached maps.
        "pipeline_version": PIPELINE_VERSION,
    }

    # Cache check: reuse the best existing result for this work, cap,
    # season, and adaptation linkage.
    cached = await find_best_cached_job(
        session,
        resolved.id,
        "full",
        body.character_cap,
        season=effective_season,
        adaptation_tmdb_id=resolved.adaptation.tmdb_id if resolved.adaptation else None,
    )
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
            character_cap=body.character_cap,
            estimated_cost_usd=Decimal("0"),
            requester_ip=request.client.host if request.client else "127.0.0.1",
            user_agent=request.headers.get("user-agent"),
        )
        session.add(cached_job)
        await session.commit()
        log.info("job_cache_hit", job_id=str(cached_job.id), source_model=cached.model)
        return JobCreateResponse(job_id=str(cached_job.id))

    today_cost = await get_today_cost(session)
    if today_cost >= Decimal(str(settings.daily_cost_limit_usd)):
        log.warning(
            "job_blocked_budget_exhausted",
            today_cost_usd=str(today_cost),
            limit_usd=settings.daily_cost_limit_usd,
        )
        raise HTTPException(
            status_code=503,
            detail={
                "error": (
                    "The service has hit today's spending limit. "
                    "Please try again tomorrow."
                ),
                "code": "DAILY_BUDGET_EXHAUSTED",
            },
        )

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
        character_cap=body.character_cap,
        requester_ip=request.client.host if request.client else "127.0.0.1",
        user_agent=request.headers.get("user-agent"),
    )
    session.add(job)
    await record_event(
        session,
        "form_submit",
        {
            "model": body.model,
            "work_type": work_type,
            "spoiler_mode": "full",
            "formats": body.formats,
            "has_email": bool(body.email),
            "character_cap": body.character_cap,
        },
        job_id=job.id,
    )
    await session.commit()

    job_id = str(job.id)
    queue = get_queue()
    # 600s timeout (RQ default is 180s): the grounded two-stage path can take
    # 90-180s for Stage 1 web_search + 20-30s for Stage 2 structuring. Adding
    # headroom for network jitter and large analyses (Dune-class works).
    queue.enqueue(generate_character_map_task, job_id, job_timeout=600)
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
        progress_stage=job.progress_stage,
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

# Finer-grained progress within status='generating', mapped to the bar fill.
# Bumps the bar past the broad 'generating' tick so users see real movement
# during the long Stage 1 (web_search) phase.
_STAGE_TO_PROGRESS = {
    "searching":   0.25,   # Stage 1 web_search — longest phase (60-130s)
    "structuring": 0.65,   # Stage 2 closed-list JSON build (15-30s)
    "generating":  0.40,   # ungrounded single LLM call
    "enriching":   0.80,   # TMDB cast + creator fuzzy match
    "rendering":   0.92,   # markdown + PDF render
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

        last_stage = None
        while True:
            async with async_session_factory() as session:
                job = await session.get(Job, uid)

            if not job:
                yield f"event: error\ndata: {json.dumps({'error': 'not_found'})}\n\n"
                return

            stage = job.progress_stage
            if job.status != last_status or stage != last_stage:
                # Pick the finer-grained stage value if present; fall back to
                # status-level progress for queued/done/refused/failed.
                progress = (
                    _STAGE_TO_PROGRESS.get(stage)
                    if stage is not None
                    else _STATUS_TO_PROGRESS.get(job.status, 0.05)
                )
                payload = {
                    "status": job.status,
                    "progress": progress,
                    "stage": stage,
                }
                yield f"event: status\ndata: {json.dumps(payload)}\n\n"
                last_status = job.status
                last_stage = stage

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
