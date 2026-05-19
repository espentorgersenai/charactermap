from typing import Literal, Optional

from pydantic import BaseModel


class ResolveRequest(BaseModel):
    query: str
    work_type: Literal["book", "film_tv"]


class SeasonInfo(BaseModel):
    number: int  # TMDB season_number; season 0 = specials, often skipped
    name: str  # e.g. "Season 2" or named seasons
    year: Optional[int] = None  # air_date year
    episode_count: Optional[int] = None


class AdaptationInfo(BaseModel):
    tmdb_id: int
    title: str
    year: Optional[int]
    rating: Optional[float]
    poster_url: Optional[str]
    media_type: Optional[Literal["movie", "tv"]] = None


class ResolveCandidate(BaseModel):
    source: str  # "openlibrary" or "tmdb"
    id: str  # Open Library work ID or TMDb id (as string)
    title: str
    year: Optional[int]
    author: Optional[str] = None  # for books
    director: Optional[str] = None  # for film_tv
    cover_url: Optional[str]
    confidence_score: float  # 0.0 to 1.0
    adaptation: Optional[AdaptationInfo] = None
    media_type: Optional[Literal["movie", "tv"]] = None  # for film_tv source
    # Populated only for media_type=='tv'. Excludes season 0 (specials).
    seasons: Optional[list[SeasonInfo]] = None


class ResolveResponse(BaseModel):
    candidates: list[ResolveCandidate]


class CastMemberPublic(BaseModel):
    tmdb_person_id: int
    name: str  # actor's real name
    character: str  # credited character name (may differ from LLM canonical)
    headshot_url: Optional[str] = None  # full TMDB URL; None when no profile photo
    order: int  # billing order, ascending


class AdaptationCastResponse(BaseModel):
    tmdb_id: int
    media_type: Literal["movie", "tv"]
    cast: list[CastMemberPublic]
