import time
import pytest
from unittest.mock import patch
from app.security.signed_urls import sign_artifact_url, verify_artifact_url


def test_sign_and_verify_round_trip():
    url = sign_artifact_url("/api/artifacts/abc/file.pdf")
    assert "?sig=" in url
    assert "&exp=" in url
    path, qs = url.split("?", 1)
    params = dict(p.split("=", 1) for p in qs.split("&"))
    assert verify_artifact_url(path, params["sig"], params["exp"])


def test_expired_url_rejected():
    with patch("app.security.signed_urls.time") as mock_time:
        mock_time.time.return_value = 1000.0
        url = sign_artifact_url("/api/artifacts/abc/file.pdf", expiry_seconds=10)
    path, qs = url.split("?", 1)
    params = dict(p.split("=", 1) for p in qs.split("&"))
    with patch("app.security.signed_urls.time") as mock_time:
        mock_time.time.return_value = 1020.0
        assert not verify_artifact_url(path, params["sig"], params["exp"])


def test_wrong_signature_rejected():
    url = sign_artifact_url("/api/artifacts/abc/file.pdf")
    path, qs = url.split("?", 1)
    params = dict(p.split("=", 1) for p in qs.split("&"))
    assert not verify_artifact_url(path, "deadbeef" * 8, params["exp"])


def test_tampered_path_rejected():
    url = sign_artifact_url("/api/artifacts/abc/file.pdf")
    path, qs = url.split("?", 1)
    params = dict(p.split("=", 1) for p in qs.split("&"))
    assert not verify_artifact_url("/api/artifacts/abc/other.pdf", params["sig"], params["exp"])


def test_invalid_exp_rejected():
    assert not verify_artifact_url("/path", "sig", "not-a-number")
