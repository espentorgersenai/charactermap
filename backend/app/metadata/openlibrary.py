import json

import httpx

from app.metadata.confidence import compute_confidence, extract_year_from_query
from app.models.api import ResolveCandidate

OL_SEARCH_URL = "https://openlibrary.org/search.json"
OL_COVER_URL = "https://covers.openlibrary.org/b/id/{cover_id}-M.jpg"


async def search_books(query: str, redis_client=None) -> list[dict]:
    """Search Open Library, return raw result dicts. Caches in Redis for 7 days."""
    cache_key = f"ol:search:{query.lower()}"

    if redis_client:
        cached = await redis_client.get(cache_key)
        if cached:
            return json.loads(cached)

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(OL_SEARCH_URL, params={"q": query, "limit": 5})
        resp.raise_for_status()
        data = resp.json()

    results = data.get("docs", [])

    if redis_client:
        await redis_client.setex(cache_key, 7 * 24 * 3600, json.dumps(results))

    return results


def parse_ol_candidates(
    raw_results: list[dict],
    query: str,
) -> list[ResolveCandidate]:
    """Parse raw OL search results into ResolveCandidate objects with confidence scores."""
    query_year = extract_year_from_query(query)
    is_single = len(raw_results) == 1

    candidates = []
    for doc in raw_results[:5]:
        title = doc.get("title", "")
        year = doc.get("first_publish_year")
        author = ", ".join(doc.get("author_name", [])[:2]) if doc.get("author_name") else None
        cover_id = doc.get("cover_i")
        cover_url = OL_COVER_URL.format(cover_id=cover_id) if cover_id else None
        edition_count = doc.get("edition_count", 0)
        work_id = doc.get("key", "").replace("/works/", "") or doc.get("cover_edition_key", "")

        confidence = compute_confidence(
            query=query,
            candidate_title=title,
            is_single_result=is_single,
            popularity_count=edition_count,
            candidate_year=year,
            query_year=query_year,
        )

        candidates.append(
            ResolveCandidate(
                source="openlibrary",
                id=work_id,
                title=title,
                year=year,
                author=author,
                cover_url=cover_url,
                confidence_score=confidence,
            )
        )

    return sorted(candidates, key=lambda c: c.confidence_score, reverse=True)
