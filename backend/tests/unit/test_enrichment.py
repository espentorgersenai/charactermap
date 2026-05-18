"""Unit tests for app.metadata.enrichment — fuzzy cast matching and creator."""
from app.metadata.enrichment import match_cast_to_characters, set_creator
from app.metadata.tmdb import CastMember, DirectorCredit
from app.models.character_map import (
    ActorInfo,
    Character,
    CharacterMap,
    Faction,
)


def _char(id: str, name: str, actor: ActorInfo | None = None) -> Character:
    return Character(
        id=id,
        name=name,
        role="",
        description="",
        faction_id="f",
        importance="supporting",
        is_deceased_in_work=False,
        spoiler_level=0,
        actor=actor,
    )


def _cast(name: str, character: str, person_id: int, order: int = 0, profile: str | None = "/p.jpg") -> CastMember:
    return CastMember(
        name=name,
        character=character,
        tmdb_person_id=person_id,
        profile_path=profile,
        order=order,
    )


def _map(characters: list[Character]) -> CharacterMap:
    return CharacterMap(
        title="T", subtitle="", blurb="", spoiler_mode="full",
        factions=[Faction(id="f", label="F", description="", color_hint="slate")],
        characters=characters, relationships=[], notes="",
    )


# ── match_cast_to_characters ───────────────────────────────────────────────
class TestMatchCastToCharacters:
    def test_empty_cast_matches_nothing(self):
        chars = [_char("c1", "Alice")]
        matched = match_cast_to_characters(chars, [])
        assert matched == 0
        assert chars[0].actor is None

    def test_exact_character_name_match(self):
        chars = [_char("c1", "Indiana Jones")]
        cast = [_cast("Harrison Ford", "Indiana Jones", 99)]
        matched = match_cast_to_characters(chars, cast)
        assert matched == 1
        assert chars[0].actor is not None
        assert chars[0].actor.tmdb_person_id == 99
        assert chars[0].actor.name == "Harrison Ford"
        assert chars[0].actor.headshot_url == "https://image.tmdb.org/t/p/w185/p.jpg"

    def test_strips_honorifics(self):
        chars = [_char("c1", "Dr. Strange")]
        cast = [_cast("Benedict Cumberbatch", "Stephen Strange", 1),
                _cast("Other", "Strange", 2)]
        # "Strange" matches better than "Stephen Strange"
        matched = match_cast_to_characters(chars, cast)
        assert matched == 1
        assert chars[0].actor.tmdb_person_id == 2

    def test_below_threshold_no_match(self):
        chars = [_char("c1", "Bilbo Baggins")]
        cast = [_cast("Someone", "Darth Vader", 42)]
        matched = match_cast_to_characters(chars, cast)
        assert matched == 0
        assert chars[0].actor is None

    def test_each_cast_member_used_at_most_once(self):
        # Two characters with similar names; one cast member.
        chars = [_char("c1", "John Smith"), _char("c2", "John Smith Jr.")]
        cast = [_cast("Actor", "John Smith", 7)]
        matched = match_cast_to_characters(chars, cast)
        assert matched == 1
        # First character grabs the only match; the second stays empty.
        assert chars[0].actor is not None
        assert chars[1].actor is None

    def test_preserves_existing_actor(self):
        prefilled = ActorInfo(name="Manual", tmdb_person_id=1, headshot_url=None)
        chars = [_char("c1", "Alice", actor=prefilled)]
        cast = [_cast("Other", "Alice", 99)]
        match_cast_to_characters(chars, cast)
        assert chars[0].actor.tmdb_person_id == 1  # unchanged

    def test_profile_path_none_yields_null_headshot(self):
        chars = [_char("c1", "Frodo Baggins")]
        cast = [_cast("Elijah Wood", "Frodo Baggins", 5, profile=None)]
        match_cast_to_characters(chars, cast)
        assert chars[0].actor is not None
        assert chars[0].actor.headshot_url is None

    def test_picks_best_score_when_multiple_above_threshold(self):
        chars = [_char("c1", "Captain Jack Sparrow")]
        cast = [
            _cast("Wrong", "Jack", 1),  # weaker match
            _cast("Johnny Depp", "Captain Jack Sparrow", 2),  # exact
        ]
        match_cast_to_characters(chars, cast)
        assert chars[0].actor.tmdb_person_id == 2

    def test_parenthetical_in_credit_is_ignored(self):
        chars = [_char("c1", "Hermione Granger")]
        # TMDB sometimes writes "Hermione Granger (younger)" for child actors
        cast = [_cast("Emma Watson", "Hermione Granger (older)", 11)]
        match_cast_to_characters(chars, cast)
        assert chars[0].actor.tmdb_person_id == 11


# ── set_creator ────────────────────────────────────────────────────────────
class TestSetCreator:
    def test_book_with_author(self):
        m = _map([_char("c1", "x")])
        set_creator(m, "book", "Michael Crichton", None)
        assert m.creator is not None
        assert m.creator.kind == "author"
        assert m.creator.name == "Michael Crichton"
        assert m.creator.tmdb_person_id is None

    def test_book_without_author(self):
        m = _map([_char("c1", "x")])
        set_creator(m, "book", None, None)
        assert m.creator is None

    def test_film_with_director(self):
        m = _map([_char("c1", "x")])
        d = DirectorCredit(name="Steven Spielberg", tmdb_person_id=42)
        set_creator(m, "film_tv", None, d)
        assert m.creator.kind == "director"
        assert m.creator.name == "Steven Spielberg"
        assert m.creator.tmdb_person_id == 42

    def test_film_without_director(self):
        m = _map([_char("c1", "x")])
        set_creator(m, "film_tv", "ignored", None)
        assert m.creator is None  # film/tv doesn't fall back to author
