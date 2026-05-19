"""Shared fixtures for unit tests.

Auto-replaces `app.security.rate_limit.get_redis` with a fresh fakeredis
instance per test so the limiter behaves deterministically and never
attempts to connect to a real Redis.
"""
import fakeredis.aioredis
import pytest


@pytest.fixture(autouse=True)
async def _isolated_redis(monkeypatch):
    """Each test gets its own fakeredis instance. No state leaks across tests."""
    fake = fakeredis.aioredis.FakeRedis()
    monkeypatch.setattr(
        "app.security.rate_limit.get_redis",
        lambda: fake,
    )
    yield fake
    await fake.flushall()
    await fake.aclose()
