import pytest
from app.renderers.markdown import render_markdown
from app.models.character_map import (
    ActorInfo, CharacterMap, Character, CreatorInfo, Faction, Relationship,
)

FIXTURE = CharacterMap(
    title="Congo",
    subtitle="Michael Crichton, 1980",
    blurb="An expedition into the Congo Basin.",
    spoiler_mode="full",
    factions=[
        Faction(id="erts", label="ERTS Expedition", description="The primary team.", color_hint="blue"),
    ],
    characters=[
        Character(
            id="peter",
            name="Peter Elliot",
            role="Primatologist",
            description="A UC Berkeley professor.",
            faction_id="erts",
            importance="protagonist",
            is_deceased_in_work=False,
            spoiler_level=0,
        ),
        Character(
            id="travis",
            name="R. B. Travis",
            role="CEO",
            description="Antagonist, <script>alert('xss')</script> greedy.",
            faction_id="erts",
            importance="major",
            is_deceased_in_work=True,
            spoiler_level=3,
        ),
    ],
    relationships=[
        Relationship(from_id="peter", to_id="travis", type="antagonism", label="rivals", spoiler_level=2),
    ],
    notes="Full-spoiler map.",
)


def test_title_present():
    md = render_markdown(FIXTURE)
    assert "# Congo" in md


def test_faction_section_present():
    md = render_markdown(FIXTURE)
    assert "## ERTS Expedition" in md


def test_character_name_present():
    md = render_markdown(FIXTURE)
    assert "Peter Elliot" in md


def test_deceased_marker():
    md = render_markdown(FIXTURE)
    assert "R. B. Travis †" in md or "R. B. Travis" in md


def test_relationships_table_present():
    md = render_markdown(FIXTURE)
    assert "## Relationships" in md
    assert "antagonism" in md


def test_bleach_strips_script_tags():
    md = render_markdown(FIXTURE)
    assert "<script>" not in md
    assert "alert('xss')" in md


def test_coverage_note_present():
    cm = FIXTURE.model_copy(update={"coverage_note": "Cap forced exclusions."})
    md = render_markdown(cm)
    assert "Coverage note" in md
    assert "Cap forced exclusions." in md


def test_setting_preamble_present():
    cm = FIXTURE.model_copy(update={"setting_preamble": "The story takes place in the Congo."})
    md = render_markdown(cm)
    assert "## Setting" in md
    assert "The story takes place in the Congo." in md


def test_footer_present():
    md = render_markdown(FIXTURE)
    assert "full spoilers" in md.lower()


def test_no_tmdb_attribution_without_actors_or_director():
    md = render_markdown(FIXTURE)
    assert "TMDB API" not in md
    assert "TMDb" not in md


def test_character_with_actor_renders_played_by_and_image():
    cm = FIXTURE.model_copy(deep=True)
    cm.characters[0].actor = ActorInfo(
        name="Tim Curry",
        tmdb_person_id=2154,
        headshot_url="https://image.tmdb.org/t/p/w185/abc.jpg",
    )
    md = render_markdown(cm)
    assert "played by Tim Curry" in md
    assert "![Peter Elliot as played by Tim Curry](https://image.tmdb.org/t/p/w185/abc.jpg)" in md


def test_character_with_actor_but_no_headshot_omits_image():
    cm = FIXTURE.model_copy(deep=True)
    cm.characters[0].actor = ActorInfo(
        name="Tim Curry", tmdb_person_id=2154, headshot_url=None,
    )
    md = render_markdown(cm)
    assert "played by Tim Curry" in md
    assert "![Peter Elliot" not in md


def test_creator_author_line_present():
    cm = FIXTURE.model_copy(update={
        "creator": CreatorInfo(kind="author", name="Michael Crichton"),
    })
    md = render_markdown(cm)
    assert "**By:** Michael Crichton" in md


def test_creator_director_with_headshot_renders_image():
    cm = FIXTURE.model_copy(update={
        "creator": CreatorInfo(
            kind="director",
            name="Frank Marshall",
            tmdb_person_id=11,
            headshot_url="https://image.tmdb.org/t/p/w185/dir.jpg",
        ),
    })
    md = render_markdown(cm)
    assert "**Directed by:** ![Frank Marshall](https://image.tmdb.org/t/p/w185/dir.jpg) Frank Marshall" in md


def test_tmdb_attribution_when_actors_present():
    cm = FIXTURE.model_copy(deep=True)
    cm.characters[0].actor = ActorInfo(
        name="Tim Curry", tmdb_person_id=2154, headshot_url=None,
    )
    md = render_markdown(cm)
    assert "TMDB API" in md


def test_tmdb_attribution_when_director_creator_only():
    cm = FIXTURE.model_copy(update={
        "creator": CreatorInfo(kind="director", name="Frank Marshall", tmdb_person_id=11),
    })
    md = render_markdown(cm)
    assert "TMDB API" in md


def test_author_creator_alone_does_not_trigger_tmdb_attribution():
    cm = FIXTURE.model_copy(update={
        "creator": CreatorInfo(kind="author", name="Michael Crichton"),
    })
    md = render_markdown(cm)
    assert "TMDB API" not in md
