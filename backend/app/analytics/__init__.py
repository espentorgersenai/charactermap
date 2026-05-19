"""Helper for writing analytics events from server-side code paths.

Keeps the analytics writer in one place so unit tests can patch a single
function. Properties are arbitrary JSON-serialisable dicts (validated by
the consumer's logic, not here).
"""
from __future__ import annotations

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.tables import AnalyticsEvent

log = structlog.get_logger()


async def record_event(
    session: AsyncSession,
    event_type: str,
    properties: dict | None = None,
    job_id=None,
) -> None:
    """Persist an analytics event row. Caller commits."""
    try:
        session.add(
            AnalyticsEvent(
                event_type=event_type,
                job_id=job_id,
                properties=properties or {},
            )
        )
    except Exception as e:
        # Analytics must never break a user-facing path.
        log.warning("analytics_record_failed", event=event_type, error=str(e))
