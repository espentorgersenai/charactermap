"""GET /api/limits — surface remaining quota to the frontend (SPEC §10.2)."""
from decimal import Decimal

import structlog
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.cost import get_today_cost
from app.db.session import get_db
from app.security import rate_limit as rl

log = structlog.get_logger()
router = APIRouter()


@router.get("/api/limits")
async def get_limits(
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> dict:
    ip = rl.client_ip(request)
    redis = rl.get_redis()
    jobs_remaining = await rl.peek_remaining(redis, f"rl:jobs:{ip}", rl.JOBS_WINDOWS)
    resolve_remaining = await rl.peek_remaining(redis, f"rl:resolve:{ip}", rl.RESOLVE_WINDOWS)

    today_cost = await get_today_cost(session)
    limit = Decimal(str(settings.daily_cost_limit_usd))
    remaining_cost = max(Decimal("0"), limit - today_cost)

    return {
        "jobs": jobs_remaining,
        "resolve": resolve_remaining,
        "cost": {
            "limit_usd": float(limit),
            "spent_usd": float(today_cost),
            "remaining_usd": float(remaining_cost),
        },
    }
