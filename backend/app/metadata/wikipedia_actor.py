"""Wikipedia-driven actor lookup, used as a fallback when TMDB fuzzy matching
leaves a character with no actor.

Strategy (cheap, no-key, best-effort):
  1. Ask the Wikipedia OpenSearch API for "<Character> (<Work>)" or
     "<Character>" — both forms produce a candidate page.
  2. Fetch the page's HTML extract via the REST summary endpoint, find a
     line of the form "portrayed by <Actor>" or "played by <Actor>".
  3. If we got an actor name, hand it back to TMDB's /search/person to
     pick up the canonical headshot.

Returns an ActorInfo or None. Every step is wrapped in try/except — this is
strictly best-effort and must never fail a job.
"""
from __future__ import annotations

import re
from typing import Optional

import httpx
import structlog

from app.config import settings
from app.metadata.tmdb import TMDB_BASE, TMDB_HEADSHOT_BASE
from app.models.character_map import ActorInfo

log = structlog.get_logger()

_WIKI_API = "https://en.wikipedia.org/w/api.php"
_PORTRAYED_RE = re.compile(
    r"(?:portrayed|played|voiced|depicted)\s+by\s+([A-Z][\w'\-\.]+(?:\s+[A-Z][\w'\-\.]+){0,3})",
    re.IGNORECASE,
)
_TIMEOUT_S = 8.0


async def _wiki_search_extract(query: str, client: httpx.AsyncClient) -> Optional[str]:
    """Return the plaintext extract of the top Wikipedia search hit, or None."""
    try:
        resp = await client.get(
            _WIKI_API,
            params={
                "action": "query",
                "format": "json",
                "generator": "search",
                "gsrsearch": query,
                "gsrlimit": "1",
                "prop": "extracts",
                "explaintext": "1",
                "exintro": "0",
                "exchars": "1500",
            },
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return None
    pages = (data.get("query") or {}).get("pages") or {}
    if not pages:
        return None
    page = next(iter(pages.values()))
    return page.get("extract")


def _extract_actor_name(text: str) -> Optional[str]:
    m = _PORTRAYED_RE.search(text)
    if not m:
        return None
    name = m.group(1).strip().rstrip(".,;:")
    # Sanity floor: actor names are at least two characters and contain a space
    # in the vast majority of cases. One-word matches are usually false positives
    # (e.g. "portrayed by Theatre").
    if len(name) < 3 or " " not in name:
        return None
    return name


async def _tmdb_person_lookup(
    actor_name: str, client: httpx.AsyncClient
) -> Optional[ActorInfo]:
    """Resolve an actor name to a TMDB ActorInfo via /search/person."""
    if not settings.tmdb_api_key:
        return None
    try:
        resp = await client.get(
            f"{TMDB_BASE}/search/person",
            params={"api_key": settings.tmdb_api_key, "query": actor_name},
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return None
    results = data.get("results") or []
    if not results:
        return None
    top = results[0]
    pid = top.get("id")
    if not pid:
        return None
    profile = top.get("profile_path")
    return ActorInfo(
        name=top.get("name") or actor_name,
        tmdb_person_id=int(pid),
        headshot_url=(f"{TMDB_HEADSHOT_BASE}{profile}" if profile else None),
    )


async def lookup_actor_via_wikipedia(
    character_name: str, work_title: str
) -> Optional[ActorInfo]:
    """Best-effort: find the actor for a character via Wikipedia, then TMDB.

    Tries the disambiguated query first ("Cersei Lannister Game of Thrones")
    then the bare character name. Returns ActorInfo with a TMDB headshot when
    everything aligns, or None when any step misses.
    """
    queries = [
        f"{character_name} {work_title}",
        f"{character_name}",
    ]
    async with httpx.AsyncClient(timeout=_TIMEOUT_S, follow_redirects=True) as client:
        for q in queries:
            extract = await _wiki_search_extract(q, client)
            if not extract:
                continue
            actor_name = _extract_actor_name(extract)
            if not actor_name:
                continue
            info = await _tmdb_person_lookup(actor_name, client)
            if info is not None:
                log.info(
                    "wiki_actor_resolved",
                    character=character_name,
                    actor=actor_name,
                    tmdb_person_id=info.tmdb_person_id,
                    query=q,
                )
                return info
    return None
