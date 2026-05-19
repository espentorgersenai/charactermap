"""Season-scoped TV credits + season list fetch.

When the user pins a TV generation to a specific season, get_credits must
hit /tv/{id}/season/{n}/credits instead of /aggregate_credits. get_tv_seasons
returns the season list used to populate the picker dropdown."""
import pytest

from app.metadata.tmdb import get_credits, get_tv_seasons


@pytest.mark.asyncio
async def test_get_credits_for_tv_with_season_uses_season_endpoint(monkeypatch):
    seen_paths: list[str] = []

    async def fake_get(path, params, redis_client):
        seen_paths.append(path)
        return {"cast": [], "crew": []}

    monkeypatch.setattr("app.metadata.tmdb._tmdb_get", fake_get)
    monkeypatch.setattr("app.metadata.tmdb.settings.tmdb_api_key", "key")

    await get_credits(61859, "tv", season=2)

    assert seen_paths == ["/tv/61859/season/2/credits"]


@pytest.mark.asyncio
async def test_get_credits_tv_without_season_unchanged(monkeypatch):
    """Sanity: season=None still routes to aggregate_credits — no regression."""
    seen_paths: list[str] = []

    async def fake_get(path, params, redis_client):
        seen_paths.append(path)
        return {"cast": [], "crew": []}

    monkeypatch.setattr("app.metadata.tmdb._tmdb_get", fake_get)
    monkeypatch.setattr("app.metadata.tmdb.settings.tmdb_api_key", "key")

    await get_credits(61859, "tv")

    assert any("/aggregate_credits" in p for p in seen_paths)
    assert not any("season" in p for p in seen_paths)


@pytest.mark.asyncio
async def test_get_tv_seasons_returns_sorted_excluding_specials(monkeypatch):
    async def fake_get(path, params, redis_client):
        return {
            "seasons": [
                {"season_number": 0, "name": "Specials", "air_date": "2010-01-01", "episode_count": 3},
                {"season_number": 2, "name": "Season 2", "air_date": "2017-09-01", "episode_count": 6},
                {"season_number": 1, "name": "Season 1", "air_date": "2016-02-01", "episode_count": 6},
            ]
        }

    monkeypatch.setattr("app.metadata.tmdb._tmdb_get", fake_get)
    monkeypatch.setattr("app.metadata.tmdb.settings.tmdb_api_key", "key")

    seasons = await get_tv_seasons(61859)

    # season 0 (specials) excluded; sorted ascending
    assert [s.number for s in seasons] == [1, 2]
    assert seasons[0].year == 2016
    assert seasons[1].name == "Season 2"
    assert seasons[1].episode_count == 6


@pytest.mark.asyncio
async def test_get_tv_seasons_handles_missing_air_date(monkeypatch):
    async def fake_get(path, params, redis_client):
        return {"seasons": [{"season_number": 1, "name": "Season 1", "air_date": ""}]}

    monkeypatch.setattr("app.metadata.tmdb._tmdb_get", fake_get)
    monkeypatch.setattr("app.metadata.tmdb.settings.tmdb_api_key", "key")

    seasons = await get_tv_seasons(1)

    assert len(seasons) == 1
    assert seasons[0].year is None


@pytest.mark.asyncio
async def test_get_tv_seasons_empty_on_failure(monkeypatch):
    async def fake_get(path, params, redis_client):
        raise RuntimeError("tmdb down")

    monkeypatch.setattr("app.metadata.tmdb._tmdb_get", fake_get)
    monkeypatch.setattr("app.metadata.tmdb.settings.tmdb_api_key", "key")

    seasons = await get_tv_seasons(99999)
    assert seasons == []


@pytest.mark.asyncio
async def test_get_tv_seasons_returns_empty_without_api_key(monkeypatch):
    monkeypatch.setattr("app.metadata.tmdb.settings.tmdb_api_key", "")
    seasons = await get_tv_seasons(1)
    assert seasons == []
