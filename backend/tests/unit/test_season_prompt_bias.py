"""When job.resolved_meta has a `season` key, all three prompt-render paths
(legacy single-call user message, grounded Stage 1 analysis, grounded Stage 2
structuring) must inject a <season_focus> block telling the model to scope to
that season only. Without season, the block must be absent."""
from unittest.mock import MagicMock

from app.worker.pipeline import (
    _render_analysis_user_message,
    _render_structuring_user_message,
    _render_user_message,
)


def _job(season=None, work_type="film_tv"):
    j = MagicMock()
    j.resolved_title = "The Night Manager"
    j.resolved_year = 2016
    j.work_type = work_type
    j.title_query = "Night Manager"
    j.resolved_meta = {"author": None, "director": None, "season": season}
    return j


def test_season_bias_present_in_user_message():
    msg = _render_user_message(_job(season=2))
    assert "<season_focus>" in msg
    assert "Season 2" in msg


def test_season_bias_present_in_analysis_message():
    msg = _render_analysis_user_message(_job(season=2))
    assert "<season_focus>" in msg
    assert "Season 2" in msg


def test_season_bias_present_in_structuring_message():
    msg = _render_structuring_user_message(_job(season=2), analysis="...prose...")
    assert "<season_focus>" in msg
    assert "Season 2" in msg


def test_no_season_bias_block_when_unset():
    msg = _render_user_message(_job(season=None))
    assert "<season_focus>" not in msg


def test_no_season_bias_block_when_zero():
    """Season 0 (specials) is treated the same as unset — we never pin to it."""
    msg = _render_user_message(_job(season=0))
    assert "<season_focus>" not in msg
