import json
from dataclasses import dataclass
from typing import Literal, Optional

import httpx

from app.config import settings
from app.metadata.confidence import compute_confidence, extract_year_from_query
from app.models.api import AdaptationInfo, ResolveCandidate, SeasonInfo

TMDB_BASE = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w300"
TMDB_HEADSHOT_BASE = "https://image.tmdb.org/t/p/w185"


@dataclass
class CastMember:
    name: str
    character: str  # character name as credited
    tmdb_person_id: int
    profile_path: Optional[str]
    order: int


@dataclass
class DirectorCredit:
    name: str
    tmdb_person_id: int
    profile_path: Optional[str] = None


async def _tmdb_get(path: str, params: dict = None, redis_client=None) -> dict:
    cache_key = f"tmdb:{path}:{str(sorted((params or {}).items()))}"

    if redis_client:
        cached = await redis_client.get(cache_key)
        if cached:
            return json.loads(cached)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{TMDB_BASE}{path}",
                params={"api_key": settings.tmdb_api_key, **(params or {})},
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as e:
        # 4xx (malformed query, bad id) and 5xx (TMDb outage) both surface as
        # "no results" to the user. Don't blow up the resolve route.
        import structlog
        structlog.get_logger().info(
            "tmdb_request_failed", path=path, status=e.response.status_code,
        )
        return {}
    except (httpx.RequestError, json.JSONDecodeError):
        import structlog
        structlog.get_logger().info("tmdb_request_error", path=path)
        return {}

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
        media_type = r.get("media_type") if r.get("media_type") in ("movie", "tv") else None

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
                director=None,  # populated post-LLM via get_credits
                cover_url=poster_url,
                confidence_score=confidence,
                media_type=media_type,
            )
        )

    return sorted(candidates, key=lambda c: c.confidence_score, reverse=True)


async def get_tv_seasons(tmdb_id: int, redis_client=None) -> list[SeasonInfo]:
    """Fetch the season list for a TV series. Season 0 (specials) is excluded.

    Returns [] on any TMDB failure or for non-TV ids — callers treat seasons
    as best-effort; an empty list just means the dropdown won't appear."""
    if not settings.tmdb_api_key:
        return []
    try:
        data = await _tmdb_get(f"/tv/{tmdb_id}", None, redis_client)
    except Exception:
        return []
    out: list[SeasonInfo] = []
    for s in data.get("seasons", []) or []:
        n = s.get("season_number")
        if n is None or n == 0:
            continue  # skip specials/extras
        air = s.get("air_date") or ""
        year = int(air[:4]) if air and len(air) >= 4 else None
        out.append(SeasonInfo(
            number=int(n),
            name=s.get("name") or f"Season {n}",
            year=year,
            episode_count=s.get("episode_count"),
        ))
    out.sort(key=lambda s: s.number)
    return out


async def fetch_season_cast(
    tmdb_id: int, season_number: int, redis_client=None, cast_limit: int = 80
) -> list[CastMember]:
    """Fetch credits for a specific TV season. Returns [] on failure.

    Uses /tv/{id}/season/{n}/credits which returns the season's cast in the
    same shape as /credits (single character per entry). Used when the user
    pins generation to a specific season — narrows the candidate pool versus
    aggregate_credits' union across all seasons."""
    if not settings.tmdb_api_key:
        return []
    try:
        data = await _tmdb_get(
            f"/tv/{tmdb_id}/season/{season_number}/credits", None, redis_client
        )
    except Exception:
        return []
    return _parse_cast(data, cast_limit)


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
    media_type = best.get("media_type") if best.get("media_type") in ("movie", "tv") else None

    return AdaptationInfo(
        tmdb_id=best["id"],
        title=adapt_title,
        year=adapt_year,
        rating=best.get("vote_average"),
        poster_url=poster_url,
        media_type=media_type,
    )


def _parse_cast(data: dict, cast_limit: int) -> list[CastMember]:
    """Shared cast parser used by best-effort get_credits and strict fetch_cast.

    Handles both shapes:
      - /credits (movies + TV main-cast): each entry has a single `character`
      - /aggregate_credits (TV, all seasons): each entry has `roles: [{character, ...}]`
        — one actor can play multiple characters across seasons. We flatten so
        each (actor, character) pair is a separate CastMember; fuzzy matching
        then has each role independently scorable.
    """
    out: list[CastMember] = []
    for c in sorted(data.get("cast", []), key=lambda c: c.get("order", 9999)):
        if not (c.get("id") and c.get("name")):
            continue
        roles = c.get("roles")
        if roles:
            for r in roles:
                out.append(CastMember(
                    name=c.get("name", ""),
                    character=r.get("character", ""),
                    tmdb_person_id=int(c["id"]),
                    profile_path=c.get("profile_path"),
                    order=int(c.get("order", 9999)),
                ))
        else:
            out.append(CastMember(
                name=c.get("name", ""),
                character=c.get("character", ""),
                tmdb_person_id=int(c["id"]),
                profile_path=c.get("profile_path"),
                order=int(c.get("order", 9999)),
            ))
    return out[:cast_limit]


async def fetch_cast_strict(
    tmdb_id: int,
    media_type: Literal["movie", "tv"],
    redis_client=None,
    cast_limit: int = 30,
) -> list[CastMember]:
    """Fetch cast for a TMDB work, raising on failure.

    Unlike get_credits (best-effort, swallows errors for post-LLM enrichment),
    this raises httpx/RuntimeError on TMDB failure so the API layer can
    surface a 503 to the caller. Returns an empty list only when TMDB
    genuinely has no cast credits."""
    if not settings.tmdb_api_key:
        raise RuntimeError("TMDB API key not configured")
    # See get_credits — TV needs aggregate_credits for full-series coverage.
    credits_path = (
        f"/tv/{tmdb_id}/aggregate_credits" if media_type == "tv"
        else f"/movie/{tmdb_id}/credits"
    )
    data = await _tmdb_get(credits_path, None, redis_client)
    return _parse_cast(data, cast_limit)


def _merge_casts(casts: list[list[CastMember]], cast_limit: int) -> list[CastMember]:
    """Merge cast lists from multiple films, dedupe by tmdb_person_id keeping
    the entry with the LOWEST billing order (more prominent role wins). Cap
    output to cast_limit."""
    by_person: dict[int, CastMember] = {}
    for cast in casts:
        for member in cast:
            existing = by_person.get(member.tmdb_person_id)
            if existing is None or member.order < existing.order:
                by_person[member.tmdb_person_id] = member
    return sorted(by_person.values(), key=lambda m: m.order)[:cast_limit]


async def fetch_collection_cast(
    tmdb_id: int,
    media_type: Literal["movie", "tv"],
    redis_client=None,
    cast_limit: int = 30,
) -> list[CastMember]:
    """Aggregate cast across all films in a collection (Hobbit, LOTR, etc).

    For TV: no collection concept, returns this work's cast unchanged.
    For movies not in a collection: returns this work's cast unchanged.
    For movies in a collection: fetches each part's credits and merges via
    `_merge_casts` (dedupe by person, lowest order wins). Catches sibling-
    film failures individually — one bad part shouldn't break the rest.

    Best-effort: returns [] on TMDB failure (matching get_credits semantics)."""
    if not settings.tmdb_api_key:
        return []
    if media_type != "movie":
        return await _fetch_single_cast_safe(tmdb_id, media_type, redis_client, cast_limit)

    try:
        details = await _tmdb_get(f"/movie/{tmdb_id}", None, redis_client)
    except Exception:
        return []

    collection = details.get("belongs_to_collection")
    if not collection or not collection.get("id"):
        return await _fetch_single_cast_safe(tmdb_id, media_type, redis_client, cast_limit)

    try:
        coll_data = await _tmdb_get(f"/collection/{collection['id']}", None, redis_client)
    except Exception:
        return await _fetch_single_cast_safe(tmdb_id, media_type, redis_client, cast_limit)

    part_ids = [p["id"] for p in coll_data.get("parts", []) if p.get("id")]
    if not part_ids:
        return await _fetch_single_cast_safe(tmdb_id, media_type, redis_client, cast_limit)

    # Per-part fetch is best-effort and individually error-handled. We over-
    # fetch (cast_limit per part) so the merge has room to keep the best of
    # each, then cap at cast_limit at the end.
    per_part_limit = cast_limit
    casts: list[list[CastMember]] = []
    for pid in part_ids:
        part_cast = await _fetch_single_cast_safe(pid, "movie", redis_client, per_part_limit)
        if part_cast:
            casts.append(part_cast)

    return _merge_casts(casts, cast_limit) if casts else []


async def _fetch_single_cast_safe(
    tmdb_id: int,
    media_type: Literal["movie", "tv"],
    redis_client,
    cast_limit: int,
) -> list[CastMember]:
    """Internal: swallow-errors single-film cast (used by collection aggregator
    so one bad sibling doesn't break the rest)."""
    try:
        data = await _tmdb_get(f"/{media_type}/{tmdb_id}/credits", None, redis_client)
    except Exception:
        return []
    return _parse_cast(data, cast_limit)


async def get_credits(
    tmdb_id: int,
    media_type: Literal["movie", "tv"],
    redis_client=None,
    cast_limit: int = 80,
    aggregate_collection: bool = False,
    season: int | None = None,
) -> tuple[list[CastMember], Optional[DirectorCredit]]:
    """Fetch top-N cast (by billing order) and the director credit for a TMDB work.

    Returns ([], None) on any failure — callers must treat enrichment as best-effort.

    When aggregate_collection=True and the work is a movie in a collection
    (e.g. Hobbit trilogy), cast is merged across all parts so characters
    that only appear in sibling films (Gollum from Unexpected Journey, Eagles
    in Return of the King, etc.) still get matched. The director credit always
    comes from the originally-requested film (Peter Jackson for Hobbit 2 ≠
    Hobbit 1's director, but for our adaptation lookup the requested film's
    director is what matters)."""
    if not settings.tmdb_api_key:
        return [], None
    # TV /credits only returns the current main cast (often biased toward the
    # latest season). For shows like The Night Manager where seasons 1 and 2
    # have nearly disjoint casts, aggregate_credits returns the union across
    # all seasons + each actor's full role list. Movies don't have seasons so
    # /credits is the right call there.
    # When the user pins to a specific season, /tv/{id}/season/{n}/credits is
    # narrower than aggregate_credits — cast list = that season only.
    if media_type == "tv" and season is not None:
        credits_path = f"/tv/{tmdb_id}/season/{season}/credits"
    elif media_type == "tv":
        credits_path = f"/tv/{tmdb_id}/aggregate_credits"
    else:
        credits_path = f"/movie/{tmdb_id}/credits"
    try:
        data = await _tmdb_get(credits_path, None, redis_client)
    except Exception:
        return [], None

    if aggregate_collection and media_type == "movie":
        cast = await fetch_collection_cast(tmdb_id, media_type, redis_client, cast_limit)
        # fetch_collection_cast falls back to single-film cast when there's
        # no collection — so this never strictly worsens coverage.
    else:
        cast = _parse_cast(data, cast_limit)

    # Director: for movies, crew[].job == 'Director'; for TV the analogous is
    # 'Creator' (showrunner), but TV results may have many — take the first.
    director: Optional[DirectorCredit] = None
    crew = data.get("crew", [])
    if media_type == "movie":
        for member in crew:
            if member.get("job") == "Director" and member.get("id"):
                director = DirectorCredit(
                    name=member.get("name", ""),
                    tmdb_person_id=int(member["id"]),
                    profile_path=member.get("profile_path"),
                )
                break
    else:  # tv — fall back to created_by on the main resource if no crew director
        # The credits payload includes only episode crew, so a Creator search is
        # unreliable; expose nothing rather than wrong.
        director = None

    return cast, director
