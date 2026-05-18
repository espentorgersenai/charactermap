import pytest
import subprocess
from pathlib import Path
from app.renderers.pdf import render_pdf

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
