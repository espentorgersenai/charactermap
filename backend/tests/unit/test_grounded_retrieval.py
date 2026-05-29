from app.worker.pipeline import (
    _searches_for_cap,
    _max_tokens_for_cap,
    _load_analysis_prompt,
)


def test_searches_for_cap_scales_with_cap():
    assert _searches_for_cap(10) == 4
    assert _searches_for_cap(20) == 4
    assert _searches_for_cap(50) == 4
    assert _searches_for_cap(51) == 8   # boundary: first value above the ≤50 tier
    assert _searches_for_cap(100) == 8
    assert _searches_for_cap(101) == 12  # boundary: first value above the ≤100 tier
    assert _searches_for_cap(150) == 12


def test_max_tokens_for_cap_scales_with_cap():
    # Large rosters need a bigger Stage-2 output budget or the JSON truncates
    # mid-object (invalid_json). Ceiling only — cost-neutral when unused.
    assert _max_tokens_for_cap(20) == 16384
    assert _max_tokens_for_cap(50) == 16384
    assert _max_tokens_for_cap(51) == 32000   # boundary above the ≤50 tier
    assert _max_tokens_for_cap(100) == 32000
    assert _max_tokens_for_cap(101) == 48000  # boundary above the ≤100 tier
    assert _max_tokens_for_cap(150) == 48000


def test_analysis_prompt_is_cap_aware():
    # Must contain the {CHAR_CAP} placeholder so _render_system_prompt can
    # inject the target roster size into Stage 1.
    assert "{CHAR_CAP}" in _load_analysis_prompt()


def test_analysis_prompt_names_canonical_wiki_source():
    assert "awoiaf" in _load_analysis_prompt().lower()


def test_analysis_prompt_has_viewpoint_section():
    assert "Viewpoint" in _load_analysis_prompt()


def test_structuring_prompt_documents_is_pov():
    from app.worker.pipeline import _load_structuring_prompt
    text = _load_structuring_prompt()
    assert "is_pov" in text
    assert "Viewpoint" in text
