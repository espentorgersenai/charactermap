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


def test_bayesian_caps_at_1():
    score = _bayesian_score(vote_average=10.0, vote_count=10000)
    assert score == 10.0 * 1.0  # min(1, 10000/50) = 1.0


def test_bayesian_zero_votes():
    score = _bayesian_score(vote_average=8.0, vote_count=0)
    assert score == 0.0
