from typing import Literal

import httpx
import structlog
from fastapi import APIRouter, HTTPException, Query

from app.metadata.tmdb import TMDB_HEADSHOT_BASE, fetch_cast_strict
from app.models.api import AdaptationCastResponse, CastMemberPublic

log = structlog.get_logger()
router = APIRouter()


@router.get(
    "/api/adaptations/{tmdb_id}/cast",
    response_model=AdaptationCastResponse,
)
async def get_adaptation_cast(
    tmdb_id: int,
    media_type: Literal["movie", "tv"] = Query(
        ..., description="TMDB resource kind — required because /movie/.. and /tv/.. credit endpoints differ"
    ),
) -> AdaptationCastResponse:
    try:
        cast = await fetch_cast_strict(tmdb_id, media_type)
    except RuntimeError as e:
        log.warning("adaptations_cast_misconfigured", tmdb_id=tmdb_id, error=str(e))
        raise HTTPException(status_code=503, detail="TMDB integration is not configured")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            log.info("adaptations_cast_unknown_id", tmdb_id=tmdb_id, media_type=media_type)
            raise HTTPException(status_code=404, detail=f"No {media_type} with TMDB id {tmdb_id}")
        log.warning("adaptations_cast_tmdb_failure", tmdb_id=tmdb_id, media_type=media_type, status=e.response.status_code)
        raise HTTPException(status_code=503, detail="TMDB is currently unavailable")
    except Exception as e:
        log.warning("adaptations_cast_tmdb_failure", tmdb_id=tmdb_id, media_type=media_type, error=str(e))
        raise HTTPException(status_code=503, detail="TMDB is currently unavailable")

    public_cast = [
        CastMemberPublic(
            tmdb_person_id=m.tmdb_person_id,
            name=m.name,
            character=m.character,
            headshot_url=f"{TMDB_HEADSHOT_BASE}{m.profile_path}" if m.profile_path else None,
            order=m.order,
        )
        for m in cast
    ]
    log.info("adaptations_cast", tmdb_id=tmdb_id, media_type=media_type, count=len(public_cast))
    return AdaptationCastResponse(tmdb_id=tmdb_id, media_type=media_type, cast=public_cast)
