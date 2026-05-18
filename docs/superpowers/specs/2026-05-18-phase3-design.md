# Phase 3 — Rendering: Design

**Date:** 2026-05-18
**Status:** Approved
**Spec reference:** SPEC.md §6, §16 Phase 3 (deliverables 17–25)

---

## Scope

Phase 3 wires up all rendering: the React Flow interactive canvas (the primary product deliverable), server-side Markdown and PDF renderers, client-side PNG/SVG/JSON exports, artifact storage, and result caching. The job view's "done" state changes from "raw JSON" to a fully interactive character map.

---

## New feature: result caching

Not in the original spec — added in design. When a job is submitted, before enqueueing to RQ, check for an existing `done` non-deleted job with the same `(resolved_id, spoiler_mode)`. If one exists, pick the result from the highest-quality model available (ranking: Opus 4.7 → Sonnet 4.6 → GPT-5.5 → Gemini 2.5 Pro → Haiku 4.5), copy its `character_map` to a new job record, mark it immediately `done`, and skip the LLM call entirely.

- Cache hit cost: $0 (recorded as such for the cost guard)
- The job page shows the model that actually generated the cached result
- Cache key is `(resolved_id, spoiler_mode)` — no prompt version tracking (prompt changes are rare; old cached entries are replaced naturally over time)
- Requires a new index: `(resolved_id, spoiler_mode, status)` where `status = 'done'`
- No new DB columns needed

---

## Architecture: new files

### Backend

| File | Purpose |
|------|---------|
| `backend/app/renderers/markdown.py` | `render_markdown(char_map: CharacterMap) -> str` |
| `backend/app/renderers/pdf.py` | `render_pdf(md_text: str, job_id: str) -> Path` — shells to pandoc |
| `backend/app/routes/artifacts.py` | `POST/GET /api/jobs/:id/artifacts`, `GET /api/artifacts/:job_id/:filename` |
| `backend/renderers/pdf/template.tex` | Minimal pandoc LaTeX template (Phase 3: default pandoc template; custom in Phase 6) |

### Frontend

| File | Purpose |
|------|---------|
| `frontend/src/layout/dagreLayout.ts` | Builds React Flow nodes + edges with positions from CharacterMap JSON |
| `frontend/src/components/CharacterMapCanvas.tsx` | React Flow wrapper — mounts everything, minimap, controls |
| `frontend/src/components/CharacterCardNode.tsx` | Horizontal pill node |
| `frontend/src/components/FactionGroupNode.tsx` | Translucent labelled background rect |
| `frontend/src/components/ExportMenu.tsx` | PNG/SVG/JSON export + POST to backend |
| `frontend/src/components/ShareButton.tsx` | Clipboard copy of `/job/:id` |
| `frontend/src/components/DownloadList.tsx` | Sidebar — Markdown + PDF download buttons |

### Modified files

| File | Change |
|------|--------|
| `frontend/src/routes/JobView.tsx` | Done state: canvas + top toolbar + right sidebar |
| `frontend/src/api/client.ts` | `uploadArtifact`, `getArtifacts` |
| `frontend/package.json` | Add `@xyflow/react`, `dagre`, `@types/dagre`, `html-to-image` |
| `backend/app/worker/pipeline.py` | Run Markdown + PDF renderers after LLM step; add cache lookup before enqueue |
| `backend/app/routes/jobs.py` | Cache lookup in `POST /api/jobs` |
| `backend/app/main.py` | Include artifacts router |
| `backend/Dockerfile` | Add `pandoc texlive-latex-base texlive-fonts-recommended` |
| `backend/pyproject.toml` | Add `bleach>=6.0` |

---

## Canvas design

### Visual philosophy

The map is the product. It should look like a magazine diagram — spacious, readable at a glance, with clear visual hierarchy. Because the canvas is zoomable, there is no need to compress. Err on the side of generous spacing.

### Layout parameters (dagre)

- **Direction:** top-to-bottom (`TB`) within factions, left-to-right between factions
- **`ranksep`:** 120px (spec default is 80; increased for breathing room)
- **`nodesep`:** 80px (spec default is 60)
- **Inter-faction gap:** 120px minimum between faction group bounding boxes
- **Faction internal padding:** 32px on all sides around characters

### `CharacterCardNode` — horizontal pill

```
┌─────────────────────────────────────────────┐  ← faction-coloured border, 1.5px
│  ┌────────┐   Name (bold, white, 14px)       │
│  │  ini- │   Role (muted grey, 12px)         │
│  │  tials│                                   │
│  └────────┘                                  │
└─────────────────────────────────────────────┘
```

- **Avatar:** 44px circular, faction-coloured background, white initials. Phase 4 replaces initials with actor headshot.
- **Name:** white, 14px, bold
- **Role:** `#9ca3af`, 12px
- **Node width:** 240px minimum
- **Faction border colour** on the pill border and avatar background
- **Badges** (hidden by default, shown via toolbar toggle):
  - **⚠** amber — `spoiler_level >= 2` (late-act reveal)
  - **†** slate — `is_deceased_in_work: true`
  - Badges animate in with a scale+opacity transition when toggled

### `FactionGroupNode` — background rect

- Translucent faction-coloured fill: `rgba(faction_rgb, 0.07)`
- Faction-coloured border: `1.5px solid`
- Faction label: `11px`, `font-weight: 700`, `text-transform: uppercase`, `letter-spacing: 0.07em`, faction light colour
- Border radius: `14px`
- Internal padding: `32px`
- Not draggable independently — characters drag within it

### Edge styling

Smooth bezier curves (`type: 'smoothstep'`). Labels at the midpoint with a semi-transparent dark background (`rgba(17,17,17,0.92)`) so they read over any faction colour. Curves are wide enough to be visually clear even at default zoom.

| Relationship type | Colour | Style |
|------------------|--------|-------|
| alliance / family | `#22c55e` green | solid, 2px |
| romantic | `#ec4899` pink | solid, 2px |
| antagonism | `#ef4444` red | solid, 2.5px |
| professional | `#94a3b8` slate | dashed 5,3 — 1.5px |
| mentorship | `#f59e0b` amber | solid, 2px |
| criminal | `#eab308` yellow | dashed 5,3 — 1.5px |

### Legend toggle + badges toggle (independent)

Two independent controls:
1. **"⚠ † Badges" button** — in the toolbar, default off. Toggles the spoiler and death badges on all avatar circles simultaneously with a CSS transition. Button highlights when active.
2. **"Legend ▲" button** — floating at bottom-left of the canvas, default collapsed. Expands to show relationship colour key + badge explanations.

The legend's badge section includes a note pointing to the toolbar toggle.

### Canvas controls

- **Toolbar (top):** Share · Export ▾ · "⚠ † Badges" toggle · Reset layout · Fit view
- **Bottom-right:** zoom in · zoom out · fit-view icon · minimap (120×80px)
- **Bottom-left:** Legend toggle

### Optional banners (above canvas, below toolbar)

- **`coverage_note`** — amber banner: "⚠ Coverage note: {text}" — shown before canvas so the reader sees it first
- **`setting_preamble`** — collapsible callout panel (default expanded on first load), collapses on click. Visually distinct from character descriptions.

---

## Job done page layout (option A)

```
┌────────────────────────────────────────────────────────────┐
│ ← Back  │ ⚠† Badges │ Share │ Export ▾ │ Reset │ Fit view │  ← toolbar
├────────────────────────────────────────────────────────────┤
│                                           │  Downloads     │
│   [coverage_note amber banner]            │  📄 Markdown   │
│                                           │  📑 PDF        │
│   [setting_preamble callout, collapse]    │                │
│                                           │  Canvas export │
│                                           │  🖼 PNG (2×)   │
│   React Flow canvas (fills remaining)     │  ↗ SVG        │
│                                           │  {} JSON       │
│                                           │                │
│   [Legend ▲]        [zoom] [minimap]      │                │
└────────────────────────────────────────────────────────────┘
```

- Canvas fills the remaining space — no fixed height
- Right sidebar: 190px fixed, contains Downloads (Markdown, PDF via signed URLs) and Canvas exports (PNG/SVG/JSON via client-side generation)
- Sidebar scrolls independently if content overflows

---

## Backend: Markdown renderer

`render_markdown(char_map: CharacterMap) -> str`

Structure:
1. `# {title}` / `## {subtitle}`
2. Blurb paragraph
3. `coverage_note` (if present): `> ⚠ Coverage note: {text}`
4. `setting_preamble` (if present): as its own `## Setting` section
5. One `## {faction.label}` section per faction with character paragraphs
6. `## Relationships` — table with columns: From | To | Type | Notes
7. Footer: "This map contains full spoilers. Generated by Character Map Generator."

All text passed through `bleach.clean()` with no tags allowed before writing to disk, to strip any LLM-injected HTML/script content.

---

## Backend: PDF renderer

`render_pdf(md_text: str, job_id: str) -> Path`

- Calls `pandoc` via `subprocess.run()` with `--pdf-engine=pdflatex`
- Phase 3: default pandoc template (no custom LaTeX — polish in Phase 6)
- Output written to `ARTIFACT_STORAGE_PATH/<job_id>/character_map.pdf`
- Returns the output path; raises `RuntimeError` if pandoc exits non-zero

Pandoc + TeX installed in **worker Dockerfile only** (not API image):
```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    pandoc texlive-latex-base texlive-fonts-recommended \
    && rm -rf /var/lib/apt/lists/*
```

---

## Backend: artifact endpoints + signed URLs

**`POST /api/jobs/:id/artifacts`** — frontend uploads blob (PNG/SVG/JSON) after canvas renders. Body: `multipart/form-data` with `format` field and file data. Stored at `ARTIFACT_STORAGE_PATH/<job_id>/<format>.<ext>`. Creates `Artifact` DB record.

**`GET /api/jobs/:id/artifacts`** — returns list of artifacts with signed download URLs:
```json
[
  {"format": "markdown", "url": "/api/artifacts/<job_id>/character_map.md?sig=<hmac>&exp=<ts>"},
  {"format": "pdf",      "url": "/api/artifacts/<job_id>/character_map.pdf?sig=<hmac>&exp=<ts>"}
]
```
HMAC-SHA256, 7-day expiry, key from `settings.artifact_signing_key`.

**`GET /api/artifacts/:job_id/:filename`** — verifies `sig` + `exp` query params, serves file bytes with appropriate `Content-Type`. Returns 403 on invalid/expired signature, 404 if file not found.

---

## Result caching

In `POST /api/jobs`, before enqueueing:

```python
# find_best_cached_job: SELECT FROM jobs WHERE resolved_id=$1 AND spoiler_mode=$2
#   AND status='done' AND deleted_at IS NULL
#   ORDER BY model_rank ASC LIMIT 1
# (model_rank is a CASE expression matching the quality ranking below)
cached = await find_best_cached_job(session, resolved_id, spoiler_mode="full")
if cached:
    job = Job(..., status="done", character_map=cached.character_map,
              completed_at=now(), estimated_cost_usd=0, model=cached.model)
    session.add(job)
    await session.commit()
    return JobCreateResponse(job_id=str(job.id))
# else: proceed to RQ enqueue
```

Model quality ranking (best first):
1. `claude-opus-4-7`
2. `claude-sonnet-4-6`
3. `gpt-5.5`
4. `gemini-2.5-pro`
5. `claude-haiku-4-5-20251001`

If an Opus result exists for a work, every subsequent request for that work (regardless of model chosen) gets the Opus map instantly at $0 cost.

New index: `CREATE INDEX idx_jobs_cache ON jobs (resolved_id, spoiler_mode, status) WHERE status = 'done' AND deleted_at IS NULL;`

New Alembic migration required for the index.

---

## Tests

### Backend unit tests

| Test file | Covers |
|-----------|--------|
| `tests/unit/test_markdown_renderer.py` | H2 per faction, setting_preamble first, coverage_note after blurb, bleach strips `<script>` |
| `tests/unit/test_pdf_renderer.py` | Non-empty `.pdf` from fixture (skipped if pandoc not installed) |
| `tests/unit/test_artifacts.py` | HMAC signature round-trip, expiry rejection, invalid sig → 403 |
| `tests/unit/test_cache_lookup.py` | Opus hit → returns Opus; Sonnet only → returns Sonnet; no hits → None; deleted job → not returned |

### Manual canvas tests (§16)

- Congo canvas: no overlapping nodes, faction grouping correct, edge colours match type table
- Badges off by default; toggle shows ⚠ on spoiler nodes, † on Travis
- Legend collapsed by default; toggle expands with full key
- Reset layout re-runs dagre after manual drag
- Fit view resets viewport pan/zoom
- `setting_preamble` callout collapses and expands
- `coverage_note` amber banner visible above canvas
- PNG export is retina quality (2×); SVG is vector-clean; JSON re-import restores scene

---

## Out of scope for Phase 3

- Actor headshots (Phase 4) — avatars show initials only
- Custom LaTeX PDF template (Phase 6 polish)
- Re-import of JSON scene (Phase 3 produces the JSON; re-import UI is Phase 6)
- Cache invalidation on prompt change (deferred; entries replaced naturally)
