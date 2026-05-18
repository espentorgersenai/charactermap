import subprocess
import tempfile
from pathlib import Path

import structlog

log = structlog.get_logger()


def render_pdf(md_text: str, job_id: str, output_dir: Path) -> Path:
    """Render markdown to PDF via pandoc. Raises RuntimeError on pandoc failure."""
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "character_map.pdf"

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(md_text)
        tmp_path = Path(tmp.name)

    try:
        result = subprocess.run(
            [
                "pandoc", str(tmp_path),
                "--pdf-engine=pdflatex",
                "-o", str(output_path),
                "--variable", "geometry:margin=1in",
                "--variable", "fontsize=11pt",
                "--variable", "colorlinks=true",
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            raise RuntimeError(f"pandoc failed: {result.stderr}")
        log.info("pdf_rendered", job_id=job_id, size=output_path.stat().st_size)
        return output_path
    finally:
        tmp_path.unlink(missing_ok=True)
