"""Tests for fetch_collection_cast — merging cast across films in a TMDB collection."""
import pytest
from unittest.mock import AsyncMock, patch

from app.metadata.tmdb import (
    CastMember,
    _merge_casts,
    fetch_collection_cast,
)


def test_merge_casts_dedupes_by_person_id_keeps_lowest_order():
    a = [
        CastMember(name="Andy Serkis", character="Gollum", tmdb_person_id=1, profile_path="/a.jpg", order=12),
        CastMember(name="Ian McKellen", character="Gandalf", tmdb_person_id=2, profile_path="/b.jpg", order=1),
    ]
    b = [
        CastMember(name="Andy Serkis", character="Gollum", tmdb_person_id=1, profile_path="/a.jpg", order=5),  # better order
        CastMember(name="Martin Freeman", character="Bilbo", tmdb_person_id=3, profile_path="/c.jpg", order=0),
    ]
    merged = _merge_casts([a, b], cast_limit=10)

    serkis = next(m for m in merged if m.tmdb_person_id == 1)
    assert serkis.order == 5  # kept lower-order entry
    assert {m.tmdb_person_id for m in merged} == {1, 2, 3}


def test_merge_casts_sorts_by_order_ascending():
    casts = [[
        CastMember(name="A", character="A", tmdb_person_id=1, profile_path=None, order=10),
        CastMember(name="B", character="B", tmdb_person_id=2, profile_path=None, order=0),
        CastMember(name="C", character="C", tmdb_person_id=3, profile_path=None, order=5),
    ]]
    merged = _merge_casts(casts, cast_limit=10)
    assert [m.tmdb_person_id for m in merged] == [2, 3, 1]


def test_merge_casts_applies_limit():
    cast = [
        CastMember(name=f"P{i}", character=f"C{i}", tmdb_person_id=i, profile_path=None, order=i)
        for i in range(20)
    ]
    merged = _merge_casts([cast], cast_limit=5)
    assert len(merged) == 5
    assert [m.tmdb_person_id for m in merged] == [0, 1, 2, 3, 4]


@pytest.mark.asyncio
async def test_tv_bypasses_collection_logic():
    """TV has no collection concept — must fall through to single-cast path."""
    expected = [CastMember(name="Bryan Cranston", character="Walter White",
                           tmdb_person_id=17419, profile_path="/wh.jpg", order=0)]
    with patch("app.metadata.tmdb._fetch_single_cast_safe", new=AsyncMock(return_value=expected)) as mock_single, \
         patch("app.metadata.tmdb._tmdb_get", new=AsyncMock()) as mock_get, \
         patch("app.metadata.tmdb.settings") as mock_settings:
        mock_settings.tmdb_api_key = "k"
        result = await fetch_collection_cast(1396, "tv", None, 30)

    assert result == expected
    mock_single.assert_called_once_with(1396, "tv", None, 30)
    # Must not have hit /movie/... or /collection/...
    assert not mock_get.called


@pytest.mark.asyncio
async def test_movie_without_collection_returns_own_cast():
    """A standalone movie (no belongs_to_collection) returns just its cast."""
    own = [CastMember(name="Solo", character="One", tmdb_person_id=1, profile_path=None, order=0)]

    async def fake_get(path, *a, **kw):
        if path == "/movie/42":
            return {"belongs_to_collection": None}
        raise AssertionError(f"unexpected call: {path}")

    with patch("app.metadata.tmdb._fetch_single_cast_safe", new=AsyncMock(return_value=own)), \
         patch("app.metadata.tmdb._tmdb_get", new=AsyncMock(side_effect=fake_get)), \
         patch("app.metadata.tmdb.settings") as mock_settings:
        mock_settings.tmdb_api_key = "k"
        result = await fetch_collection_cast(42, "movie", None, 30)

    assert result == own


@pytest.mark.asyncio
async def test_movie_in_collection_aggregates_parts():
    """A movie in a collection: cast merged from all parts; Gollum-style
    bonus characters from sibling films are included."""
    # Stub TMDB API responses
    def cast_for(part_id):
        if part_id == 100:
            return [CastMember(name="Bilbo", character="Bilbo", tmdb_person_id=1, profile_path=None, order=0)]
        if part_id == 101:
            return [
                CastMember(name="Bilbo", character="Bilbo", tmdb_person_id=1, profile_path=None, order=0),
                CastMember(name="Andy Serkis", character="Gollum", tmdb_person_id=2, profile_path="/g.jpg", order=8),
            ]
        if part_id == 102:
            return [
                CastMember(name="Bilbo", character="Bilbo", tmdb_person_id=1, profile_path=None, order=0),
                CastMember(name="Eagles VO", character="Lord of the Eagles", tmdb_person_id=3, profile_path=None, order=20),
            ]
        return []

    async def fake_single(tmdb_id, media_type, redis_client, cast_limit):
        return cast_for(tmdb_id)

    async def fake_tmdb_get(path, *a, **kw):
        if path == "/movie/100":
            return {"belongs_to_collection": {"id": 999, "name": "Hobbit Collection"}}
        if path == "/collection/999":
            return {"parts": [{"id": 100}, {"id": 101}, {"id": 102}]}
        raise AssertionError(f"unexpected path: {path}")

    with patch("app.metadata.tmdb._fetch_single_cast_safe", new=AsyncMock(side_effect=fake_single)), \
         patch("app.metadata.tmdb._tmdb_get", new=AsyncMock(side_effect=fake_tmdb_get)), \
         patch("app.metadata.tmdb.settings") as mock_settings:
        mock_settings.tmdb_api_key = "k"
        result = await fetch_collection_cast(100, "movie", None, 30)

    by_id = {m.tmdb_person_id: m for m in result}
    assert 1 in by_id  # Bilbo
    assert 2 in by_id  # Gollum (from sibling film 101)
    assert 3 in by_id  # Lord of the Eagles (from sibling film 102)


@pytest.mark.asyncio
async def test_one_failing_sibling_does_not_break_others():
    """If one sibling film's credits call fails, the others still contribute."""
    async def fake_single(tmdb_id, media_type, redis_client, cast_limit):
        if tmdb_id == 101:
            return []  # simulate per-part failure
        if tmdb_id == 100:
            return [CastMember(name="Bilbo", character="Bilbo", tmdb_person_id=1, profile_path=None, order=0)]
        if tmdb_id == 102:
            return [CastMember(name="Eagles", character="Lord of the Eagles", tmdb_person_id=3, profile_path=None, order=20)]
        return []

    async def fake_tmdb_get(path, *a, **kw):
        if path == "/movie/100":
            return {"belongs_to_collection": {"id": 999}}
        if path == "/collection/999":
            return {"parts": [{"id": 100}, {"id": 101}, {"id": 102}]}
        raise AssertionError(path)

    with patch("app.metadata.tmdb._fetch_single_cast_safe", new=AsyncMock(side_effect=fake_single)), \
         patch("app.metadata.tmdb._tmdb_get", new=AsyncMock(side_effect=fake_tmdb_get)), \
         patch("app.metadata.tmdb.settings") as mock_settings:
        mock_settings.tmdb_api_key = "k"
        result = await fetch_collection_cast(100, "movie", None, 30)

    assert {m.tmdb_person_id for m in result} == {1, 3}


@pytest.mark.asyncio
async def test_collection_lookup_failure_falls_back_to_single_film():
    """If /collection/{id} itself fails, we still return the requesting film's cast."""
    own = [CastMember(name="Solo", character="One", tmdb_person_id=1, profile_path=None, order=0)]

    async def fake_tmdb_get(path, *a, **kw):
        if path == "/movie/200":
            return {"belongs_to_collection": {"id": 555}}
        if path == "/collection/555":
            raise Exception("TMDB hiccup")
        raise AssertionError(path)

    with patch("app.metadata.tmdb._fetch_single_cast_safe", new=AsyncMock(return_value=own)), \
         patch("app.metadata.tmdb._tmdb_get", new=AsyncMock(side_effect=fake_tmdb_get)), \
         patch("app.metadata.tmdb.settings") as mock_settings:
        mock_settings.tmdb_api_key = "k"
        result = await fetch_collection_cast(200, "movie", None, 30)

    assert result == own


@pytest.mark.asyncio
async def test_no_tmdb_key_returns_empty():
    with patch("app.metadata.tmdb.settings") as mock_settings:
        mock_settings.tmdb_api_key = ""
        result = await fetch_collection_cast(100, "movie", None, 30)
    assert result == []
