from typing import Literal, Optional
from pydantic import BaseModel


class Faction(BaseModel):
    id: str
    label: str
    description: str
    color_hint: Literal["blue", "red", "green", "amber", "violet", "slate"]


class ActorInfo(BaseModel):
    name: str
    tmdb_person_id: int
    headshot_url: str


class Character(BaseModel):
    id: str
    name: str
    role: str
    description: str
    faction_id: Optional[str]
    importance: Literal["protagonist", "major", "supporting", "minor"]
    is_deceased_in_work: bool
    # Optional so pipeline can detect and default missing values to 3
    spoiler_level: Optional[Literal[0, 1, 2, 3]] = None
    actor: Optional[ActorInfo] = None


class Relationship(BaseModel):
    from_id: str
    to_id: str
    type: Literal[
        "alliance", "family", "romantic", "antagonism",
        "professional", "mentorship", "criminal",
    ]
    label: str
    # Optional so pipeline can detect and default missing values to 3
    spoiler_level: Optional[Literal[0, 1, 2, 3]] = None


class CharacterMap(BaseModel):
    title: str
    subtitle: str
    blurb: str
    spoiler_mode: Literal["full"]
    setting_preamble: Optional[str] = None
    factions: list[Faction]
    characters: list[Character]
    relationships: list[Relationship]
    coverage_note: Optional[str] = None
    notes: str


class RefusalResponse(BaseModel):
    refusal: str
