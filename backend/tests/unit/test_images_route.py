import pytest
from pathlib import Path
from unittest.mock import patch
from httpx import AsyncClient, ASGITransport, Response, Request

from app.main import app


def _minimal_png() -> bytes:
    """Real validation-clean 1x1 RGB PNG — reused pattern from PDF tests."""
    import struct
    import zlib

    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    raw = b"\x00\xff\xff\xff"
    return sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


@pytest.fixture
def isolated_cache(tmp_path, monkeypatch):
    """Point the proxy at a fresh temp dir for each test."""
    from app import config as config_mod
    monkeypatch.setattr(config_mod.settings, "image_cache_path", str(tmp_path))
    return tmp_path


@pytest.mark.asyncio
async def test_invalid_extension_returns_400(isolated_cache):
    """Validator rejects anything outside the whitelisted image extensions."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/images/tmdb/abc.exe")
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_invalid_characters_returns_400(isolated_cache):
    """Filename with shell metacharacters fails the [A-Za-z0-9._-] character class."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/images/tmdb/$(whoami).jpg")
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_url_encoded_slash_does_not_escape_segment(isolated_cache):
    """FastAPI's path-without-:path segment rejects encoded slashes outright —
    they never reach our handler, so neither the cache nor TMDb is touched."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/images/tmdb/..%2Fpasswd.jpg")
    # 404 from the router (multi-segment doesn't match), not 200 from a bypass
    assert response.status_code in (400, 404)


@pytest.mark.asyncio
async def test_cache_miss_fetches_and_stores(isolated_cache):
    fake_png = _minimal_png()
    captured = {}

    class _FakeHttpxClient:
        def __init__(self, *a, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def get(self, url):
            captured["url"] = url
            return Response(200, content=fake_png, request=Request("GET", url))

    with patch("app.routes.images.httpx.AsyncClient", _FakeHttpxClient):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/images/tmdb/abc.jpg")

    assert response.status_code == 200
    assert response.headers["x-cache"] == "MISS"
    assert response.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert response.content == fake_png
    # File was persisted to the cache dir
    cached = isolated_cache / "w185" / "abc.jpg"
    assert cached.exists()
    assert cached.read_bytes() == fake_png
    assert captured["url"] == "https://image.tmdb.org/t/p/w185/abc.jpg"


@pytest.mark.asyncio
async def test_cache_hit_serves_without_upstream_call(isolated_cache):
    # Pre-seed the cache
    cached_bytes = b"fakebytes-from-disk"
    cache_path = isolated_cache / "w185" / "abc.jpg"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_bytes(cached_bytes)

    call_count = {"n": 0}

    class _FakeHttpxClient:
        def __init__(self, *a, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def get(self, url):
            call_count["n"] += 1
            raise AssertionError("Should not have hit upstream for a cache HIT")

    with patch("app.routes.images.httpx.AsyncClient", _FakeHttpxClient):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/images/tmdb/abc.jpg")

    assert response.status_code == 200
    assert response.headers["x-cache"] == "HIT"
    assert response.content == cached_bytes
    assert call_count["n"] == 0


@pytest.mark.asyncio
async def test_upstream_404_returns_404(isolated_cache):
    class _FakeHttpxClient:
        def __init__(self, *a, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def get(self, url):
            return Response(404, content=b"", request=Request("GET", url))

    with patch("app.routes.images.httpx.AsyncClient", _FakeHttpxClient):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/images/tmdb/missing.jpg")

    assert response.status_code == 404
    assert not (isolated_cache / "w185" / "missing.jpg").exists()  # not cached


@pytest.mark.asyncio
async def test_upstream_5xx_returns_502(isolated_cache):
    class _FakeHttpxClient:
        def __init__(self, *a, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def get(self, url):
            return Response(503, content=b"", request=Request("GET", url))

    with patch("app.routes.images.httpx.AsyncClient", _FakeHttpxClient):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/images/tmdb/abc.jpg")
    assert response.status_code == 502


@pytest.mark.asyncio
async def test_upstream_network_exception_returns_502(isolated_cache):
    class _FakeHttpxClient:
        def __init__(self, *a, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def get(self, url):
            raise ConnectionError("network died")

    with patch("app.routes.images.httpx.AsyncClient", _FakeHttpxClient):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/images/tmdb/abc.jpg")
    assert response.status_code == 502


@pytest.mark.asyncio
async def test_png_extension_supported(isolated_cache):
    class _FakeHttpxClient:
        def __init__(self, *a, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def get(self, url):
            return Response(200, content=b"png-bytes", request=Request("GET", url))

    with patch("app.routes.images.httpx.AsyncClient", _FakeHttpxClient):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/images/tmdb/abc.png")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
