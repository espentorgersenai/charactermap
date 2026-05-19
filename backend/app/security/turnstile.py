"""Cloudflare Turnstile server-side verification (SPEC §10.1).

`verify_token` calls Cloudflare's siteverify endpoint with the client-side
token and the server's secret. Returns True only when the response shows
`success: true`. Network errors, malformed responses, and empty tokens all
return False — fail-closed, never grant access on ambiguous output.
"""
from __future__ import annotations

import httpx
import structlog

log = structlog.get_logger()

_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


async def verify_token(token: str, secret: str, remote_ip: str | None = None) -> bool:
    """Verify a Turnstile token against Cloudflare's siteverify.

    Empty token → False without calling out. Network/parse errors → False.
    """
    if not token:
        return False
    payload = {"secret": secret, "response": token}
    if remote_ip:
        payload["remoteip"] = remote_ip
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(_VERIFY_URL, data=payload)
            data = resp.json()
    except Exception as e:
        log.warning("turnstile_verify_error", error=str(e))
        return False
    success = bool(data.get("success"))
    if not success:
        log.info(
            "turnstile_verify_failed",
            error_codes=data.get("error-codes"),
            ip=remote_ip,
        )
    return success
