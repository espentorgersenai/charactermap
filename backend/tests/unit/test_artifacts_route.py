import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.db.session import get_db
from app.security.signed_urls import sign_artifact_url


@pytest.fixture
def mock_db():
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()

    async def override():
        yield session

    app.dependency_overrides[get_db] = override
    yield session
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_upload_artifact(mock_db, tmp_path):
    from uuid import uuid4
    from app.db.tables import Job
    job_id = str(uuid4())
    mock_job = MagicMock(spec=Job)
    mock_job.id = job_id
    mock_db.get = AsyncMock(return_value=mock_job)

    with patch("app.routes.artifacts.settings") as mock_settings:
        mock_settings.artifact_storage_path = str(tmp_path)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/jobs/{job_id}/artifacts",
                params={"format": "markdown"},
                files={"file": ("character_map.md", b"# Congo\n", "text/markdown")},
            )

    assert response.status_code == 201
    data = response.json()
    assert data["format"] == "markdown"
    assert data["size"] == len(b"# Congo\n")


@pytest.mark.asyncio
async def test_upload_artifact_unknown_job(mock_db, tmp_path):
    from uuid import uuid4
    mock_db.get = AsyncMock(return_value=None)

    with patch("app.routes.artifacts.settings") as mock_settings:
        mock_settings.artifact_storage_path = str(tmp_path)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/jobs/{uuid4()}/artifacts",
                params={"format": "markdown"},
                files={"file": ("character_map.md", b"# Congo\n", "text/markdown")},
            )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_serve_artifact_invalid_signature(tmp_path):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/artifacts/some-job-id/file.pdf",
            params={"sig": "bad", "exp": "9999999999"},
        )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_serve_artifact_valid_signature(tmp_path):
    job_id = "test-job-id"
    filename = "character_map.md"
    file_content = b"# Test"

    artifact_dir = tmp_path / job_id
    artifact_dir.mkdir()
    (artifact_dir / filename).write_bytes(file_content)

    path = f"/api/artifacts/{job_id}/{filename}"
    signed = sign_artifact_url(path)
    _, qs = signed.split("?", 1)
    params = dict(p.split("=", 1) for p in qs.split("&"))

    with patch("app.routes.artifacts.settings") as mock_settings:
        mock_settings.artifact_storage_path = str(tmp_path)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(path, params=params)

    assert response.status_code == 200
    assert response.content == file_content
