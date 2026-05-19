"""Side-by-side photo/text layout for PDF character blocks (no pandoc required)."""
from pathlib import Path

from app.renderers.pdf import _CHAR_BLOCK_RE, _latex_escape, _rewrite_character_blocks


def test_latex_escape_handles_special_chars():
    assert _latex_escape("100% of cast") == r"100\% of cast"
    assert _latex_escape("A & B") == r"A \& B"
    assert _latex_escape("under_score") == r"under\_score"
    # Backslash must escape first or we'd double-escape our own output.
    assert _latex_escape("a\\b") == r"a\textbackslash{}b"


def test_char_block_regex_matches_with_actor():
    md = (
        "**Tom Builder †** *(protagonist)* — played by Rufus Sewell\n"
        "\n"
        "![Tom Builder as played by Rufus Sewell](https://image.tmdb.org/x.jpg)\n"
        "\n"
        "Master builder and itinerant craftsman.\n"
        "\n"
    )
    m = _CHAR_BLOCK_RE.search(md)
    assert m is not None
    assert m.group("name").strip() == "Tom Builder †"
    assert m.group("importance") == "protagonist"
    assert "played by Rufus Sewell" in (m.group("actor_clause") or "")
    assert m.group("url") == "https://image.tmdb.org/x.jpg"
    assert m.group("desc").strip() == "Master builder and itinerant craftsman."


def test_char_block_regex_matches_without_actor():
    """Headshot present but no '— played by' clause (e.g. director-credit-only films)."""
    md = (
        "**Mystery Figure** *(supporting)*\n"
        "\n"
        "![alt](https://image.tmdb.org/y.jpg)\n"
        "\n"
        "Description here.\n"
        "\n"
    )
    m = _CHAR_BLOCK_RE.search(md)
    assert m is not None
    assert m.group("actor_clause") == ""


def test_char_block_regex_skips_blocks_without_image():
    """A character without a headshot stays in the default stacked layout."""
    md = (
        "**Some Character** *(minor)*\n"
        "\n"
        "Description without image.\n"
        "\n"
    )
    assert _CHAR_BLOCK_RE.search(md) is None


def test_rewrite_replaces_block_with_minipages(tmp_path):
    img = tmp_path / "rufus.jpg"
    img.write_bytes(b"")
    md = (
        "**Tom Builder** *(protagonist)* — played by Rufus Sewell\n"
        "\n"
        "![alt](https://image.tmdb.org/rufus.jpg)\n"
        "\n"
        "Master builder.\n"
        "\n"
    )
    out = _rewrite_character_blocks(md, {"https://image.tmdb.org/rufus.jpg": img})
    assert "\\begin{minipage}[t]{2.5cm}" in out
    assert f"\\includegraphics[width=\\linewidth]{{{img}}}" in out
    assert "\\textbf{Tom Builder}" in out
    assert "\\textit{(protagonist)}" in out
    assert "played by Rufus Sewell" in out
    assert "Master builder." in out
    # Original markdown header/image syntax should be gone.
    assert "**Tom Builder**" not in out
    assert "![alt]" not in out


def test_rewrite_skips_when_image_failed_to_download(tmp_path):
    """Image download failure → original block preserved so _rewrite_images
    handles the missing-image fallback."""
    md = (
        "**Char** *(major)* — played by Actor\n"
        "\n"
        "![alt](https://image.tmdb.org/missing.jpg)\n"
        "\n"
        "Desc.\n"
        "\n"
    )
    out = _rewrite_character_blocks(md, local_paths={})
    assert "\\begin{minipage}" not in out
    assert "![alt](https://image.tmdb.org/missing.jpg)" in out


def test_rewrite_escapes_special_chars_in_name_and_desc(tmp_path):
    img = tmp_path / "x.jpg"
    img.write_bytes(b"")
    md = (
        "**A&B Co.** *(major)* — played by Actor\n"
        "\n"
        "![alt](https://image.tmdb.org/x.jpg)\n"
        "\n"
        "Owns 50% of the operation.\n"
        "\n"
    )
    out = _rewrite_character_blocks(md, {"https://image.tmdb.org/x.jpg": img})
    assert r"A\&B Co." in out
    assert r"50\% of the operation" in out
