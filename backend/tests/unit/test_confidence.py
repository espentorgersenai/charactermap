import pytest

from app.metadata.confidence import compute_confidence, extract_year_from_query


def test_single_result_boost():
    score = compute_confidence(
        "Congo",
        "Congo",
        is_single_result=True,
        popularity_count=100,
        candidate_year=1980,
        query_year=None,
    )
    assert score >= 0.7  # single result + perfect title match


def test_multi_result_no_boost():
    score = compute_confidence(
        "Congo",
        "Congo",
        is_single_result=False,
        popularity_count=100,
        candidate_year=1980,
        query_year=None,
    )
    assert score < 0.9


def test_year_match_boost():
    # Same title sim; only difference is query_year being present and matching.
    score_with = compute_confidence(
        "Dune",
        "Dune",
        is_single_result=False,
        popularity_count=500,
        candidate_year=1965,
        query_year=1965,
    )
    score_without = compute_confidence(
        "Dune",
        "Dune",
        is_single_result=False,
        popularity_count=500,
        candidate_year=1965,
        query_year=None,
    )
    assert score_with > score_without


def test_zero_results_returns_empty_candidates():
    from app.metadata.openlibrary import parse_ol_candidates

    candidates = parse_ol_candidates([], "Unknown Work XYZ")
    assert candidates == []


def test_extract_year_from_query():
    assert extract_year_from_query("Dune 1965") == 1965
    assert extract_year_from_query("Congo") is None
    assert extract_year_from_query("Pride and Prejudice 1813") == 1813


def test_low_popularity_reduces_score():
    score_high = compute_confidence(
        "Dune",
        "Dune",
        is_single_result=False,
        popularity_count=500,
        candidate_year=None,
        query_year=None,
    )
    score_low = compute_confidence(
        "Dune",
        "Dune",
        is_single_result=False,
        popularity_count=1,
        candidate_year=None,
        query_year=None,
    )
    assert score_high > score_low
