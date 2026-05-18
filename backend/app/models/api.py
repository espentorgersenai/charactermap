from typing import Optional

from pydantic import BaseModel


class ResolveRequest(BaseModel):
    query: str
    work_type: str  # "book" or "film_tv"


class AdaptationInfo(BaseModel):
    tmdb_id: int
    title: str
    year: Optional[int]
    rating: Optional[float]
    poster_url: Optional[str]


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


class ResolveResponse(BaseModel):
    candidates: list[ResolveCandidate]
