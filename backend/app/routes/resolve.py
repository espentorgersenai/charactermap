import structlog
from fastapi import APIRouter, Request

from app.metadata.openlibrary import parse_ol_candidates, search_books
from app.metadata.tmdb import find_adaptation_for_book, search_film_tv
from app.models.api import ResolveRequest, ResolveResponse

log = structlog.get_logger()
router = APIRouter()


@router.post("/api/resolve", response_model=ResolveResponse)
async def resolve(request: Request, body: ResolveRequest) -> ResolveResponse:
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
    return ResolveResponse(candidates=candidates)
