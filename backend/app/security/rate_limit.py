"""Redis sliding-window rate limiter (SPEC §10.2).

Per-IP windows for POST /api/jobs (2/min, 5/hr, 15/day) and POST /api/resolve
(30/min, 200/day). The implementation is a "sliding window log" using a sorted
set keyed by `rl:{scope}:{ip}`; each request adds a (now, uniq) member with
score=now, then we count members within each window bucket and reject if any
exceeds its limit. Old entries are pruned past the longest window.

Blocked attempts are NOT recorded — otherwise spammers extend their own block.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass

import redis.asyncio as aioredis
import structlog

from app.config import settings

log = structlog.get_logger()


@dataclass(frozen=True)
class Window:
    label: str
    seconds: int
    limit: int


# SPEC §10.2 baseline is 2/5/15 — temporarily loosened to 8/30/60 during the
# pre-launch iteration phase so the developer doesn't get throttled while
# testing. Tighten back before public deploy.
JOBS_WINDOWS: tuple[Window, ...] = (
    Window("per_minute", 60, 8),
    Window("per_hour", 3600, 30),
    Window("per_day", 86400, 60),
)

RESOLVE_WINDOWS: tuple[Window, ...] = (
    Window("per_minute", 60, 30),
    Window("per_day", 86400, 200),
)


@dataclass
class RateLimitDecision:
    allowed: bool
    retry_after_seconds: int = 0
    window_label: str | None = None
    remaining: dict[str, int] | None = None


_redis_singleton: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis:
    """Lazy singleton for the shared async Redis connection.

    Patched in tests via `unittest.mock.patch("app.security.rate_limit.get_redis", …)`.
    """
    global _redis_singleton
    if _redis_singleton is None:
        _redis_singleton = aioredis.from_url(settings.redis_url, decode_responses=False)
    return _redis_singleton


async def check_and_record(
    redis: aioredis.Redis,
    key: str,
    windows: tuple[Window, ...] | list[Window],
) -> RateLimitDecision:
    """Sliding-window check. Returns a decision and (when allowed) records the hit.

    Strategy: one sorted set per (scope, ip). Members are `"{now}:{uuid4}"`,
    score=now. We ZREMRANGEBYSCORE past the longest window, then for each
    window count members with score >= now - window_seconds; if any exceeds
    that window's limit we deny and compute Retry-After from the oldest
    member in that bucket.
    """
    now = time.time()
    longest = max(w.seconds for w in windows)

    # Prune anything past the longest window's tail.
    await redis.zremrangebyscore(key, 0, now - longest)

    remaining: dict[str, int] = {}
    for w in windows:
        count = await redis.zcount(key, now - w.seconds, "+inf")
        if count >= w.limit:
            # Retry-After = until the *oldest entry in this window* falls out.
            bucket = await redis.zrangebyscore(
                key, now - w.seconds, "+inf", start=0, num=1, withscores=True
            )
            if bucket:
                _member, oldest_score = bucket[0]
                retry = int((oldest_score + w.seconds) - now) + 1
            else:
                retry = w.seconds
            retry = max(retry, 1)
            return RateLimitDecision(
                allowed=False,
                retry_after_seconds=retry,
                window_label=w.label,
                remaining={ww.label: max(0, ww.limit - count) for ww in windows},
            )
        remaining[w.label] = max(0, w.limit - count - 1)

    member = f"{now}:{uuid.uuid4()}"
    await redis.zadd(key, {member: now})
    await redis.expire(key, longest)
    return RateLimitDecision(allowed=True, remaining=remaining)


async def peek_remaining(
    redis: aioredis.Redis,
    key: str,
    windows: tuple[Window, ...] | list[Window],
) -> dict[str, int]:
    """Read-only: how many requests are still allowed in each window? Does NOT
    add an entry. Used by GET /api/limits."""
    now = time.time()
    longest = max(w.seconds for w in windows)
    await redis.zremrangebyscore(key, 0, now - longest)
    out: dict[str, int] = {}
    for w in windows:
        count = await redis.zcount(key, now - w.seconds, "+inf")
        out[w.label] = max(0, w.limit - count)
    return out


def client_ip(request) -> str:
    """Resolve the caller IP, honouring X-Forwarded-For when set by the
    upstream nginx (we only deploy behind one)."""
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "0.0.0.0"
