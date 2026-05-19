"""TV credits should come from /aggregate_credits, not /credits.

TMDB's `/tv/{id}/credits` returns the current main cast — for multi-season
shows where each season has a different cast (e.g. The Night Manager:
S1 with Olivia Colman as Burr, S2 with a near-disjoint cast) only the
latest season's regulars show up. `/aggregate_credits` returns the union
across all seasons with each actor's per-season roles flattened.
"""
from unittest.mock import AsyncMock

import pytest

from app.metadata.tmdb import _parse_cast, fetch_cast_strict, get_credits


def test_parse_cast_flattens_aggregate_roles():
    """aggregate_credits-shaped payload: one actor with multiple roles → multiple CastMembers."""
    data = {
        "cast": [
            {
                "id": 1,
                "name": "An Actor",
                "profile_path": "/photo.jpg",
                "order": 0,
                "roles": [
                    {"character": "Role One", "episode_count": 5},
                    {"character": "Role Two", "episode_count": 3},
                ],
            }
        ]
    }
    out = _parse_cast(data, cast_limit=10)
    assert len(out) == 2
    assert {m.character for m in out} == {"Role One", "Role Two"}
    assert all(m.tmdb_person_id == 1 for m in out)
    assert all(m.profile_path == "/photo.jpg" for m in out)


def test_parse_cast_movies_unchanged():
    """Movie /credits shape (single `character` per entry) still parses correctly."""
    data = {
        "cast": [
            {"id": 1, "name": "A", "character": "Char A", "profile_path": None, "order": 0},
            {"id": 2, "name": "B", "character": "Char B", "profile_path": "/p.jpg", "order": 1},
        ]
    }
    out = _parse_cast(data, cast_limit=10)
    assert [m.character for m in out] == ["Char A", "Char B"]


def test_parse_cast_skips_entries_missing_id_or_name():
    data = {"cast": [
        {"id": 1, "name": "OK", "character": "C", "order": 0},
        {"id": None, "name": "BadId", "character": "X", "order": 1},
        {"id": 3, "name": "", "character": "BlankName", "order": 2},
    ]}
    out = _parse_cast(data, cast_limit=10)
    assert [m.name for m in out] == ["OK"]


@pytest.mark.asyncio
async def test_get_credits_for_tv_calls_aggregate_credits(monkeypatch):
    """When media_type='tv', the call must hit /aggregate_credits."""
    seen_paths: list[str] = []

    async def fake_get(path, params, redis_client):
        seen_paths.append(path)
        return {"cast": [], "crew": []}

    monkeypatch.setattr("app.metadata.tmdb._tmdb_get", fake_get)
    monkeypatch.setattr("app.metadata.tmdb.settings.tmdb_api_key", "key")

    await get_credits(61859, "tv")

    assert any("/aggregate_credits" in p for p in seen_paths)
    assert not any(p.endswith("/credits") for p in seen_paths)


@pytest.mark.asyncio
async def test_get_credits_for_movie_calls_credits(monkeypatch):
    seen_paths: list[str] = []

    async def fake_get(path, params, redis_client):
        seen_paths.append(path)
        return {"cast": [], "crew": []}

    monkeypatch.setattr("app.metadata.tmdb._tmdb_get", fake_get)
    monkeypatch.setattr("app.metadata.tmdb.settings.tmdb_api_key", "key")

    await get_credits(680, "movie")

    assert seen_paths == ["/movie/680/credits"]


@pytest.mark.asyncio
async def test_fetch_cast_strict_tv_uses_aggregate(monkeypatch):
    seen_paths: list[str] = []

    async def fake_get(path, params, redis_client):
        seen_paths.append(path)
        return {"cast": []}

    monkeypatch.setattr("app.metadata.tmdb._tmdb_get", fake_get)
    monkeypatch.setattr("app.metadata.tmdb.settings.tmdb_api_key", "key")

    await fetch_cast_strict(61859, "tv")

    assert seen_paths == ["/tv/61859/aggregate_credits"]
