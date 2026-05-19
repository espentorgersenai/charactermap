"""Email composition + delivery via Resend (SPEC §10.5).

These tests cover the local email-building helpers and the high-level
`send_completion_email` function, which is patched to avoid making real
Resend calls. The pipeline-side wiring (call when email is set, skip when
not) is exercised in tests/unit/test_pipeline_email.py.
"""
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.db.tables import Job
from app.email.mailer import build_email_payload, send_completion_email


def _make_job(email="user@example.com", title="Congo", with_tmdb=True) -> Job:
    return Job(
        id=uuid4(),
        work_type="book",
        title_query=title,
        resolved_id="OL1",
        resolved_title=title,
        resolved_year=1980,
        resolved_meta={"author": "Michael Crichton", "source": "openlibrary"},
        model="claude-sonnet-4-6",
        formats=["interactive", "pdf"],
        email=email,
        acknowledgement_at=datetime.now(tz=timezone.utc),
        requester_ip="127.0.0.1",
        character_cap=20,
        status="done",
        character_map={
            "title": title,
            "subtitle": "X",
            "blurb": "Y",
            "spoiler_mode": "full",
            "factions": [],
            "characters": [{"id": "p", "name": "P", "actor": "A"}] if with_tmdb else [],
            "relationships": [],
            "creator": {"kind": "director", "name": "Z"} if with_tmdb else None,
            "notes": "",
        },
    )


def test_build_email_payload_subject_includes_title():
    job = _make_job(title="Congo")
    payload = build_email_payload(job, base_url="https://test.example", pdf_bytes=b"%PDF-1.4")
    assert "Congo" in payload["subject"]


def test_build_email_payload_includes_share_link():
    job = _make_job()
    payload = build_email_payload(job, base_url="https://test.example", pdf_bytes=b"%PDF-1.4")
    assert f"https://test.example/job/{job.id}" in payload["html"]
    assert f"https://test.example/job/{job.id}" in payload["text"]


def test_build_email_payload_attaches_pdf():
    job = _make_job()
    payload = build_email_payload(job, base_url="https://test.example", pdf_bytes=b"%PDF-1.4")
    assert payload["attachments"]
    att = payload["attachments"][0]
    assert att["filename"].endswith(".pdf")
    assert att["content_type"] == "application/pdf"
    assert att["content"]  # base64 string


def test_build_email_payload_omits_attachment_when_no_pdf():
    job = _make_job()
    payload = build_email_payload(job, base_url="https://test.example", pdf_bytes=None)
    assert payload.get("attachments") in (None, [])


def test_build_email_payload_includes_delete_mailto():
    job = _make_job()
    payload = build_email_payload(job, base_url="https://test.example", pdf_bytes=b"%PDF-1.4")
    assert f"mailto:" in payload["html"]
    assert str(job.id) in payload["html"]  # job id in the delete subject


def test_build_email_payload_tmdb_attribution_when_map_uses_tmdb():
    job = _make_job(with_tmdb=True)
    payload = build_email_payload(job, base_url="https://test.example", pdf_bytes=b"%PDF-1.4")
    assert "TMDB" in payload["html"]


def test_build_email_payload_no_tmdb_attribution_when_unused():
    job = _make_job(with_tmdb=False)
    payload = build_email_payload(job, base_url="https://test.example", pdf_bytes=b"%PDF-1.4")
    assert "TMDB" not in payload["html"]


def test_build_email_payload_has_what_this_is_footer():
    """SPEC §10.5: a short "what this is" footer sets honest expectations."""
    job = _make_job()
    payload = build_email_payload(job, base_url="https://test.example", pdf_bytes=b"%PDF-1.4")
    assert "AI" in payload["html"] and "wrong" in payload["html"]


def test_build_email_payload_to_uses_job_email():
    job = _make_job(email="someone@example.com")
    payload = build_email_payload(job, base_url="https://test.example", pdf_bytes=b"%PDF-1.4")
    assert payload["to"] == ["someone@example.com"]


# --- send_completion_email guard rails ------------------------------


@pytest.mark.asyncio
async def test_send_completion_email_skips_without_api_key(monkeypatch, tmp_path):
    """No RESEND_API_KEY → no-op (dev mode)."""
    monkeypatch.setattr("app.email.mailer.settings.resend_api_key", "")
    job = _make_job()
    with patch("app.email.mailer._http_post_resend", new=AsyncMock()) as mock_post:
        ok = await send_completion_email(job, base_url="x", pdf_path=None)
    assert ok is False
    mock_post.assert_not_called()


@pytest.mark.asyncio
async def test_send_completion_email_skips_without_recipient(monkeypatch, tmp_path):
    monkeypatch.setattr("app.email.mailer.settings.resend_api_key", "re_test_key")
    job = _make_job(email=None)
    with patch("app.email.mailer._http_post_resend", new=AsyncMock()) as mock_post:
        ok = await send_completion_email(job, base_url="x", pdf_path=None)
    assert ok is False
    mock_post.assert_not_called()


@pytest.mark.asyncio
async def test_send_completion_email_calls_resend(monkeypatch, tmp_path):
    monkeypatch.setattr("app.email.mailer.settings.resend_api_key", "re_test_key")
    monkeypatch.setattr("app.email.mailer.settings.email_from", "from@x.com")
    job = _make_job()
    pdf = tmp_path / "out.pdf"
    pdf.write_bytes(b"%PDF-1.4 test")
    with patch("app.email.mailer._http_post_resend", new=AsyncMock(return_value={"id": "msg_1"})) as mock_post:
        ok = await send_completion_email(job, base_url="https://x", pdf_path=pdf)
    assert ok is True
    mock_post.assert_called_once()
    payload = mock_post.call_args.kwargs["payload"]
    assert payload["from"] == "from@x.com"
    assert payload["to"] == ["user@example.com"]
    assert payload["attachments"]
