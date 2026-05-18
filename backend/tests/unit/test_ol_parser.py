import pytest

from app.metadata.openlibrary import parse_ol_candidates


OL_FIXTURE = [
    {
        "title": "Congo",
        "first_publish_year": 1980,
        "author_name": ["Michael Crichton"],
        "cover_i": 12345,
        "edition_count": 42,
        "key": "/works/OL12345W",
    }
]


def test_ol_parser_extracts_fields():
    candidates = parse_ol_candidates(OL_FIXTURE, "Congo")
    assert len(candidates) == 1
    c = candidates[0]
    assert c.title == "Congo"
    assert c.year == 1980
    assert c.author == "Michael Crichton"
    assert c.cover_url == "https://covers.openlibrary.org/b/id/12345-M.jpg"
    assert c.source == "openlibrary"
    assert c.confidence_score > 0


def test_ol_parser_handles_missing_cover():
    doc = dict(OL_FIXTURE[0])
    del doc["cover_i"]
    candidates = parse_ol_candidates([doc], "Congo")
    assert candidates[0].cover_url is None


def test_ol_parser_extracts_work_id():
    candidates = parse_ol_candidates(OL_FIXTURE, "Congo")
    assert candidates[0].id == "OL12345W"
