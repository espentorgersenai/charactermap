from pathlib import Path
from uuid import UUID, uuid4

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_db
from app.db.tables import Artifact, Job
from app.security.signed_urls import sign_artifact_url, verify_artifact_url

log = structlog.get_logger()
router = APIRouter()

_FORMAT_EXT = {
    "png": "png", "svg": "svg", "json": "json",
    "markdown": "md", "pdf": "pdf",
}
_EXT_CONTENT_TYPE = {
    "png": "image/png", "svg": "image/svg+xml", "json": "application/json",
    "md": "text/markdown", "pdf": "application/pdf",
}


@router.post("/api/jobs/{job_id}/artifacts", status_code=201)
async def upload_artifact(
    job_id: str,
    format: str,
    file: UploadFile,
    session: AsyncSession = Depends(get_db),
) -> dict:
    job = await session.get(Job, UUID(job_id))
    if not job:
        raise HTTPException(status_code=404, detail={"error": "job not found", "code": "NOT_FOUND"})

    ext = _FORMAT_EXT.get(format, format)
    artifact_dir = Path(settings.artifact_storage_path) / job_id
    artifact_dir.mkdir(parents=True, exist_ok=True)
    file_path = artifact_dir / f"character_map.{ext}"

    content = await file.read()
    file_path.write_bytes(content)

    artifact = Artifact(
        id=uuid4(),
        job_id=UUID(job_id),
        format=format,
        file_path=str(Path(job_id) / f"character_map.{ext}"),
        file_size=len(content),
    )
    session.add(artifact)
    await session.commit()
    log.info("artifact_uploaded", job_id=job_id, format=format, size=len(content))
    return {"format": format, "size": len(content)}


@router.get("/api/jobs/{job_id}/artifacts")
async def list_artifacts(job_id: str, session: AsyncSession = Depends(get_db)) -> list:
    job = await session.get(Job, UUID(job_id))
    if not job:
        raise HTTPException(status_code=404, detail={"error": "job not found", "code": "NOT_FOUND"})

    result = await session.execute(
        select(Artifact).where(Artifact.job_id == UUID(job_id))
    )
    artifacts = result.scalars().all()
    return [
        {
            "format": a.format,
            "url": sign_artifact_url(
                f"/api/artifacts/{job_id}/{Path(a.file_path).name}"
            ),
        }
        for a in artifacts
    ]


@router.get("/api/artifacts/{job_id}/{filename}")
async def serve_artifact(job_id: str, filename: str, request: Request) -> FileResponse:
    sig = request.query_params.get("sig", "")
    exp = request.query_params.get("exp", "")
    path = f"/api/artifacts/{job_id}/{filename}"

    if not verify_artifact_url(path, sig, exp):
        raise HTTPException(
            status_code=403,
            detail={"error": "invalid or expired signature", "code": "FORBIDDEN"},
        )

    file_path = Path(settings.artifact_storage_path) / job_id / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail={"error": "file not found", "code": "NOT_FOUND"})

    ext = filename.rsplit(".", 1)[-1] if "." in filename else ""
    media_type = _EXT_CONTENT_TYPE.get(ext, "application/octet-stream")
    return FileResponse(str(file_path), media_type=media_type, filename=filename)
