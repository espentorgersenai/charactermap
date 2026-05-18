import pytest
import subprocess
from pathlib import Path
from app.renderers.pdf import (
    _REMOTE_IMAGE_RE,
    _rewrite_images,
    render_pdf,
)

pytestmark = pytest.mark.skipif(
    subprocess.run(["which", "pandoc"], capture_output=True).returncode != 0
    or subprocess.run(["which", "pdflatex"], capture_output=True).returncode != 0,
    reason="pandoc or pdflatex not installed",
)

MINIMAL_MD = """# Congo

## ERTS Expedition

**Peter Elliot** *(protagonist)*

A UC Berkeley professor.

---

This map contains full spoilers.
"""


def test_pdf_produced(tmp_path):
    path = render_pdf(MINIMAL_MD, "test-job-id", tmp_path)
    assert path.exists()
    assert path.stat().st_size > 0
    assert path.suffix == ".pdf"


def test_pdf_in_correct_directory(tmp_path):
    path = render_pdf(MINIMAL_MD, "test-job-id", tmp_path)
    assert path.parent == tmp_path


def test_pandoc_error_raises(tmp_path, monkeypatch):
    """Force pandoc to fail by patching subprocess.run to return a non-zero exit code."""
    import subprocess as _sp

    def _fake_run(cmd, **kwargs):
        result = _sp.CompletedProcess(cmd, returncode=1, stdout="", stderr="pandoc failed: synthetic error")
        return result

    monkeypatch.setattr("app.renderers.pdf.subprocess.run", _fake_run)
    with pytest.raises(RuntimeError, match="pandoc failed"):
        render_pdf("anything", "test-job-id", tmp_path)


def test_image_regex_matches_remote_image():
    md = "![Alice as played by Bob](https://image.tmdb.org/t/p/w185/abc.jpg)"
    matches = list(_REMOTE_IMAGE_RE.finditer(md))
    assert len(matches) == 1
    assert matches[0].group(2) == "https://image.tmdb.org/t/p/w185/abc.jpg"


def test_image_regex_ignores_local_paths():
    md = "![Alice](./local.jpg)"
    assert _REMOTE_IMAGE_RE.search(md) is None


def test_rewrite_drops_failed_downloads():
    md = (
        "![Alice](https://image.tmdb.org/a.jpg) and "
        "![Bob](https://image.tmdb.org/b.jpg)"
    )
    # Only Alice downloaded successfully
    local_paths = {"https://image.tmdb.org/a.jpg": Path("/tmp/a.jpg")}
    rewritten = _rewrite_images(md, local_paths)
    assert "(/tmp/a.jpg)" in rewritten
    assert "{ width=2.5cm }" in rewritten
    assert "https://image.tmdb.org/b.jpg" not in rewritten
    # Bob fell back to bracketed alt text
    assert "[Bob]" in rewritten


def test_rewrite_preserves_non_image_markdown():
    md = "# Title\n\nSome **bold** text and a [link](https://example.com)."
    rewritten = _rewrite_images(md, {})
    assert rewritten == md


def _minimal_png() -> bytes:
    """Build a real, validation-clean 1x1 RGB PNG at runtime (the libpng
    in TeX Live is picky about hand-rolled byte literals)."""
    import struct
    import zlib

    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)  # 1x1 RGB
    raw = b"\x00\xff\xff\xff"  # filter byte + one RGB pixel
    return sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


def test_pdf_with_remote_image(tmp_path, monkeypatch):
    """End-to-end: a remote image URL gets downloaded, the PDF is built."""
    import httpx
    from app.renderers import pdf as pdf_module

    fake_png = _minimal_png()

    class _FakeClient:
        def __init__(self, *a, **kw): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def get(self, url):
            return httpx.Response(200, content=fake_png, request=httpx.Request("GET", url))

    monkeypatch.setattr(pdf_module.httpx, "Client", _FakeClient)

    md = (
        "# Test\n\n"
        "![Pic](https://image.tmdb.org/test.png)\n\n"
        "Body.\n"
    )
    path = render_pdf(md, "test-job-id", tmp_path)
    assert path.exists()
    assert path.stat().st_size > 0
