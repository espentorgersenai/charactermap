import pytest
from app.renderers.markdown import render_markdown
from app.models.character_map import (
    CharacterMap, Character, Faction, Relationship,
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
