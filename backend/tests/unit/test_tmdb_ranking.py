import pytest

from app.metadata.tmdb import _bayesian_score


def test_bayesian_prefers_high_vote_average():
    score_good = _bayesian_score(vote_average=8.0, vote_count=100)
    score_bad = _bayesian_score(vote_average=4.0, vote_count=100)
    assert score_good > score_bad


def test_bayesian_discounts_low_vote_count():
    score_many = _bayesian_score(vote_average=7.0, vote_count=200)
    score_few = _bayesian_score(vote_average=7.0, vote_count=5)
    assert score_many > score_few


def test_bayesian_saturates_at_high_vote_count():
    # vote_count=10000 → min(1, 10000/50) = 1.0 → score = vote_average * 1.0
    score = _bayesian_score(vote_average=8.0, vote_count=10000)
    assert score == pytest.approx(8.0)


def test_bayesian_zero_votes():
    score = _bayesian_score(vote_average=8.0, vote_count=0)
    assert score == 0.0


def test_bayesian_selects_best_from_fixture_list():
    # Simulate three adaptations; the second has the best Bayesian score
    adaptations = [
        {"vote_average": 8.0, "vote_count": 10},    # score: 8.0 * min(1, 10/50) = 1.6
        {"vote_average": 7.0, "vote_count": 100},   # score: 7.0 * min(1, 100/50) = 7.0  <- best
        {"vote_average": 9.0, "vote_count": 2},     # score: 9.0 * min(1, 2/50) = 0.36
    ]
    best = max(adaptations, key=lambda r: _bayesian_score(r["vote_average"], r["vote_count"]))
    assert best["vote_average"] == 7.0
    assert best["vote_count"] == 100
