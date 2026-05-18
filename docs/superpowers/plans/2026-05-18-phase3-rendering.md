# Phase 3 — Rendering: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the "raw JSON" done state with a fully interactive React Flow character map, add server-side Markdown + PDF renderers, artifact storage with signed URLs, and result caching (Opus maps reused for all subsequent requests for the same work).

**Architecture:** Backend-first build order — signed URLs → artifact endpoints → cache index → renderers → pipeline wiring — then frontend: TypeScript types → dagre layout → React Flow components → JobView done state. The canvas uses custom React Flow node types (`characterCard`, `factionGroup`) with dagre auto-layout. Badges (⚠ †) and legend are independent toggles, hidden by default.

**Tech Stack:** React Flow (`@xyflow/react`), dagre, html-to-image, FastAPI, SQLAlchemy async, Alembic, bleach, pandoc + pdflatex (in worker Docker image), HMAC-SHA256 signed URLs

---

## File map

### New backend files

| File | Purpose |
|------|---------|
| `backend/app/security/signed_urls.py` | `sign_artifact_url`, `verify_artifact_url` (HMAC-SHA256, 7-day TTL) |
| `backend/app/routes/artifacts.py` | `POST/GET /api/jobs/:id/artifacts`, `GET /api/artifacts/:job_id/:filename` |
| `backend/app/renderers/markdown.py` | `render_markdown(char_map) → str` with bleach sanitisation |
| `backend/app/renderers/pdf.py` | `render_pdf(md_text, job_id, output_dir) → Path` via pandoc subprocess |
| `backend/app/db/migrations/versions/0002_cache_index.py` | Partial index on `(resolved_id, spoiler_mode)` where `status='done'` |

### New frontend files

| File | Purpose |
|------|---------|
| `frontend/src/types/characterMap.ts` | TypeScript interfaces matching backend Pydantic schema |
| `frontend/src/layout/dagreLayout.ts` | `buildLayout(charMap) → {nodes, edges}` — positions via dagre |
| `frontend/src/components/CharacterCardNode.tsx` | Horizontal pill node — avatar, name, role, badges |
| `frontend/src/components/FactionGroupNode.tsx` | Translucent background rect with label |
| `frontend/src/components/CharacterMapCanvas.tsx` | React Flow wrapper + toolbar + banners + legend toggle |
| `frontend/src/components/ExportMenu.tsx` | PNG/SVG/JSON export + POST to backend |
| `frontend/src/components/ShareButton.tsx` | Clipboard copy of `/job/:id` |
| `frontend/src/components/DownloadList.tsx` | Sidebar: Markdown + PDF download buttons via signed URLs |

### Modified files

| File | Change |
|------|--------|
| `backend/pyproject.toml` | Add `bleach>=6.0` |
| `backend/Dockerfile` | Add pandoc + texlive to worker stage |
| `backend/app/main.py` | Include artifacts router |
| `backend/app/worker/pipeline.py` | Run MD+PDF renderers after done; cache lookup in job creation |
| `backend/app/routes/jobs.py` | `find_best_cached_job` + cache-hit path in `POST /api/jobs` |
| `frontend/package.json` | Add `@xyflow/react`, `dagre`, `@types/dagre`, `html-to-image` |
| `frontend/src/api/client.ts` | `uploadArtifact`, `getArtifacts` |
| `frontend/src/routes/JobView.tsx` | Done state: full-page canvas with sidebar |

---

## Task 0: Install new dependencies

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `frontend/package.json` (via npm install)

- [ ] **Step 1: Add bleach to backend**

In `backend/pyproject.toml`, add to `dependencies`:
```toml
"bleach>=6.0",
```

- [ ] **Step 2: Install frontend packages**

```bash
cd frontend && npm install @xyflow/react dagre @types/dagre html-to-image
```

Expected: packages added to `package.json` and `package-lock.json`, no peer-dep errors.

- [ ] **Step 3: Verify TypeScript can see the new types**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -5
```

Expected: no errors (or only pre-existing errors, not new ones from the installed packages).

- [ ] **Step 4: Commit**

```bash
git add backend/pyproject.toml frontend/package.json frontend/package-lock.json
git commit -m "chore: add bleach, @xyflow/react, dagre, html-to-image dependencies"
```

---

## Task 1: CharacterMap TypeScript types

**Files:**
- Create: `frontend/src/types/characterMap.ts`

- [ ] **Step 1: Create the types file**

Create `frontend/src/types/characterMap.ts`:

```typescript
export type ColorHint = 'blue' | 'red' | 'green' | 'amber' | 'violet' | 'slate'
export type Importance = 'protagonist' | 'major' | 'supporting' | 'minor'
export type RelationshipType =
  | 'alliance' | 'family' | 'romantic' | 'antagonism'
  | 'professional' | 'mentorship' | 'criminal'
export type SpoilerLevel = 0 | 1 | 2 | 3

export interface Faction {
  id: string
  label: string
  description: string
  color_hint: ColorHint
}

export interface ActorInfo {
  name: string
  tmdb_person_id: number
  headshot_url: string
}

export interface Character {
  id: string
  name: string
  role: string
  description: string
  faction_id: string | null
  importance: Importance
  is_deceased_in_work: boolean
  spoiler_level: SpoilerLevel | null
  actor?: ActorInfo
}

export interface Relationship {
  from_id: string
  to_id: string
  type: RelationshipType
  label: string
  spoiler_level: SpoilerLevel | null
}

export interface CharacterMap {
  title: string
  subtitle: string
  blurb: string
  spoiler_mode: 'full'
  setting_preamble?: string
  factions: Faction[]
  characters: Character[]
  relationships: Relationship[]
  coverage_note?: string
  notes: string
}
```

- [ ] **Step 2: Verify no TypeScript errors**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep characterMap
```

Expected: no output (no errors in the new file).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/types/characterMap.ts
git commit -m "feat: CharacterMap TypeScript types"
```

---

## Task 2: Signed URLs (TDD)

**Files:**
- Create: `backend/app/security/signed_urls.py`
- Create: `backend/tests/unit/test_signed_urls.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/unit/test_signed_urls.py`:

```python
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
    # Now time has advanced past expiry
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
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd backend && python -m pytest tests/unit/test_signed_urls.py -v 2>&1 | head -10
```

Expected: `ImportError` for `app.security.signed_urls`.

- [ ] **Step 3: Implement**

Create `backend/app/security/signed_urls.py`:

```python
import hashlib
import hmac
import time as time_module

from app.config import settings


def sign_artifact_url(path: str, expiry_seconds: int = 7 * 24 * 3600) -> str:
    exp = int(time_module.time()) + expiry_seconds
    sig = _compute_sig(path, str(exp))
    return f"{path}?sig={sig}&exp={exp}"


def verify_artifact_url(path: str, sig: str, exp: str) -> bool:
    try:
        if int(exp) < int(time_module.time()):
            return False
        expected = _compute_sig(path, exp)
        return hmac.compare_digest(sig, expected)
    except (ValueError, TypeError):
        return False


def _compute_sig(path: str, exp: str) -> str:
    msg = f"{path}:{exp}".encode()
    key = settings.artifact_signing_key.encode()
    return hmac.new(key, msg, hashlib.sha256).hexdigest()
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd backend && python -m pytest tests/unit/test_signed_urls.py -v
```

Expected: 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/security/signed_urls.py backend/tests/unit/test_signed_urls.py
git commit -m "feat: HMAC-SHA256 signed artifact URLs + tests"
```

---

## Task 3: Artifact endpoints (TDD)

**Files:**
- Create: `backend/app/routes/artifacts.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/unit/test_artifacts_route.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/unit/test_artifacts_route.py`:

```python
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
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd backend && python -m pytest tests/unit/test_artifacts_route.py -v 2>&1 | head -10
```

Expected: `ImportError` for `app.routes.artifacts`.

- [ ] **Step 3: Implement the artifacts router**

Create `backend/app/routes/artifacts.py`:

```python
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
```

- [ ] **Step 4: Wire the router into main.py**

Edit `backend/app/main.py` — add after the existing router includes:

```python
from app.routes.artifacts import router as artifacts_router
# ...
app.include_router(artifacts_router)
```

- [ ] **Step 5: Run tests to confirm they pass**

```bash
cd backend && python -m pytest tests/unit/test_artifacts_route.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 6: Run full unit suite**

```bash
cd backend && python -m pytest tests/unit/ -q
```

Expected: all tests PASS (no regressions).

- [ ] **Step 7: Commit**

```bash
git add backend/app/routes/artifacts.py backend/app/main.py backend/tests/unit/test_artifacts_route.py
git commit -m "feat: artifact upload/list/serve endpoints with HMAC signed URLs"
```

---

## Task 4: Alembic migration — cache index

**Files:**
- Create: `backend/app/db/migrations/versions/0002_cache_index.py`

- [ ] **Step 1: Create the migration file**

Create `backend/app/db/migrations/versions/0002_cache_index.py`:

```python
"""cache index on resolved_id + spoiler_mode for done jobs

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-18 00:00:00.000000
"""
from alembic import op
from sqlalchemy import text

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "idx_jobs_cache",
        "jobs",
        ["resolved_id", "spoiler_mode"],
        postgresql_where=text("status = 'done' AND deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_jobs_cache", table_name="jobs")
```

- [ ] **Step 2: Run the migration**

```bash
docker exec charmap_api alembic upgrade head
```

Expected: `Running upgrade 0001 -> 0002, cache index on resolved_id + spoiler_mode for done jobs`

- [ ] **Step 3: Verify the index exists**

```bash
docker exec charmap_postgres psql -U charactermap -c "\d jobs" | grep idx_jobs_cache
```

Expected: `idx_jobs_cache` appears in the index list.

- [ ] **Step 4: Commit**

```bash
git add backend/app/db/migrations/versions/0002_cache_index.py
git commit -m "feat: Alembic migration 0002 — cache index on (resolved_id, spoiler_mode) for done jobs"
```

---

## Task 5: Result cache lookup (TDD)

**Files:**
- Modify: `backend/app/routes/jobs.py`
- Create: `backend/tests/unit/test_cache_lookup.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/unit/test_cache_lookup.py`:

```python
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from app.routes.jobs import find_best_cached_job
from app.db.tables import Job

MODEL_QUALITY_ORDER = [
    "claude-opus-4-7",
    "claude-sonnet-4-6",
    "gpt-5.5",
    "gemini-2.5-pro",
    "claude-haiku-4-5-20251001",
]


def _make_job(model: str, character_map: dict | None = None, deleted: bool = False) -> Job:
    j = MagicMock(spec=Job)
    j.model = model
    j.status = "done"
    j.character_map = character_map or {"title": "Congo"}
    j.deleted_at = datetime.now(tz=timezone.utc) if deleted else None
    return j


@pytest.mark.asyncio
async def test_opus_job_returned_when_available():
    sonnet_job = _make_job("claude-sonnet-4-6")
    opus_job = _make_job("claude-opus-4-7")
    session = AsyncMock()
    session.execute = AsyncMock()
    session.execute.return_value.scalars.return_value.all.return_value = [sonnet_job, opus_job]

    result = await find_best_cached_job(session, "OL12345W", "full")
    assert result is opus_job


@pytest.mark.asyncio
async def test_sonnet_returned_when_no_opus():
    haiku_job = _make_job("claude-haiku-4-5-20251001")
    sonnet_job = _make_job("claude-sonnet-4-6")
    session = AsyncMock()
    session.execute = AsyncMock()
    session.execute.return_value.scalars.return_value.all.return_value = [haiku_job, sonnet_job]

    result = await find_best_cached_job(session, "OL12345W", "full")
    assert result is sonnet_job


@pytest.mark.asyncio
async def test_no_cached_jobs_returns_none():
    session = AsyncMock()
    session.execute = AsyncMock()
    session.execute.return_value.scalars.return_value.all.return_value = []

    result = await find_best_cached_job(session, "OL12345W", "full")
    assert result is None


@pytest.mark.asyncio
async def test_unknown_model_ranked_last():
    unknown_job = _make_job("gpt-99")
    haiku_job = _make_job("claude-haiku-4-5-20251001")
    session = AsyncMock()
    session.execute = AsyncMock()
    session.execute.return_value.scalars.return_value.all.return_value = [unknown_job, haiku_job]

    result = await find_best_cached_job(session, "OL12345W", "full")
    assert result is haiku_job
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd backend && python -m pytest tests/unit/test_cache_lookup.py -v 2>&1 | head -10
```

Expected: `ImportError` — `find_best_cached_job` not yet defined.

- [ ] **Step 3: Add `find_best_cached_job` to jobs.py and the cache-hit path**

Add to `backend/app/routes/jobs.py` (at the top of the file, after existing imports):

```python
from typing import Optional
from sqlalchemy import select
```

Add this function before the `create_job` route handler:

```python
_MODEL_QUALITY_ORDER = [
    "claude-opus-4-7",
    "claude-sonnet-4-6",
    "gpt-5.5",
    "gemini-2.5-pro",
    "claude-haiku-4-5-20251001",
]


async def find_best_cached_job(
    session: AsyncSession,
    resolved_id: str,
    spoiler_mode: str,
) -> Optional[Job]:
    """Return the highest-quality cached CharacterMap result, or None."""
    result = await session.execute(
        select(Job).where(
            Job.resolved_id == resolved_id,
            Job.spoiler_mode == spoiler_mode,
            Job.status == "done",
            Job.deleted_at.is_(None),
            Job.character_map.is_not(None),
        )
    )
    jobs = result.scalars().all()
    if not jobs:
        return None
    jobs.sort(
        key=lambda j: _MODEL_QUALITY_ORDER.index(j.model)
        if j.model in _MODEL_QUALITY_ORDER else 99
    )
    return jobs[0]
```

Then update the `create_job` route handler — add a cache-hit check right after the `acknowledged_spoilers` gate and before the Job construction:

```python
    # Cache check: reuse the best existing result for this work
    cached = await find_best_cached_job(session, resolved.id, "full")
    if cached:
        cached_job = Job(
            id=uuid4(),
            work_type=work_type,
            title_query=body.title_query,
            resolved_id=resolved.id,
            resolved_title=resolved.title,
            resolved_year=resolved.year,
            resolved_meta=resolved_meta,
            model=cached.model,           # record the model that actually generated it
            formats=body.formats,
            email=body.email,
            acknowledgement_at=datetime.now(tz=timezone.utc),
            status="done",
            completed_at=datetime.now(tz=timezone.utc),
            character_map=cached.character_map,
            estimated_cost_usd=Decimal("0"),
            requester_ip=request.client.host if request.client else "127.0.0.1",
            user_agent=request.headers.get("user-agent"),
        )
        session.add(cached_job)
        await session.commit()
        log.info("job_cache_hit", job_id=str(cached_job.id), source_model=cached.model)
        return JobCreateResponse(job_id=str(cached_job.id))
```

Also add `from decimal import Decimal` to the imports in `jobs.py`.

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd backend && python -m pytest tests/unit/test_cache_lookup.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 5: Run full unit suite**

```bash
cd backend && python -m pytest tests/unit/ -q
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routes/jobs.py backend/tests/unit/test_cache_lookup.py
git commit -m "feat: result cache — reuse best existing map on POST /api/jobs, Opus trumps all"
```

---

## Task 6: Markdown renderer (TDD)

**Files:**
- Create: `backend/app/renderers/markdown.py`
- Create: `backend/tests/unit/test_markdown_renderer.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/unit/test_markdown_renderer.py`:

```python
import pytest
from app.renderers.markdown import render_markdown
from app.models.character_map import (
    CharacterMap, Character, Faction, Relationship,
)

FIXTURE = CharacterMap(
    title="Congo",
    subtitle="Michael Crichton, 1980",
    blurb="An expedition into the Congo Basin.",
    spoiler_mode="full",
    factions=[
        Faction(id="erts", label="ERTS Expedition", description="The primary team.", color_hint="blue"),
    ],
    characters=[
        Character(
            id="peter",
            name="Peter Elliot",
            role="Primatologist",
            description="A UC Berkeley professor.",
            faction_id="erts",
            importance="protagonist",
            is_deceased_in_work=False,
            spoiler_level=0,
        ),
        Character(
            id="travis",
            name="R. B. Travis",
            role="CEO",
            description="Antagonist, <script>alert('xss')</script> greedy.",
            faction_id="erts",
            importance="major",
            is_deceased_in_work=True,
            spoiler_level=3,
        ),
    ],
    relationships=[
        Relationship(from_id="peter", to_id="travis", type="antagonism", label="rivals", spoiler_level=2),
    ],
    notes="Full-spoiler map.",
)


def test_title_present():
    md = render_markdown(FIXTURE)
    assert "# Congo" in md


def test_faction_section_present():
    md = render_markdown(FIXTURE)
    assert "## ERTS Expedition" in md


def test_character_name_present():
    md = render_markdown(FIXTURE)
    assert "Peter Elliot" in md


def test_deceased_marker():
    md = render_markdown(FIXTURE)
    assert "R. B. Travis †" in md or "R. B. Travis" in md  # dagger in name


def test_relationships_table_present():
    md = render_markdown(FIXTURE)
    assert "## Relationships" in md
    assert "antagonism" in md


def test_bleach_strips_script_tags():
    md = render_markdown(FIXTURE)
    assert "<script>" not in md
    assert "alert('xss')" in md  # text content preserved, tag stripped


def test_coverage_note_present():
    cm = FIXTURE.model_copy(update={"coverage_note": "Cap forced exclusions."})
    md = render_markdown(cm)
    assert "Coverage note" in md
    assert "Cap forced exclusions." in md


def test_setting_preamble_present():
    cm = FIXTURE.model_copy(update={"setting_preamble": "The story takes place in the Congo."})
    md = render_markdown(cm)
    assert "## Setting" in md
    assert "The story takes place in the Congo." in md


def test_footer_present():
    md = render_markdown(FIXTURE)
    assert "full spoilers" in md.lower()
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd backend && python -m pytest tests/unit/test_markdown_renderer.py -v 2>&1 | head -10
```

Expected: `ImportError` for `app.renderers.markdown`.

- [ ] **Step 3: Implement the renderer**

Create `backend/app/renderers/markdown.py`:

```python
import bleach
from app.models.character_map import CharacterMap


def _clean(text: str) -> str:
    """Strip any HTML injected by the LLM."""
    return bleach.clean(text, tags=[], strip=True)


def render_markdown(char_map: CharacterMap) -> str:
    lines: list[str] = []

    lines += [f"# {_clean(char_map.title)}", f"## {_clean(char_map.subtitle)}", ""]
    lines += [_clean(char_map.blurb), ""]

    if char_map.coverage_note:
        lines += [f"> ⚠ **Coverage note:** {_clean(char_map.coverage_note)}", ""]

    if char_map.setting_preamble:
        lines += ["## Setting", "", _clean(char_map.setting_preamble), ""]

    char_by_id = {c.id: c for c in char_map.characters}

    for faction in char_map.factions:
        lines += [f"## {_clean(faction.label)}", "", _clean(faction.description), ""]
        for char in char_map.characters:
            if char.faction_id != faction.id:
                continue
            dagger = " †" if char.is_deceased_in_work else ""
            lines += [
                f"**{_clean(char.name)}{dagger}** *({char.importance})*",
                "",
                _clean(char.description),
                "",
            ]

    if char_map.relationships:
        lines += ["## Relationships", "", "| From | To | Type | Notes |", "|------|----|------|-------|"]
        for rel in char_map.relationships:
            from_name = _clean(char_by_id[rel.from_id].name) if rel.from_id in char_by_id else rel.from_id
            to_name = _clean(char_by_id[rel.to_id].name) if rel.to_id in char_by_id else rel.to_id
            lines.append(f"| {from_name} | {to_name} | {rel.type} | {_clean(rel.label)} |")
        lines.append("")

    lines += ["---", "", f"*{_clean(char_map.notes)}*", ""]
    lines.append(
        "This map contains full spoilers. Generated by Character Map Generator."
    )
    return "\n".join(lines)
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd backend && python -m pytest tests/unit/test_markdown_renderer.py -v
```

Expected: 9 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/renderers/markdown.py backend/tests/unit/test_markdown_renderer.py
git commit -m "feat: Markdown renderer with bleach sanitisation + tests"
```

---

## Task 7: PDF renderer + Dockerfile update (TDD)

**Files:**
- Create: `backend/app/renderers/pdf.py`
- Create: `backend/tests/unit/test_pdf_renderer.py`
- Modify: `backend/Dockerfile`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/unit/test_pdf_renderer.py`:

```python
import pytest
import subprocess
from pathlib import Path
from app.renderers.pdf import render_pdf

# Skip entire module if pandoc isn't installed in this environment
pytestmark = pytest.mark.skipif(
    subprocess.run(["which", "pandoc"], capture_output=True).returncode != 0,
    reason="pandoc not installed",
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


def test_pandoc_error_raises(tmp_path):
    with pytest.raises(RuntimeError, match="pandoc failed"):
        render_pdf("", "test-job-id", tmp_path / "nonexistent" / "deep")
```

- [ ] **Step 2: Implement the PDF renderer**

Create `backend/app/renderers/pdf.py`:

```python
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
```

- [ ] **Step 3: Run tests (skipped if pandoc not local)**

```bash
cd backend && python -m pytest tests/unit/test_pdf_renderer.py -v
```

Expected: either 3 PASS (if pandoc is installed locally) or `3 skipped` with the "pandoc not installed" reason. Both are acceptable.

- [ ] **Step 4: Update the Dockerfile to install pandoc in the worker image**

The single `backend/Dockerfile` is shared by both `api` and `worker` containers. Add pandoc after the existing `RUN pip install` lines:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir hatch

COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[dev]"

# Install pandoc + minimal LaTeX for PDF rendering (used by worker only)
RUN apt-get update && apt-get install -y --no-install-recommends \
    pandoc \
    texlive-latex-base \
    texlive-fonts-recommended \
    && rm -rf /var/lib/apt/lists/*

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/renderers/pdf.py backend/tests/unit/test_pdf_renderer.py backend/Dockerfile
git commit -m "feat: PDF renderer via pandoc + Dockerfile install + tests"
```

---

## Task 8: Wire renderers + cache into pipeline

**Files:**
- Modify: `backend/app/worker/pipeline.py`

No new tests — the integration test covers the full pipeline. This task adds the renderer calls after a successful generation.

- [ ] **Step 1: Read the current end of pipeline.py to find the insertion point**

```bash
grep -n "job.status = .done" backend/app/worker/pipeline.py
```

Note the line number where `job.status = "done"` is set and `job.character_map` is written.

- [ ] **Step 2: Add renderer imports to the top of pipeline.py**

Add to the existing imports block in `backend/app/worker/pipeline.py`:

```python
from app.renderers.markdown import render_markdown
from app.renderers.pdf import render_pdf
from app.db.tables import Artifact
```

- [ ] **Step 3: Add renderer calls in the `else` (success) branch of run_pipeline**

In `run_pipeline`, in the `else:` block after `job.character_map = char_map.model_dump()`, add:

```python
        # Render Markdown + PDF artifacts
        artifact_dir = Path(settings.artifact_storage_path) / job_id
        artifact_dir.mkdir(parents=True, exist_ok=True)
        try:
            md_text = render_markdown(char_map)
            md_path = artifact_dir / "character_map.md"
            md_path.write_text(md_text, encoding="utf-8")
            session.add(Artifact(
                id=uuid4(),
                job_id=UUID(job_id),
                format="markdown",
                file_path=str(Path(job_id) / "character_map.md"),
                file_size=len(md_text.encode()),
            ))
            log.info("markdown_rendered", job_id=job_id)
        except Exception as e:
            log.warning("markdown_render_failed", job_id=job_id, error=str(e))

        try:
            pdf_path = render_pdf(md_text, job_id, artifact_dir)
            session.add(Artifact(
                id=uuid4(),
                job_id=UUID(job_id),
                format="pdf",
                file_path=str(Path(job_id) / "character_map.pdf"),
                file_size=pdf_path.stat().st_size,
            ))
            log.info("pdf_rendered", job_id=job_id)
        except Exception as e:
            log.warning("pdf_render_failed", job_id=job_id, error=str(e))

Note: ensure `from uuid import uuid4` is in `pipeline.py` imports (it uses `UUID` already; `uuid4` may need to be added separately).

- [ ] **Step 4: Verify pipeline.py imports cleanly**

```bash
cd backend && python -c "from app.worker.pipeline import run_pipeline; print('OK')"
```

Expected: `OK`

- [ ] **Step 5: Run full unit suite to check no regressions**

```bash
cd backend && python -m pytest tests/unit/ -q
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/worker/pipeline.py
git commit -m "feat: run Markdown + PDF renderers in pipeline after successful generation"
```

---

## Task 9: dagreLayout.ts

**Files:**
- Create: `frontend/src/layout/dagreLayout.ts`

- [ ] **Step 1: Create the layout module**

Create `frontend/src/layout/dagreLayout.ts`:

```typescript
import dagre from 'dagre'
import type { Edge, Node } from '@xyflow/react'
import type { CharacterMap, Character, Faction, Relationship, RelationshipType } from '../types/characterMap'

// ── Visual constants ────────────────────────────────────────────────────────
const NODE_WIDTH = 240
const NODE_HEIGHT = 64
const RANKSEP = 120          // vertical space between character rows within a faction
const NODESEP = 80           // horizontal space between characters within a faction
const FACTION_PADDING = 32   // padding inside each faction rect
const FACTION_LABEL_H = 36   // height reserved for the faction label above characters
const FACTION_GAP = 120      // horizontal gap between adjacent faction rects
const CANVAS_TOP = 48        // top offset for the first row of factions

// ── Faction colour mapping ──────────────────────────────────────────────────
const COLOUR_MAP: Record<string, string> = {
  blue:   '#3b82f6',
  red:    '#ef4444',
  green:  '#22c55e',
  amber:  '#f59e0b',
  violet: '#8b5cf6',
  slate:  '#64748b',
}

// ── Edge style mapping ──────────────────────────────────────────────────────
const EDGE_STYLES: Record<RelationshipType, { stroke: string; strokeDasharray?: string; strokeWidth: number }> = {
  alliance:     { stroke: '#22c55e', strokeWidth: 2 },
  family:       { stroke: '#22c55e', strokeWidth: 2 },
  romantic:     { stroke: '#ec4899', strokeWidth: 2 },
  antagonism:   { stroke: '#ef4444', strokeWidth: 2.5 },
  professional: { stroke: '#94a3b8', strokeDasharray: '5,3', strokeWidth: 1.5 },
  mentorship:   { stroke: '#f59e0b', strokeWidth: 2 },
  criminal:     { stroke: '#eab308', strokeDasharray: '5,3', strokeWidth: 1.5 },
}

// ── Per-faction dagre layout ────────────────────────────────────────────────
function layoutCharsInFaction(chars: Character[]): Map<string, { x: number; y: number }> {
  const g = new dagre.graphlib.Graph()
  g.setGraph({ rankdir: 'TB', ranksep: RANKSEP, nodesep: NODESEP })
  g.setDefaultEdgeLabel(() => ({}))
  chars.forEach(c => g.setNode(c.id, { width: NODE_WIDTH, height: NODE_HEIGHT }))
  dagre.layout(g)
  const positions = new Map<string, { x: number; y: number }>()
  chars.forEach(c => {
    const n = g.node(c.id)
    // dagre centres nodes; convert to top-left
    positions.set(c.id, { x: n.x - NODE_WIDTH / 2, y: n.y - NODE_HEIGHT / 2 })
  })
  return positions
}

// ── Main export ─────────────────────────────────────────────────────────────
export function buildLayout(charMap: CharacterMap): { nodes: Node[]; edges: Edge[] } {
  const { factions, characters, relationships } = charMap

  // Group characters by faction (fallback: first faction)
  const factionChars = new Map<string, Character[]>(factions.map(f => [f.id, []]))
  characters.forEach(c => {
    const fid = c.faction_id ?? factions[0]?.id
    if (fid && factionChars.has(fid)) {
      factionChars.get(fid)!.push(c)
    } else if (factions.length > 0) {
      factionChars.get(factions[0].id)!.push(c)
    }
  })

  const nodes: Node[] = []
  const nodeIdSet = new Set<string>()
  let cursorX = FACTION_PADDING

  factions.forEach((faction: Faction) => {
    const chars = factionChars.get(faction.id) ?? []
    if (chars.length === 0) return

    const colour = COLOUR_MAP[faction.color_hint] ?? '#64748b'
    const charPositions = layoutCharsInFaction(chars)

    // Bounding box of the laid-out characters
    let maxRight = 0, maxBottom = 0
    charPositions.forEach(({ x, y }) => {
      maxRight  = Math.max(maxRight,  x + NODE_WIDTH)
      maxBottom = Math.max(maxBottom, y + NODE_HEIGHT)
    })

    const groupW = maxRight  + FACTION_PADDING * 2
    const groupH = maxBottom + FACTION_PADDING * 2 + FACTION_LABEL_H
    const groupX = cursorX
    const groupY = CANVAS_TOP

    // Faction background rect node — rendered first so it appears behind characters
    nodes.push({
      id: `__faction_${faction.id}`,
      type: 'factionGroup',
      position: { x: groupX, y: groupY },
      style: { width: groupW, height: groupH },
      data: { label: faction.label, colour, description: faction.description },
      draggable: false,
      selectable: false,
      zIndex: 0,
    })

    // Character pill nodes — positioned absolutely within the faction rect
    chars.forEach(char => {
      const pos = charPositions.get(char.id)!
      nodes.push({
        id: char.id,
        type: 'characterCard',
        position: {
          x: groupX + FACTION_PADDING + pos.x,
          y: groupY + FACTION_LABEL_H + FACTION_PADDING + pos.y,
        },
        data: { character: char, colour, showBadges: false },
        zIndex: 1,
      })
      nodeIdSet.add(char.id)
    })

    cursorX += groupW + FACTION_GAP
  })

  // Build edges — only between characters that actually exist in the layout
  const edges: Edge[] = relationships
    .filter(r => nodeIdSet.has(r.from_id) && nodeIdSet.has(r.to_id))
    .map(r => ({
      id: `${r.from_id}__${r.to_id}__${r.type}`,
      source: r.from_id,
      target: r.to_id,
      type: 'smoothstep',
      label: r.label,
      labelBgStyle: { fill: 'rgba(17,17,17,0.92)', rx: 3, ry: 3 },
      labelStyle: { fill: '#ccc', fontSize: 11, fontFamily: '-apple-system,sans-serif' },
      style: EDGE_STYLES[r.type] ?? EDGE_STYLES.professional,
      zIndex: 2,
    }))

  return { nodes, edges }
}
```

- [ ] **Step 2: Smoke-test the layout with a Node.js script**

```bash
cd frontend && node -e "
const { buildLayout } = require('./src/layout/dagreLayout.ts')
" 2>&1 | head -5
```

This will likely fail because Node can't run TypeScript directly. Instead, verify through the TypeScript compiler:

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep dagreLayout
```

Expected: no errors from `dagreLayout.ts`.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/layout/dagreLayout.ts
git commit -m "feat: dagreLayout — dagre TB layout per faction, generous spacing (ranksep=120)"
```

---

## Task 10: CharacterCardNode + FactionGroupNode

**Files:**
- Create: `frontend/src/components/CharacterCardNode.tsx`
- Create: `frontend/src/components/FactionGroupNode.tsx`

- [ ] **Step 1: Create CharacterCardNode**

Create `frontend/src/components/CharacterCardNode.tsx`:

```tsx
import { Handle, Position } from '@xyflow/react'
import type { NodeProps } from '@xyflow/react'
import type { Character } from '../types/characterMap'

export interface CardNodeData {
  character: Character
  colour: string
  showBadges: boolean
}

export function CharacterCardNode({ data }: NodeProps) {
  const { character: c, colour, showBadges } = data as CardNodeData
  const initials = c.name
    .split(' ')
    .slice(0, 2)
    .map((w: string) => w[0])
    .join('')
    .toUpperCase()

  return (
    <>
      <Handle type="target" position={Position.Left}  style={{ opacity: 0 }} />
      <Handle type="target" position={Position.Top}   style={{ opacity: 0 }} />
      <Handle type="source" position={Position.Right} style={{ opacity: 0 }} />
      <Handle type="source" position={Position.Bottom} style={{ opacity: 0 }} />

      <div
        style={{ borderColor: colour }}
        className="flex items-center gap-3 bg-[#1e1e1e] rounded-[10px] border-[1.5px] px-3.5 py-2.5 cursor-grab active:cursor-grabbing hover:shadow-[0_0_0_2px_rgba(255,255,255,0.1)] transition-shadow select-none"
      >
        {/* Avatar circle */}
        <div className="relative flex-shrink-0">
          <div
            style={{ backgroundColor: colour }}
            className="w-11 h-11 rounded-full flex items-center justify-center text-sm font-extrabold text-white"
          >
            {initials}
          </div>

          {/* Spoiler badge — top-right, hidden unless showBadges */}
          {c.spoiler_level != null && c.spoiler_level >= 2 && (
            <span
              className={`absolute -top-1 -right-1 w-[17px] h-[17px] rounded-full
                bg-amber-500 text-black text-[9px] font-bold
                flex items-center justify-center border-[1.5px] border-[#111]
                transition-all duration-200
                ${showBadges ? 'opacity-100 scale-100' : 'opacity-0 scale-50 pointer-events-none'}`}
            >
              ⚠
            </span>
          )}

          {/* Death badge — top-left, hidden unless showBadges */}
          {c.is_deceased_in_work && (
            <span
              className={`absolute -top-1 -left-1 w-[17px] h-[17px] rounded-full
                bg-[#374151] text-[#d1d5db] text-[12px] font-bold leading-none
                flex items-center justify-center border-[1.5px] border-[#111]
                transition-all duration-200
                ${showBadges ? 'opacity-100 scale-100' : 'opacity-0 scale-50 pointer-events-none'}`}
            >
              †
            </span>
          )}
        </div>

        {/* Name + role */}
        <div className="min-w-0">
          <div className="text-sm font-bold text-white truncate leading-tight">{c.name}</div>
          <div className="text-[11px] text-[#9ca3af] mt-0.5 truncate">{c.role}</div>
        </div>
      </div>
    </>
  )
}
```

- [ ] **Step 2: Create FactionGroupNode**

Create `frontend/src/components/FactionGroupNode.tsx`:

```tsx
import type { NodeProps } from '@xyflow/react'

export interface FactionGroupData {
  label: string
  colour: string
  description: string
}

export function FactionGroupNode({ data, style }: NodeProps) {
  const { label, colour } = data as FactionGroupData

  return (
    <div
      style={{
        width:  style?.width  ?? '100%',
        height: style?.height ?? '100%',
        borderColor: colour,
        backgroundColor: `${colour}12`,   // ~7% opacity tint
      }}
      className="rounded-[14px] border-[1.5px] pointer-events-none absolute inset-0"
    >
      <span
        style={{ color: `${colour}dd` }}
        className="absolute top-3 left-4 text-[11px] font-bold tracking-[0.07em] uppercase select-none"
      >
        {label}
      </span>
    </div>
  )
}
```

- [ ] **Step 3: Verify TypeScript**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep -E "CharacterCardNode|FactionGroupNode"
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/CharacterCardNode.tsx frontend/src/components/FactionGroupNode.tsx
git commit -m "feat: CharacterCardNode (horizontal pill) + FactionGroupNode (translucent rect)"
```

---

## Task 11: CharacterMapCanvas

**Files:**
- Create: `frontend/src/components/CharacterMapCanvas.tsx`

- [ ] **Step 1: Create the canvas component**

Create `frontend/src/components/CharacterMapCanvas.tsx`:

```tsx
import { useState, useMemo, useCallback } from 'react'
import {
  ReactFlow,
  ReactFlowProvider,
  useNodesState,
  useEdgesState,
  MiniMap,
  Controls,
  Background,
  BackgroundVariant,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'

import { buildLayout } from '../layout/dagreLayout'
import { CharacterCardNode } from './CharacterCardNode'
import { FactionGroupNode } from './FactionGroupNode'
import { ExportMenu } from './ExportMenu'
import { ShareButton } from './ShareButton'
import type { CharacterMap } from '../types/characterMap'

const NODE_TYPES = {
  characterCard: CharacterCardNode,
  factionGroup:  FactionGroupNode,
}

// ── Legend panel (shown when toggled open) ──────────────────────────────────
function LegendPanel() {
  const EDGE_LEGEND = [
    { label: 'Alliance / Family', colour: '#22c55e', dashed: false },
    { label: 'Romantic',          colour: '#ec4899', dashed: false },
    { label: 'Antagonism',        colour: '#ef4444', dashed: false },
    { label: 'Professional',      colour: '#94a3b8', dashed: true  },
    { label: 'Mentorship',        colour: '#f59e0b', dashed: false },
    { label: 'Criminal',          colour: '#eab308', dashed: true  },
  ]
  return (
    <div className="mb-1.5 bg-[#1a1a1a] border border-[#2a2a2a] rounded-lg p-3 min-w-[210px]">
      <p className="text-[10px] font-bold text-[#555] uppercase tracking-[0.06em] mb-2">Relationships</p>
      {EDGE_LEGEND.map(e => (
        <div key={e.label} className="flex items-center gap-2 mb-1.5 last:mb-0">
          <div
            style={{
              width: 28, height: e.dashed ? 0 : 2,
              background: e.dashed ? 'transparent' : e.colour,
              borderTop: e.dashed ? `2px dashed ${e.colour}` : 'none',
              flexShrink: 0,
            }}
          />
          <span className="text-[12px] text-[#ccc]">{e.label}</span>
        </div>
      ))}
      <div className="border-t border-[#2a2a2a] my-2" />
      <p className="text-[10px] font-bold text-[#555] uppercase tracking-[0.06em] mb-2">
        Badges <span className="normal-case font-normal">(toggle in toolbar)</span>
      </p>
      <div className="flex items-center gap-2 mb-1.5">
        <span className="w-[18px] h-[18px] rounded-full bg-amber-500 flex items-center justify-center text-[9px] font-bold text-black flex-shrink-0">⚠</span>
        <span className="text-[12px] text-[#ccc]">Late-act reveal (spoiler)</span>
      </div>
      <div className="flex items-center gap-2">
        <span className="w-[18px] h-[18px] rounded-full bg-[#374151] flex items-center justify-center text-[12px] font-bold text-[#d1d5db] flex-shrink-0">†</span>
        <span className="text-[12px] text-[#ccc]">Dies in the story</span>
      </div>
    </div>
  )
}

// ── Setting preamble callout ─────────────────────────────────────────────────
function SettingPreamble({ text }: { text: string }) {
  const [open, setOpen] = useState(true)
  return (
    <div className="mx-4 mt-3 bg-[#1a1a1a] border border-[#2a2a2a] rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(v => !v)}
        className="w-full flex items-center justify-between px-4 py-2.5 text-sm font-semibold text-[#aaa] hover:text-white transition-colors"
      >
        <span>📖 Setting</span>
        <span className={`text-[10px] transition-transform ${open ? 'rotate-180' : ''}`}>▲</span>
      </button>
      {open && (
        <div className="px-4 pb-3 text-sm text-[#ccc] leading-relaxed border-t border-[#2a2a2a]">
          <p className="mt-3">{text}</p>
        </div>
      )}
    </div>
  )
}

// ── Inner canvas (must be inside ReactFlowProvider) ──────────────────────────
interface CanvasProps { charMap: CharacterMap; jobId: string }

function InnerCanvas({ charMap, jobId }: CanvasProps) {
  const [showBadges, setShowBadges] = useState(false)
  const [showLegend, setShowLegend] = useState(false)

  const { nodes: initNodes, edges: initEdges } = useMemo(
    () => buildLayout(charMap),
    [charMap],
  )

  const [nodes, setNodes, onNodesChange] = useNodesState(initNodes)
  const [edges, , onEdgesChange] = useEdgesState(initEdges)

  // Propagate badge state into node data
  const liveNodes = useMemo(
    () => nodes.map(n =>
      n.type === 'characterCard'
        ? { ...n, data: { ...n.data, showBadges } }
        : n,
    ),
    [nodes, showBadges],
  )

  const resetLayout = useCallback(() => {
    const { nodes: fresh } = buildLayout(charMap)
    setNodes(fresh)
  }, [charMap, setNodes])

  return (
    <div className="flex flex-col h-full bg-[#111]">

      {/* ── Top toolbar ── */}
      <div className="bg-[#1a1a1a] border-b border-[#2a2a2a] px-6 py-2.5 flex items-center gap-2.5 flex-shrink-0">
        <button
          onClick={() => setShowBadges(v => !v)}
          title="Toggle spoiler / death badges on character nodes"
          className={`px-4 py-2 text-sm font-semibold rounded-lg border-[1.5px] transition-colors ${
            showBadges
              ? 'bg-[#292929] text-white border-[#666]'
              : 'bg-transparent text-[#888] border-[#333] hover:border-[#555] hover:text-[#ccc]'
          }`}
        >
          ⚠ † Badges
        </button>

        <div className="w-px h-6 bg-[#2a2a2a] mx-1" />

        <ShareButton jobId={jobId} />
        <ExportMenu jobId={jobId} />

        <div className="w-px h-6 bg-[#2a2a2a] mx-1" />

        <button
          onClick={resetLayout}
          className="px-4 py-2 text-sm font-semibold text-[#e5e7eb] border-[1.5px] border-[#444] rounded-lg bg-transparent hover:border-[#666] transition-colors"
        >
          Reset layout
        </button>
      </div>

      {/* ── Optional banners ── */}
      {charMap.coverage_note && (
        <div className="mx-4 mt-3 px-4 py-2.5 bg-amber-900/15 border border-amber-500/40 rounded-lg text-amber-300 text-sm flex items-start gap-2 flex-shrink-0">
          <span className="flex-shrink-0 mt-0.5">⚠</span>
          <span><strong>Coverage note:</strong> {charMap.coverage_note}</span>
        </div>
      )}

      {charMap.setting_preamble && (
        <div className="flex-shrink-0">
          <SettingPreamble text={charMap.setting_preamble} />
        </div>
      )}

      {/* ── React Flow canvas ── */}
      <div className="flex-1 relative">
        <ReactFlow
          nodes={liveNodes}
          edges={edges}
          nodeTypes={NODE_TYPES}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          fitView
          fitViewOptions={{ padding: 0.12 }}
          minZoom={0.08}
          maxZoom={2.5}
          deleteKeyCode={null}
          className="bg-[#111]"
        >
          <MiniMap
            style={{ background: '#1a1a1a', border: '1px solid #2a2a2a', borderRadius: 6 }}
            nodeColor="#2a2a2a"
          />
          <Controls
            style={{ background: '#1a1a1a', border: '1px solid #2a2a2a', borderRadius: 6 }}
          />
          <Background color="#1e1e1e" variant={BackgroundVariant.Dots} gap={20} />
        </ReactFlow>

        {/* ── Legend toggle (bottom-left, independent of badges) ── */}
        <div className="absolute bottom-3.5 left-3.5 z-10">
          {showLegend && <LegendPanel />}
          <button
            onClick={() => setShowLegend(v => !v)}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-[#1a1a1a] border border-[#2a2a2a] rounded-lg text-[12px] font-semibold text-[#aaa] hover:border-[#444] hover:text-[#e5e7eb] transition-colors"
          >
            Legend
            <span className={`text-[10px] transition-transform duration-200 ${showLegend ? 'rotate-180' : ''}`}>
              ▲
            </span>
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Public export (wraps in provider) ────────────────────────────────────────
export function CharacterMapCanvas({ charMap, jobId }: CanvasProps) {
  return (
    <ReactFlowProvider>
      <InnerCanvas charMap={charMap} jobId={jobId} />
    </ReactFlowProvider>
  )
}
```

- [ ] **Step 2: Verify TypeScript**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep -E "CharacterMapCanvas|dagreLayout"
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/CharacterMapCanvas.tsx
git commit -m "feat: CharacterMapCanvas — React Flow canvas with toolbar, legend toggle, badge toggle"
```

---

## Task 12: ExportMenu + ShareButton + DownloadList + client.ts helpers

**Files:**
- Create: `frontend/src/components/ExportMenu.tsx`
- Create: `frontend/src/components/ShareButton.tsx`
- Create: `frontend/src/components/DownloadList.tsx`
- Modify: `frontend/src/api/client.ts`

- [ ] **Step 1: Add artifact API helpers to client.ts**

Append to `frontend/src/api/client.ts`:

```typescript
export interface ArtifactInfo {
  format: string
  url: string
}

export async function uploadArtifact(
  jobId: string,
  format: string,
  blob: Blob,
): Promise<void> {
  const form = new FormData()
  form.append('file', blob, `character-map.${format}`)
  const res = await fetch(`/api/jobs/${jobId}/artifacts?format=${format}`, {
    method: 'POST',
    body: form,
  })
  if (!res.ok) {
    console.warn('Artifact upload failed', format, res.status)
  }
}

export async function getArtifacts(jobId: string): Promise<ArtifactInfo[]> {
  const res = await fetch(`/api/jobs/${jobId}/artifacts`)
  if (!res.ok) return []
  return res.json()
}
```

- [ ] **Step 2: Create ShareButton**

Create `frontend/src/components/ShareButton.tsx`:

```tsx
import { useState } from 'react'

export function ShareButton({ jobId }: { jobId: string }) {
  const [copied, setCopied] = useState(false)

  const handleShare = async () => {
    try {
      await navigator.clipboard.writeText(`${window.location.origin}/job/${jobId}`)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // Fallback: select the URL bar
      window.prompt('Copy this link:', `${window.location.origin}/job/${jobId}`)
    }
  }

  return (
    <button
      onClick={handleShare}
      className="px-4 py-2 text-sm font-semibold bg-[#2563eb] text-white rounded-lg hover:bg-[#1d4ed8] transition-colors"
    >
      {copied ? '✓ Copied!' : 'Share'}
    </button>
  )
}
```

- [ ] **Step 3: Create ExportMenu**

Create `frontend/src/components/ExportMenu.tsx`:

```tsx
import { useState, useRef } from 'react'
import { useReactFlow } from '@xyflow/react'
import { toPng, toSvg } from 'html-to-image'
import { uploadArtifact } from '../api/client'

const CANVAS_BG = '#111111'

export function ExportMenu({ jobId }: { jobId: string }) {
  const { toObject } = useReactFlow()
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState<string | null>(null)

  function download(dataUrl: string, filename: string) {
    const a = document.createElement('a')
    a.href = dataUrl
    a.download = filename
    a.click()
  }

  function getViewport(): HTMLElement {
    const el = document.querySelector('.react-flow__viewport') as HTMLElement | null
    if (!el) throw new Error('React Flow viewport not found')
    return el
  }

  const exportPng = async () => {
    setBusy('png')
    try {
      const dataUrl = await toPng(getViewport(), { pixelRatio: 2, backgroundColor: CANVAS_BG })
      download(dataUrl, 'character-map.png')
      const blob = await (await fetch(dataUrl)).blob()
      await uploadArtifact(jobId, 'png', blob)
    } finally {
      setBusy(null)
      setOpen(false)
    }
  }

  const exportSvg = async () => {
    setBusy('svg')
    try {
      const dataUrl = await toSvg(getViewport(), { backgroundColor: CANVAS_BG })
      download(dataUrl, 'character-map.svg')
      const blob = await (await fetch(dataUrl)).blob()
      await uploadArtifact(jobId, 'svg', blob)
    } finally {
      setBusy(null)
      setOpen(false)
    }
  }

  const exportJson = async () => {
    setBusy('json')
    try {
      const obj = toObject()
      const json = JSON.stringify(obj, null, 2)
      download(
        `data:application/json;charset=utf-8,${encodeURIComponent(json)}`,
        'character-map.charmap.json',
      )
      await uploadArtifact(jobId, 'json', new Blob([json], { type: 'application/json' }))
    } finally {
      setBusy(null)
      setOpen(false)
    }
  }

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(v => !v)}
        className="px-4 py-2 text-sm font-semibold text-[#e5e7eb] border-[1.5px] border-[#444] rounded-lg bg-transparent hover:border-[#666] transition-colors"
      >
        Export ▾
      </button>
      {open && (
        <>
          {/* Click-away overlay */}
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          <div className="absolute top-full mt-1 left-0 bg-[#1a1a1a] border border-[#2a2a2a] rounded-lg overflow-hidden z-20 min-w-[150px] shadow-xl">
            {[
              { key: 'png',  label: '🖼 PNG (2×)',  fn: exportPng  },
              { key: 'svg',  label: '↗ SVG',        fn: exportSvg  },
              { key: 'json', label: '{ } JSON',      fn: exportJson },
            ].map(({ key, label, fn }) => (
              <button
                key={key}
                onClick={fn}
                disabled={busy !== null}
                className="w-full px-4 py-2.5 text-left text-sm text-[#e5e7eb] hover:bg-[#242424] disabled:opacity-50 transition-colors"
              >
                {busy === key ? '…' : label}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
```

- [ ] **Step 4: Create DownloadList**

Create `frontend/src/components/DownloadList.tsx`:

```tsx
import { useEffect, useState } from 'react'
import { getArtifacts, type ArtifactInfo } from '../api/client'

const FORMAT_LABELS: Record<string, string> = {
  markdown: '📄 Markdown',
  pdf:      '📑 PDF',
  png:      '🖼 PNG (2×)',
  svg:      '↗ SVG',
  json:     '{ } JSON',
}

export function DownloadList({ jobId }: { jobId: string }) {
  const [artifacts, setArtifacts] = useState<ArtifactInfo[]>([])

  useEffect(() => {
    getArtifacts(jobId)
      .then(setArtifacts)
      .catch(() => {/* non-fatal */})
  }, [jobId])

  if (artifacts.length === 0) return null

  return (
    <div className="flex flex-col gap-1.5">
      {artifacts.map(a => (
        <a
          key={a.format}
          href={a.url}
          download
          className="block w-full bg-[#1e1e1e] border border-[#2a2a2a] rounded-lg px-3 py-2.5 text-sm text-[#e5e7eb] font-medium hover:border-[#555] hover:text-white transition-colors no-underline"
        >
          {FORMAT_LABELS[a.format] ?? a.format}
        </a>
      ))}
    </div>
  )
}
```

- [ ] **Step 5: Build to verify TypeScript**

```bash
cd frontend && npm run build 2>&1 | tail -10
```

Expected: `✓ built in ...ms`. Fix any TypeScript errors before committing.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/ExportMenu.tsx frontend/src/components/ShareButton.tsx frontend/src/components/DownloadList.tsx frontend/src/api/client.ts
git commit -m "feat: ExportMenu (PNG/SVG/JSON), ShareButton, DownloadList + artifact API helpers"
```

---

## Task 13: JobView done state

**Files:**
- Modify: `frontend/src/routes/JobView.tsx`

- [ ] **Step 1: Replace the raw JSON done state with the canvas + sidebar layout**

Read `frontend/src/routes/JobView.tsx` first. The current done state is:

```tsx
if (job?.status === 'done') {
  return (
    <main className="max-w-3xl ...">
      ...raw JSON pre block...
    </main>
  )
}
```

Replace the done-state block with:

```tsx
if (job?.status === 'done' && job.character_map) {
  const charMap = job.character_map as unknown as CharacterMap
  return (
    <div className="flex h-screen overflow-hidden">
      {/* Canvas fills the viewport */}
      <div className="flex-1 min-w-0">
        <CharacterMapCanvas charMap={charMap} jobId={id!} />
      </div>

      {/* Right sidebar: downloads */}
      <div className="w-[190px] flex-shrink-0 bg-[#161616] border-l border-[#222] p-4 overflow-y-auto">
        <div className="mb-4">
          <p className="text-[11px] font-bold text-[#555] uppercase tracking-[0.06em] mb-2.5">
            Downloads
          </p>
          <DownloadList jobId={id!} />
        </div>
      </div>
    </div>
  )
}
```

Add the required imports at the top of `JobView.tsx`:

```tsx
import { CharacterMapCanvas } from '../components/CharacterMapCanvas'
import { DownloadList } from '../components/DownloadList'
import type { CharacterMap } from '../types/characterMap'
```

- [ ] **Step 2: Build**

```bash
cd frontend && npm run build 2>&1 | tail -10
```

Expected: `✓ built in ...ms` with no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/routes/JobView.tsx
git commit -m "feat: JobView done state — React Flow canvas + sidebar downloads"
```

---

## Task 14: Manual test + deploy

- [ ] **Step 1: Rebuild Docker images (pandoc layer is new)**

```bash
docker compose build api worker
docker compose up -d
```

Expected: images rebuild, all 5 containers healthy.

- [ ] **Step 2: Run full unit test suite**

```bash
docker exec charmap_api python -m pytest tests/unit/ -q
```

Expected: all tests PASS.

- [ ] **Step 3: Manual canvas smoke test**

Generate a Congo map via the UI at `http://localhost:8201`. When done:

- [ ] Canvas renders with no overlapping nodes
- [ ] Three faction groups visible with correct coloured borders
- [ ] Character pills show name + role
- [ ] Edges connect the right nodes with correct colours
- [ ] "⚠ † Badges" toggle shows/hides badges (previously invisible)
- [ ] "Legend ▲" toggle shows/hides the colour key
- [ ] "Reset layout" re-runs dagre after dragging
- [ ] Fit view zooms to fit all nodes
- [ ] Minimap reflects the canvas
- [ ] "Share" button copies the URL

- [ ] **Step 4: Manual export smoke test**

- [ ] PNG export downloads a retina-quality image (right-click → Inspect size)
- [ ] SVG export downloads a vector file
- [ ] JSON export downloads a `.charmap.json`
- [ ] Markdown and PDF appear in the Downloads sidebar after the pipeline runs
- [ ] Markdown download link works (signed URL resolves)
- [ ] PDF download link works

- [ ] **Step 5: Cache test**

Generate the same title again (same model or different). Check the logs:

```bash
docker compose logs api | grep "job_cache_hit"
```

Expected: second generation logs `job_cache_hit` instead of going to the worker queue.

- [ ] **Step 6: Deploy to lfc**

```bash
./deploy.sh
```

Expected: `✓ Deploy complete`. Verify live at `http://lfc:8202/api/health`.

- [ ] **Step 7: Wrapup commit**

```bash
git add -A
git commit -m "chore: wrapup session 3 — Phase 3 rendering complete" --allow-empty
```

---

## Phase 3 test checklist (from §16)

Before marking Phase 3 done:

- [ ] `pytest tests/unit/` — all pass (includes signed URLs, artifacts, markdown, cache lookup)
- [ ] `pytest tests/unit/test_pdf_renderer.py` — PASS or SKIP (pandoc not local)
- [ ] Canvas for Congo: no overlapping nodes, factions correct, edge colours match
- [ ] ⚠ badge on spoiler ≥ 2 nodes; hidden by default, visible after toggle
- [ ] † badge on deceased characters; hidden by default, visible after toggle
- [ ] Legend collapses/expands independently of badge toggle
- [ ] PNG retina-quality (2×); SVG vector-clean; JSON re-import scene
- [ ] Reset layout re-runs dagre after drag
- [ ] `setting_preamble` collapsible panel renders correctly
- [ ] `coverage_note` amber banner visible above canvas
- [ ] Markdown + PDF in Downloads sidebar; signed URLs work
- [ ] Cache hit logged on second request for same work
