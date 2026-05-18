import hashlib
import re
import subprocess
import tempfile
from pathlib import Path

import httpx
import structlog

log = structlog.get_logger()

# pandoc + LaTeX cannot fetch remote URLs (see CLAUDE.md). We download every
# `![alt](http...)` to a temp dir and rewrite the markdown to point at the
# local file. The {width=...} attribute is pandoc-markdown — it scales the
# image in the PDF; vanilla MD viewers ignore it, which is why we only add it
# during PDF rewriting, not in the markdown the user downloads.
_REMOTE_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\((https?://[^)\s]+)\)")
_IMAGE_WIDTH = "2.5cm"
_DOWNLOAD_TIMEOUT_S = 10.0


def _download_images(md_text: str, image_dir: Path) -> dict[str, Path]:
    """Download every remote image URL referenced in md_text into image_dir.

    Returns a mapping {url: local_path} for URLs that downloaded successfully.
    Failures are logged and dropped — the markdown is then rewritten to omit
    the broken image rather than fail the whole PDF.
    """
    urls = {m.group(2) for m in _REMOTE_IMAGE_RE.finditer(md_text)}
    if not urls:
        return {}

    image_dir.mkdir(parents=True, exist_ok=True)
    local_paths: dict[str, Path] = {}
    with httpx.Client(timeout=_DOWNLOAD_TIMEOUT_S, follow_redirects=True) as client:
        for url in urls:
            try:
                resp = client.get(url)
                resp.raise_for_status()
            except Exception as e:
                log.warning("pdf_image_download_failed", url=url, error=str(e))
                continue
            suffix = Path(url.split("?", 1)[0]).suffix or ".jpg"
            digest = hashlib.sha1(url.encode()).hexdigest()[:16]
            local_path = image_dir / f"{digest}{suffix}"
            local_path.write_bytes(resp.content)
            local_paths[url] = local_path
    return local_paths


def _rewrite_images(md_text: str, local_paths: dict[str, Path]) -> str:
    """Replace remote image URLs with local paths (+ size hint). Broken
    images are dropped — the alt text remains as plain bracketed text so the
    PDF doesn't silently lose context."""
    def repl(match: re.Match) -> str:
        alt, url = match.group(1), match.group(2)
        path = local_paths.get(url)
        if path is None:
            return f"[{alt}]" if alt else ""
        return f"![{alt}]({path}){{ width={_IMAGE_WIDTH} }}"
    return _REMOTE_IMAGE_RE.sub(repl, md_text)


def render_pdf(md_text: str, job_id: str, output_dir: Path) -> Path:
    """Render markdown to PDF via pandoc. Raises RuntimeError on pandoc failure."""
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "character_map.pdf"

    with tempfile.TemporaryDirectory(prefix="charmap-pdf-") as workdir:
        workdir_path = Path(workdir)
        local_paths = _download_images(md_text, workdir_path / "images")
        rewritten = _rewrite_images(md_text, local_paths)
        md_path = workdir_path / "character_map.md"
        md_path.write_text(rewritten, encoding="utf-8")

        result = subprocess.run(
            [
                "pandoc", str(md_path),
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
        log.info(
            "pdf_rendered",
            job_id=job_id,
            size=output_path.stat().st_size,
            images=len(local_paths),
        )
        return output_path
