"""POST /api/analytics — pseudonymous product events (SPEC §14.2).

Event type is constrained to the documented enum; arbitrary properties pass
through to JSONB.
"""
from typing import Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.tables import AnalyticsEvent

log = structlog.get_logger()
router = APIRouter()

# SPEC §14.2 — keep in lockstep with that list.
VALID_EVENT_TYPES = {
    "form_submit",
    "resolve_hit",
    "resolve_no_results",
    "job_done",
    "job_failed",
    "job_refused",
    "headshot_override",
    "share_click",
    "recent_map_click",
}


class AnalyticsEventBody(BaseModel):
    event_type: str
    job_id: Optional[UUID] = None
    properties: dict = {}

    @field_validator("event_type")
    @classmethod
    def event_type_must_be_known(cls, v: str) -> str:
        if v not in VALID_EVENT_TYPES:
            raise ValueError(f"event_type must be one of {sorted(VALID_EVENT_TYPES)}")
        return v


@router.post("/api/analytics", status_code=204)
async def post_analytics(
    body: AnalyticsEventBody,
    session: AsyncSession = Depends(get_db),
) -> Response:
    row = AnalyticsEvent(
        event_type=body.event_type,
        job_id=body.job_id,
        properties=body.properties,
    )
    session.add(row)
    await session.commit()
    return Response(status_code=204)
