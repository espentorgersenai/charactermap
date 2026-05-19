import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics import record_event
from app.db.session import get_db
from app.metadata.openlibrary import parse_ol_candidates, search_books
from app.metadata.tmdb import find_adaptation_for_book, search_film_tv
from app.models.api import ResolveRequest, ResolveResponse
from app.security import rate_limit as rl

log = structlog.get_logger()
router = APIRouter()


@router.post("/api/resolve", response_model=ResolveResponse)
async def resolve(
    request: Request,
    body: ResolveRequest,
    session: AsyncSession = Depends(get_db),
) -> ResolveResponse:
    ip = rl.client_ip(request)
    decision = await rl.check_and_record(
        rl.get_redis(), f"rl:resolve:{ip}", rl.RESOLVE_WINDOWS
    )
    if not decision.allowed:
        log.warning(
            "resolve_rate_limited",
            ip=ip,
            window=decision.window_label,
            retry_after=decision.retry_after_seconds,
        )
        raise HTTPException(
            status_code=429,
            detail={
                "error": "Too many lookups. Please slow down.",
                "code": "RATE_LIMITED",
                "window": decision.window_label,
            },
            headers={"Retry-After": str(decision.retry_after_seconds)},
        )

    redis_client = None  # Phase 5 wires Redis; for now no caching

    if body.work_type == "book":
        raw = await search_books(body.query, redis_client)
        candidates = parse_ol_candidates(raw, body.query)

        # Attach TMDb adaptation to each candidate asynchronously
        for candidate in candidates:
            adaptation = await find_adaptation_for_book(candidate.title, candidate.year, redis_client)
            if adaptation:
                candidate.adaptation = adaptation

    else:  # film_tv
        candidates = await search_film_tv(body.query, redis_client)

    log.info("resolve", query=body.query, work_type=body.work_type, count=len(candidates))
    if candidates:
        auto_skipped = (
            len(candidates) >= 1
            and candidates[0].confidence_score is not None
            and candidates[0].confidence_score >= 0.90
        )
        await record_event(
            session,
            "resolve_hit",
            {
                "candidate_count": len(candidates),
                "auto_skipped": auto_skipped,
                "work_type": body.work_type,
            },
        )
    else:
        await record_event(
            session,
            "resolve_no_results",
            {"work_type": body.work_type},
        )
    await session.commit()
    return ResolveResponse(candidates=candidates)
