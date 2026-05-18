"""TMDb image proxy per SPEC §9.5.

Cache layout: settings.image_cache_path / w185 / abc.jpg
URL pattern:  GET /images/tmdb/abc.jpg  → proxies image.tmdb.org/t/p/w185/abc.jpg

Rationale:
- TMDb rate-limits direct hot-linking from production apps.
- Pages with N headshots make N requests to TMDb on every load otherwise.
- TMDb outages would break every map at once if we hot-link.

The cache is content-addressed (TMDb paths are immutable hashes), so we set
Cache-Control: immutable, 1 year. Browser and nginx tiers can both cache.
"""
import re
from pathlib import Path

import httpx
import structlog
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response

from app.config import settings

log = structlog.get_logger()
router = APIRouter()

# TMDb profile/poster paths look like /abc123.jpg — letters, digits, ./_-
_PATH_RE = re.compile(r"^[A-Za-z0-9._-]+\.(jpg|jpeg|png|webp)$")
_TMDB_BASE = "https://image.tmdb.org/t/p/w185"
_FETCH_TIMEOUT_S = 10.0
_CONTENT_TYPE_BY_SUFFIX = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}
_CACHE_CONTROL = "public, max-age=31536000, immutable"


@router.get("/images/tmdb/{filename}")
async def proxy_tmdb_image(filename: str) -> Response:
    # Reject anything that doesn't match a TMDB filename. Defends against
    # path traversal (../../etc/passwd), URL-encoded slashes, etc.
    if not _PATH_RE.match(filename):
        raise HTTPException(status_code=400, detail="Invalid image path")

    cache_root = Path(settings.image_cache_path) / "w185"
    cache_path = cache_root / filename

    content_type = _CONTENT_TYPE_BY_SUFFIX[Path(filename).suffix.lower()]

    if cache_path.exists():
        return FileResponse(
            cache_path,
            media_type=content_type,
            headers={"Cache-Control": _CACHE_CONTROL, "X-Cache": "HIT"},
        )

    upstream_url = f"{_TMDB_BASE}/{filename}"
    try:
        async with httpx.AsyncClient(timeout=_FETCH_TIMEOUT_S, follow_redirects=True) as client:
            resp = await client.get(upstream_url)
    except Exception as e:
        log.warning("tmdb_image_fetch_failed", filename=filename, error=str(e))
        raise HTTPException(status_code=502, detail="Upstream TMDb fetch failed")

    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail="Image not found on TMDb")
    if resp.status_code >= 400:
        log.warning("tmdb_image_bad_status", filename=filename, status=resp.status_code)
        raise HTTPException(status_code=502, detail="Upstream TMDb error")

    # Atomic write: temp file → rename. Avoids serving a half-written file to a
    # second request that lands between content arrival and disk flush.
    cache_root.mkdir(parents=True, exist_ok=True)
    tmp_path = cache_path.with_suffix(cache_path.suffix + ".tmp")
    tmp_path.write_bytes(resp.content)
    tmp_path.rename(cache_path)

    log.info("tmdb_image_cached", filename=filename, bytes=len(resp.content))
    return Response(
        content=resp.content,
        media_type=content_type,
        headers={"Cache-Control": _CACHE_CONTROL, "X-Cache": "MISS"},
    )
