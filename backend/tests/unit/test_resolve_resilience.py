"""Resolve must degrade to 'no results' rather than 500 when upstream services
reject the query (Open Library 422 for short queries, TMDb outages, etc.)."""
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.metadata.openlibrary import search_books
from app.metadata.tmdb import _tmdb_get


@pytest.mark.asyncio
async def test_search_books_returns_empty_on_422(monkeypatch):
    """Open Library 422 (short query) → empty list, not exception."""

    class _Resp:
        status_code = 422

        def raise_for_status(self):
            raise httpx.HTTPStatusError(
                "422", request=httpx.Request("GET", "http://x"), response=self,
            )

        def json(self):  # pragma: no cover - never reached
            return {}

    class _Client:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *a):
            return False
        async def get(self, *a, **kw):
            return _Resp()

    monkeypatch.setattr("app.metadata.openlibrary.httpx.AsyncClient", lambda **kw: _Client())
    out = await search_books("It")
    assert out == []


@pytest.mark.asyncio
async def test_search_books_returns_empty_on_network_error(monkeypatch):
    class _Client:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *a):
            return False
        async def get(self, *a, **kw):
            raise httpx.ConnectError("boom")

    monkeypatch.setattr("app.metadata.openlibrary.httpx.AsyncClient", lambda **kw: _Client())
    out = await search_books("anything")
    assert out == []


@pytest.mark.asyncio
async def test_tmdb_get_returns_empty_on_5xx(monkeypatch):
    class _Resp:
        status_code = 503

        def raise_for_status(self):
            raise httpx.HTTPStatusError(
                "503", request=httpx.Request("GET", "http://x"), response=self,
            )

        def json(self):  # pragma: no cover
            return {}

    class _Client:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *a):
            return False
        async def get(self, *a, **kw):
            return _Resp()

    monkeypatch.setattr("app.metadata.tmdb.httpx.AsyncClient", lambda **kw: _Client())
    out = await _tmdb_get("/search/multi", {"query": "x"})
    assert out == {}
