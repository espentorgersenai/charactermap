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

# Character blocks with a headshot. Layout in markdown.py looks like:
#
#   **Name †** *(importance)* — played by Actor
#
#   ![alt](url)
#
#   Description paragraph.
#
# The PDF renderer rewrites these into side-by-side LaTeX minipages (photo
# left, text right) for a cleaner cast-list feel. Blocks without a headshot
# don't match this regex and stay in the default stacked layout.
_CHAR_BLOCK_RE = re.compile(
    r"^\*\*(?P<name>[^*\n]+)\*\*\s+\*\((?P<importance>[a-z]+)\)\*"
    r"(?P<actor_clause>(?:\s+—\s+played by\s+[^\n]+)?)\n"
    r"\n"
    r"!\[(?P<alt>[^\]]*)\]\((?P<url>https?://[^)\s]+)\)\n"
    r"\n"
    r"(?P<desc>[^\n]+(?:\n[^\n]+)*)\n",
    re.MULTILINE,
)

# Unicode chars in the symbol-and-pictograph blocks (U+2600+) aren't covered
# by pdflatex's default inputenc + lmodern tables — silently kills the PDF.
# Map the ones we actually emit (markdown.py uses ⚠ in the coverage-note line)
# to ASCII equivalents. Add new chars here as they appear.
_UNICODE_FALLBACKS = {
    "⚠": "!",
}


def _strip_pdf_unsafe_chars(s: str) -> str:
    for src, dst in _UNICODE_FALLBACKS.items():
        s = s.replace(src, dst)
    return s


# Per-character mapping for LaTeX escaping. Single-pass via re.sub so the
# braces emitted by `\textbackslash{}` don't themselves get re-escaped.
_LATEX_MAP = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}
_LATEX_RE = re.compile(r"[\\&%$#_{}~^]")


def _latex_escape(s: str) -> str:
    return _LATEX_RE.sub(lambda m: _LATEX_MAP[m.group(0)], s)


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


def _rewrite_character_blocks(md_text: str, local_paths: dict[str, Path]) -> str:
    """For character blocks with a headshot, emit a side-by-side LaTeX minipage
    layout (photo left, name + description right). Blocks without a headshot
    don't match the regex and stay as default stacked markdown.

    The right-side minipage holds raw LaTeX (escaped name + description + actor
    clause). Markdown formatting inside the description is *not* re-parsed —
    descriptions are plain prose from the LLM, so this is fine in practice."""
    def repl(match: re.Match) -> str:
        url = match.group("url")
        path = local_paths.get(url)
        if path is None:
            # Image download failed — keep the original block so the existing
            # broken-image fallback in _rewrite_images handles it.
            return match.group(0)

        name = _latex_escape(match.group("name").strip())
        importance = _latex_escape(match.group("importance").strip())
        desc = _latex_escape(match.group("desc").strip())

        actor_clause_raw = match.group("actor_clause") or ""
        actor_latex = ""
        if actor_clause_raw.strip():
            actor_name = actor_clause_raw.split("played by", 1)[1].strip()
            actor_latex = f" \\textemdash{{}} played by {_latex_escape(actor_name)}"

        # Two top-aligned minipages: photo on the left, name + description on
        # the right. The [t] alignment is what guarantees the heading's
        # top-of-text-line sits exactly at the top of the photo (which was
        # the previous wrapfigure version's problem — wrapfig threads the
        # figure into a paragraph and detaches it from the heading).
        # The `%` swallows the newlines so they don't insert a space between
        # the boxes; the `\hspace{0.5cm}` is the visual gap between photo
        # and text. Trailing `\par\vspace` puts visible air before the next
        # character block.
        return (
            "\\noindent\\begin{minipage}[t]{2.5cm}%\n"
            f"\\includegraphics[width=\\linewidth]{{{path}}}%\n"
            "\\end{minipage}%\n"
            "\\hspace{0.5cm}%\n"
            "\\begin{minipage}[t]{\\dimexpr\\linewidth-3cm}%\n"
            f"\\textbf{{{name}}} \\textit{{({importance})}}{actor_latex}\\par%\n"
            "\\vspace{0.3em}%\n"
            f"{desc}%\n"
            "\\end{minipage}%\n"
            "\n\n\\par\\vspace{1.6em}\n\n"
        )
    return _CHAR_BLOCK_RE.sub(repl, md_text)


def render_pdf(md_text: str, job_id: str, output_dir: Path) -> Path:
    """Render markdown to PDF via pandoc. Raises RuntimeError on pandoc failure."""
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "character_map.pdf"

    with tempfile.TemporaryDirectory(prefix="charmap-pdf-") as workdir:
        workdir_path = Path(workdir)
        local_paths = _download_images(md_text, workdir_path / "images")
        # Strip pdflatex-unsafe unicode (⚠ etc.) first so the substitution
        # doesn't sneak through the later passes.
        rewritten = _strip_pdf_unsafe_chars(md_text)
        # Character blocks with a headshot get the side-by-side minipage layout
        # first; the remaining standalone images (creator headshot, etc.) go
        # through the default `_rewrite_images` size-hint pass.
        rewritten = _rewrite_character_blocks(rewritten, local_paths)
        rewritten = _rewrite_images(rewritten, local_paths)
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
                # graphicx is only auto-included when the doc has at least one
                # markdown ![]() image. Our character-block rewriter consumes
                # all those into raw LaTeX `\includegraphics`, so we need to
                # request the package explicitly.
                "--variable", "header-includes=\\usepackage{graphicx}",
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
