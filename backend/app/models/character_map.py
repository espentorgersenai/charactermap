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
    headshot_url: Optional[str] = None  # null when TMDB has no profile photo


class CreatorInfo(BaseModel):
    # 'author' for books, 'director' for film/tv. Populated post-LLM from
    # OpenLibrary (author name only) or TMDB credits (director with person id).
    kind: Literal["author", "director"]
    name: str
    tmdb_person_id: Optional[int] = None
    headshot_url: Optional[str] = None


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
    # Short grounding phrase emitted by the LLM to ensure each name is tied to
    # a specific scene or relationship in the source. Optional during rollout.
    name_evidence: Optional[str] = None
    actor: Optional[ActorInfo] = None
    # Coarse geographic origin (region / city / holdfast) for geographic-view
    # rendering. Free-form string — the frontend resolves it against a per-work
    # region→coordinate table. None for works without a defined geography.
    home_region: Optional[str] = None
    # True only for narrative viewpoint (POV) characters — chapters/sections
    # told from their perspective (e.g. ASOIAF POV chapters). Populated by
    # Stage 2 from the analysis's Viewpoint section; default False.
    is_pov: bool = False


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
    # 1-2 sentence summary of substantive adaptation divergences (book vs film,
    # original vs remake). Populated by Stage 2 structuring when the Stage 1
    # analysis surfaces a "Key Adaptation Differences" section.
    adaptation_note: Optional[str] = None
    notes: str
    creator: Optional[CreatorInfo] = None
    # Deep link back to the source the work was resolved from
    # (TMDB movie/tv page or OpenLibrary work page). Populated post-LLM.
    source_url: Optional[str] = None


class RefusalResponse(BaseModel):
    refusal: str
