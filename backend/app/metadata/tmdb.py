import json

import httpx

from app.config import settings
from app.metadata.confidence import compute_confidence, extract_year_from_query
from app.models.api import AdaptationInfo, ResolveCandidate

TMDB_BASE = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w300"


async def _tmdb_get(path: str, params: dict = None, redis_client=None) -> dict:
    cache_key = f"tmdb:{path}:{str(sorted((params or {}).items()))}"

    if redis_client:
        cached = await redis_client.get(cache_key)
        if cached:
            return json.loads(cached)

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{TMDB_BASE}{path}",
            params={"api_key": settings.tmdb_api_key, **(params or {})},
        )
        resp.raise_for_status()
        data = resp.json()

    if redis_client:
        await redis_client.setex(cache_key, 7 * 24 * 3600, json.dumps(data))

    return data


def _bayesian_score(vote_average: float, vote_count: int) -> float:
    """Pick highest-rated adaptation per §9.3: vote_average × min(1, vote_count/50)."""
    return vote_average * min(1.0, vote_count / 50)


async def search_film_tv(query: str, redis_client=None) -> list[ResolveCandidate]:
    """Search TMDb for film/TV works. Returns candidates with confidence scores."""
    query_year = extract_year_from_query(query)
    data = await _tmdb_get(
        "/search/multi", {"query": query, "include_adult": "false"}, redis_client
    )
    results = [r for r in data.get("results", []) if r.get("media_type") in ("movie", "tv")][:5]
    is_single = len(results) == 1

    candidates = []
    for r in results:
        title = r.get("title") or r.get("name", "")
        year_str = r.get("release_date") or r.get("first_air_date") or ""
        year = int(year_str[:4]) if year_str and len(year_str) >= 4 else None
        poster_path = r.get("poster_path")
        poster_url = f"{TMDB_IMAGE_BASE}{poster_path}" if poster_path else None
        vote_count = r.get("vote_count", 0)

        confidence = compute_confidence(
            query=query,
            candidate_title=title,
            is_single_result=is_single,
            popularity_count=vote_count,
            candidate_year=year,
            query_year=query_year,
        )

        candidates.append(
            ResolveCandidate(
                source="tmdb",
                id=str(r["id"]),
                title=title,
                year=year,
                director=None,  # omit for now; full credits lookup is Phase 4
                cover_url=poster_url,
                confidence_score=confidence,
            )
        )

    return sorted(candidates, key=lambda c: c.confidence_score, reverse=True)


async def find_adaptation_for_book(
    title: str,
    year: int | None,
    redis_client=None,
) -> AdaptationInfo | None:
    """Given a book title+year, find its highest-rated TMDb adaptation."""
    if not settings.tmdb_api_key:
        return None

    try:
        data = await _tmdb_get(
            "/search/multi", {"query": title, "include_adult": "false"}, redis_client
        )
    except Exception:
        return None

    results = [r for r in data.get("results", []) if r.get("media_type") in ("movie", "tv")]
    if not results:
        return None

    # Pick the best by Bayesian score
    best = max(
        results,
        key=lambda r: _bayesian_score(r.get("vote_average", 0), r.get("vote_count", 0)),
    )

    adapt_title = best.get("title") or best.get("name", "")
    year_str = best.get("release_date") or best.get("first_air_date") or ""
    adapt_year = int(year_str[:4]) if year_str and len(year_str) >= 4 else None
    poster_path = best.get("poster_path")
    poster_url = f"{TMDB_IMAGE_BASE}{poster_path}" if poster_path else None

    return AdaptationInfo(
        tmdb_id=best["id"],
        title=adapt_title,
        year=adapt_year,
        rating=best.get("vote_average"),
        poster_url=poster_url,
    )
