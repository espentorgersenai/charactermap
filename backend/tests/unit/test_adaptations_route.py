import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.metadata.tmdb import CastMember


_FIXTURE_CAST = [
    CastMember(name="John Travolta", character="Vincent Vega", tmdb_person_id=85, profile_path="/jt.jpg", order=0),
    CastMember(name="Samuel L. Jackson", character="Jules Winnfield", tmdb_person_id=2231, profile_path="/sj.jpg", order=1),
    CastMember(name="Harvey Keitel", character="The Wolf", tmdb_person_id=1037, profile_path=None, order=10),
]


@pytest.mark.asyncio
async def test_returns_cast_for_movie():
    with patch("app.routes.adaptations.fetch_cast_strict", new=AsyncMock(return_value=_FIXTURE_CAST)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/adaptations/680/cast", params={"media_type": "movie"})

    assert response.status_code == 200
    body = response.json()
    assert body["tmdb_id"] == 680
    assert body["media_type"] == "movie"
    assert len(body["cast"]) == 3
    assert body["cast"][0]["name"] == "John Travolta"
    assert body["cast"][0]["character"] == "Vincent Vega"
    assert body["cast"][0]["tmdb_person_id"] == 85
    assert body["cast"][0]["headshot_url"] == "https://image.tmdb.org/t/p/w185/jt.jpg"


@pytest.mark.asyncio
async def test_null_profile_path_yields_null_headshot():
    with patch("app.routes.adaptations.fetch_cast_strict", new=AsyncMock(return_value=_FIXTURE_CAST)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/adaptations/680/cast", params={"media_type": "movie"})

    wolf = next(c for c in response.json()["cast"] if c["character"] == "The Wolf")
    assert wolf["headshot_url"] is None


@pytest.mark.asyncio
async def test_missing_media_type_returns_422():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/adaptations/680/cast")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_invalid_media_type_returns_422():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/adaptations/680/cast", params={"media_type": "podcast"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_tmdb_unavailable_returns_503():
    with patch("app.routes.adaptations.fetch_cast_strict", new=AsyncMock(side_effect=RuntimeError("TMDB API key not configured"))):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/adaptations/680/cast", params={"media_type": "movie"})
    assert response.status_code == 503


@pytest.mark.asyncio
async def test_tmdb_5xx_returns_503():
    import httpx

    request = httpx.Request("GET", "https://api.themoviedb.org/3/movie/680/credits")
    response_obj = httpx.Response(500, request=request)
    err = httpx.HTTPStatusError("server error", request=request, response=response_obj)
    with patch("app.routes.adaptations.fetch_cast_strict", new=AsyncMock(side_effect=err)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/adaptations/680/cast", params={"media_type": "movie"})
    assert response.status_code == 503


@pytest.mark.asyncio
async def test_tmdb_404_returns_404():
    """Unknown TMDB id should surface as 404, not lumped into 503."""
    import httpx

    request = httpx.Request("GET", "https://api.themoviedb.org/3/movie/9999999/credits")
    response_obj = httpx.Response(404, request=request)
    err = httpx.HTTPStatusError("not found", request=request, response=response_obj)
    with patch("app.routes.adaptations.fetch_cast_strict", new=AsyncMock(side_effect=err)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/adaptations/9999999/cast", params={"media_type": "movie"})
    assert response.status_code == 404
    assert "9999999" in response.json()["detail"]


@pytest.mark.asyncio
async def test_empty_cast_returns_200():
    """Genuine empty cast is a valid response, distinct from a TMDB outage."""
    with patch("app.routes.adaptations.fetch_cast_strict", new=AsyncMock(return_value=[])):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/adaptations/680/cast", params={"media_type": "movie"})
    assert response.status_code == 200
    assert response.json()["cast"] == []
