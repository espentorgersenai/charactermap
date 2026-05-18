"""Post-LLM enrichment: populate Character.actor (fuzzy-matched against TMDB
credits) and CharacterMap.creator (director from TMDB, author from OpenLibrary).

Enrichment is best-effort: any failure here must not fail the job. Unmatched
characters keep actor=None and the frontend falls back to initials.
"""
import re
from difflib import SequenceMatcher
from typing import Optional

from app.metadata.tmdb import TMDB_HEADSHOT_BASE, CastMember, DirectorCredit
from app.models.character_map import ActorInfo, Character, CharacterMap, CreatorInfo

# Honorific/title prefixes stripped before fuzzy comparison
_HONORIFIC_RE = re.compile(
    r"^(mr|mrs|ms|miss|dr|prof|professor|sir|lady|lord|"
    r"king|queen|prince|princess|capt|captain|sgt|lt|col|gen)"
    r"\.?\s+",
    re.IGNORECASE,
)
_PARENS_RE = re.compile(r"\([^)]*\)")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9\s]")
_LEADING_ARTICLE_RE = re.compile(r"^(the|a|an)\s+")

# Threshold for a confident character-name match. Tuned conservatively — false
# positives are worse than missing-but-still-rendered initials.
MATCH_THRESHOLD = 0.65

# Token-level matching needs a minimum token length to avoid catching tiny
# common tokens (e.g. credit "Old Man" matching every character named "Old").
_MIN_TOKEN_LEN = 4
# Token-only matches are discounted relative to a full-string match, because
# matching one token out of many is weaker evidence than matching the whole
# name. Discount tuned so "Winston Wolfe" ↔ "The Wolf" still clears threshold
# (token ratio 0.89 × 0.85 = 0.76) but two-letter accidental hits don't.
_TOKEN_DISCOUNT = 0.85


def _normalize(s: str) -> str:
    s = s.lower()
    s = _HONORIFIC_RE.sub("", s)
    s = _PARENS_RE.sub("", s)
    s = _NON_ALNUM_RE.sub("", s)
    s = " ".join(s.split())
    # Strip a leading article ("The Wolf" → "wolf", "An Education" → "education")
    s = _LEADING_ARTICLE_RE.sub("", s)
    return s


def _ratio(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def _best_token_ratio(a: str, b: str) -> float:
    """Best pairwise SequenceMatcher ratio between any token in a and any in b,
    ignoring tokens shorter than _MIN_TOKEN_LEN. Lets short surnames /
    nicknames match when the full-string ratio drowns in surrounding chrome."""
    a_tokens = [t for t in a.split() if len(t) >= _MIN_TOKEN_LEN]
    b_tokens = [t for t in b.split() if len(t) >= _MIN_TOKEN_LEN]
    if not a_tokens or not b_tokens:
        return 0.0
    return max(_ratio(at, bt) for at in a_tokens for bt in b_tokens)


def _score(char_name: str, cast: CastMember) -> float:
    """Score how well a CastMember matches an LLM character name.

    Three signals, take the strongest:
    1. Full-string ratio against the credited character name (highest fidelity).
    2. Best per-token ratio against the credited character name, discounted —
       catches cases where TMDB credits a name fragment ("The Wolf") vs the
       LLM's full name ("Winston Wolfe").
    3. Actor's real-life name, halved (weakest — used for cases where the
       LLM only knows the actor, e.g. archival footage).
    """
    nname = _normalize(char_name)
    n_credit = _normalize(cast.character)
    n_actor = _normalize(cast.name)
    return max(
        _ratio(nname, n_credit),
        _best_token_ratio(nname, n_credit) * _TOKEN_DISCOUNT,
        _ratio(nname, n_actor) * 0.5,
    )


def match_cast_to_characters(
    characters: list[Character],
    cast: list[CastMember],
    threshold: float = MATCH_THRESHOLD,
) -> int:
    """Mutate characters in place, setting `.actor` for confident matches.

    Greedy assignment: each character picks its best unused cast member; cast
    members assigned to one character can't match another. Returns the count
    of characters that got an actor.
    """
    if not cast:
        return 0
    used_person_ids: set[int] = set()
    matched = 0
    for char in characters:
        if char.actor is not None:
            continue
        best: Optional[tuple[float, CastMember]] = None
        for member in cast:
            if member.tmdb_person_id in used_person_ids:
                continue
            score = _score(char.name, member)
            if score >= threshold and (best is None or score > best[0]):
                best = (score, member)
        if best is not None:
            _, member = best
            char.actor = ActorInfo(
                name=member.name,
                tmdb_person_id=member.tmdb_person_id,
                headshot_url=(
                    f"{TMDB_HEADSHOT_BASE}{member.profile_path}"
                    if member.profile_path else None
                ),
            )
            # TMDB wins the naming discussion: when a confident match exists,
            # adopt TMDB's credited character name (e.g. "Winston Wolfe" →
            # "The Wolf"). LLM name is lost, but: relationships reference
            # by id (safe), markdown/PDF reads the same field, and the
            # credit is the audience-facing name on the work itself.
            if member.character:
                char.name = member.character
            used_person_ids.add(member.tmdb_person_id)
            matched += 1
    return matched


def set_creator(
    char_map: CharacterMap,
    work_type: str,
    author_name: Optional[str],
    director: Optional[DirectorCredit],
) -> None:
    """Populate char_map.creator based on work_type.

    book   → author from OpenLibrary metadata (no TMDB person id available)
    film_tv → director from TMDB credits
    """
    if work_type == "book" and author_name:
        char_map.creator = CreatorInfo(kind="author", name=author_name)
    elif work_type == "film_tv" and director is not None:
        char_map.creator = CreatorInfo(
            kind="director",
            name=director.name,
            tmdb_person_id=director.tmdb_person_id,
            headshot_url=(
                f"{TMDB_HEADSHOT_BASE}{director.profile_path}"
                if director.profile_path else None
            ),
        )
