"""Send the completion email via Resend (SPEC §10.5).

What we send:
  - HTML + plain-text body with a one-sentence framing.
  - The PDF attached directly (typically <500 KB).
  - A prominent "Open your map" link to /job/:id.
  - TMDb attribution footer when the map uses TMDb data.
  - A "what this is" honesty footer matching the homepage banner.
  - A `mailto:` link for deletion with a pre-filled subject.

Not yet wired in:
  - Inline PNG preview thumbnail. Backend has no server-side React Flow
    renderer; this is tracked as a follow-up Planka card.

`send_completion_email` short-circuits to False when there's no recipient
or no API key configured (dev mode). Network failures are logged and
returned as False — they MUST NOT break the pipeline.
"""
from __future__ import annotations

import base64
import html
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx
import structlog

from app.config import settings
from app.db.tables import Job

log = structlog.get_logger()

_RESEND_URL = "https://api.resend.com/emails"


def _uses_tmdb_data(char_map: dict | None) -> bool:
    if not char_map:
        return False
    creator = char_map.get("creator")
    if creator and creator.get("kind") == "director":
        return True
    return any(c.get("actor") for c in char_map.get("characters", []))


def _slugify(value: str) -> str:
    import re
    import unicodedata
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    value = re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-").lower()
    return value[:60] or "character-map"


def _html_body(job: Job, share_url: str, uses_tmdb: bool, delete_mailto: str) -> str:
    safe_title = html.escape(job.resolved_title or job.title_query or "your work")
    parts = [
        f"<p>Hi! Your character map for <strong>{safe_title}</strong> is ready.</p>",
        (
            f'<p><a href="{html.escape(share_url)}" '
            f'style="background:#111;color:#fff;padding:12px 18px;'
            f'border-radius:6px;text-decoration:none;display:inline-block;">'
            f"Open your map</a></p>"
        ),
        "<p>The PDF is attached to this email.</p>",
        (
            "<hr style='border:none;border-top:1px solid #ddd;margin:24px 0;'>"
            "<p style='font-size:13px;color:#555;'>"
            "This is a hobby project. The AI sometimes gets things wrong. "
            "If something looks off, try a different model from the dropdown."
            "</p>"
        ),
    ]
    if uses_tmdb:
        parts.append(
            "<p style='font-size:12px;color:#777;'>"
            "This product uses the TMDB API but is not endorsed or certified by TMDB. "
            "Photos and adaptation data: TMDb."
            "</p>"
        )
    parts.append(
        f"<p style='font-size:12px;color:#777;'>"
        f"Want this map deleted? "
        f'<a href="{html.escape(delete_mailto)}">Email us</a> '
        f"and we'll remove it.</p>"
    )
    return "".join(parts)


def _text_body(job: Job, share_url: str, uses_tmdb: bool, delete_mailto: str) -> str:
    title = job.resolved_title or job.title_query or "your work"
    lines = [
        f"Hi! Your character map for {title} is ready.",
        "",
        f"Open your map: {share_url}",
        "",
        "The PDF is attached to this email.",
        "",
        "-- ",
        "This is a hobby project. The AI sometimes gets things wrong.",
        "If something looks off, try a different model from the dropdown.",
    ]
    if uses_tmdb:
        lines += [
            "",
            "This product uses the TMDB API but is not endorsed or certified by TMDB.",
            "Photos and adaptation data: TMDb.",
        ]
    lines += ["", f"Want this map deleted? {delete_mailto}"]
    return "\n".join(lines)


def _delete_mailto(job: Job) -> str:
    subject = f"Delete character map {job.id}"
    return f"mailto:privacy@torgersen.ai?subject={quote(subject)}"


def build_email_payload(
    job: Job,
    base_url: str,
    pdf_bytes: bytes | None,
) -> dict[str, Any]:
    """Return the Resend-shaped payload (excluding the `from` field)."""
    share_url = f"{base_url.rstrip('/')}/job/{job.id}"
    uses_tmdb = _uses_tmdb_data(job.character_map)
    delete_mailto = _delete_mailto(job)

    payload: dict[str, Any] = {
        "to": [job.email] if job.email else [],
        "subject": f"Your character map for \"{job.resolved_title}\"",
        "html": _html_body(job, share_url, uses_tmdb, delete_mailto),
        "text": _text_body(job, share_url, uses_tmdb, delete_mailto),
    }
    if pdf_bytes:
        slug = _slugify(job.resolved_title or "character-map")
        payload["attachments"] = [{
            "filename": f"{slug}.pdf",
            "content_type": "application/pdf",
            "content": base64.b64encode(pdf_bytes).decode("ascii"),
        }]
    return payload


async def _http_post_resend(*, payload: dict[str, Any], api_key: str) -> dict:
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            _RESEND_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()


async def send_completion_email(
    job: Job,
    base_url: str,
    pdf_path: Path | None,
) -> bool:
    if not settings.resend_api_key:
        log.info("email_skipped_no_api_key", job_id=str(job.id))
        return False
    if not job.email:
        log.info("email_skipped_no_recipient", job_id=str(job.id))
        return False

    pdf_bytes: bytes | None = None
    if pdf_path is not None and Path(pdf_path).exists():
        pdf_bytes = Path(pdf_path).read_bytes()

    payload = build_email_payload(job, base_url, pdf_bytes)
    payload["from"] = settings.email_from
    try:
        result = await _http_post_resend(payload=payload, api_key=settings.resend_api_key)
    except Exception as e:
        log.warning("email_send_failed", job_id=str(job.id), error=str(e))
        return False
    log.info("email_sent", job_id=str(job.id), resend_id=result.get("id"))
    return True
