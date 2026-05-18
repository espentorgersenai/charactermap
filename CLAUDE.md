# CLAUDE.md — Character Map Generator

A web app that generates visual, interactive character maps for books and films using LLMs.

**Full spec:** `SPEC.md` — read it before doing anything. **Phase 1 complete. Implement Phase 2 next** unless asked otherwise.

---

## Project Overview

Users enter a book or film title, pick a model, and get back an interactive React Flow character map — nodes per character, edges per relationship, faction groupings, actor headshots for adaptations. Deployable artifacts: interactive web view, PNG, SVG, Markdown, PDF, JSON.

Key constraints:
- v1 is full-spoiler only. Spoiler-free mode is v1.5.
- Desktop-only at launch. Architecture must not preclude a future React Native / Capacitor shell.
- Runs on **lfc** (home GPU server) behind the VPS nginx. Ports: API `8200`, frontend `8201`.
- LLM cost is capped daily (`DAILY_COST_LIMIT_USD`, default $5). Never remove the cost guard.

---

## Project Management

Cards live on **Planka** → [kanban.torgersen.ai](https://kanban.torgersen.ai) — project: *Character Map*, board: *Character Map*.

Every card must have:
- One **category** label: `bug` · `feature` · `infra` · `tech-debt` · `verify-later` · `scale-test`
- One or more **svc:** labels: `svc:api` · `svc:worker` · `svc:frontend` · `svc:db` · `svc:llm` · `svc:resolve`
- One **phase:** label: `phase:1` … `phase:7`

Workflow: **ToDo → In Progress → Completed**. Use *Waiting* for cards blocked on an external dependency (API key, third-party outage).

**Agent responsibilities for Planka — every session:**
- **At session start:** the chronicle / session brief shows the top ToDo cards. If a card on the brief matches the work the user asks for, work that card.
- **When a card's work ships:** move it to *Completed* (don't leave it in *ToDo* or *In Progress*).
- **When new work is discovered:** file a new card. This includes: deferred parts of the current task, bugs found while testing, follow-ups for "we'll do that later" decisions. Set the three required labels (category + svc + phase). Don't accumulate undocumented TODOs in your head — file them.
- **Tools:** use the `mcp__planka__*` tools. `cards.update` requires `position` when moving between lists (422 without it). `cards.create` requires `type: "project"` (400 without it). Both quirks already in *Known Quirks* below.
- **Bias toward filing:** if uncertain whether something deserves a card, file it. A short Planka card is cheaper than re-discovering the same gap two sessions later.

---

## Stack

| Layer | Tech |
|-------|------|
| Frontend | React 18 + TypeScript + Vite |
| UI | Tailwind CSS + shadcn/ui (system `prefers-color-scheme`) |
| Map canvas | React Flow (`@xyflow/react`) + dagre |
| Canvas exports | `html-to-image` (PNG), `toSvg()` (SVG), `toObject()` (JSON) |
| State | TanStack Query (API) + Zustand (UI) |
| Backend | Python 3.12 + FastAPI + uvicorn (4 workers) |
| Job queue | Redis + RQ |
| Database | PostgreSQL 16 + SQLAlchemy async + Alembic |
| Cache | Redis (queue + rate limits + metadata cache) |
| Email | Resend |
| Captcha | Cloudflare Turnstile |
| Deployment | lfc (home server) → Docker Compose → VPS nginx proxy |
| LLM providers | Anthropic · OpenAI · Google (common `LLMClient` protocol) |

---

## Critical Rules

- **Never remove the cost guard.** `DAILY_COST_LIMIT_USD` is the financial kill-switch. Don't bypass it, even in tests.
- **Never fabricate character data.** The LLM prompt's prime directive is "omit when uncertain." A thin correct map beats a complete invented one. See §5.1 of SPEC.md.
- **`acknowledged_spoilers: true` is a hard gate.** `POST /api/jobs` must reject any request where this field is false or missing. No exceptions.
- **No nginx in the charactermap docker-compose.** TLS termination is handled by the VPS usv-fleet nginx. Do not add an nginx service to docker-compose.yml.
- **Wrap all user input before LLM calls.** Title queries, actor override text — everything goes inside `<user_input>...</user_input>` tags. See §10.6.
- **`spoiler_level` must be present on every character and relationship.** Missing → default to `3` + log warning. Never silently drop the field.

---

## Development

### Running locally

```bash
# Start all services
docker compose up -d

# Run migrations
docker exec charmap_api alembic upgrade head

# Tail logs
docker compose logs -f api worker
```

### Deploying to lfc

```bash
./deploy.sh   # SSH → lfc, docker compose pull + up -d + migrations
```

### Prompt iteration (bypass the web stack)

```bash
python scripts/dev-generate.py \
  --title "Congo" --author "Michael Crichton" --year 1980 --work-type book \
  --model claude-sonnet-4-6

# Run the full golden set
python scripts/run_golden_set.py --model claude-sonnet-4-6
```

Outputs land in `tuning/run-<timestamp>/`. See §19 of SPEC.md for the full prompt engineering workflow.

---

## Verification

Each phase has a test checkpoint defined in §16 of SPEC.md. At minimum before marking a phase done:

**Automated:**
```bash
pytest backend/tests/
```

**Phase 1 manual smoke:**
- Form restores model + formats from localStorage; email is not restored
- Acknowledgement unchecked → Generate disabled
- High-confidence resolve ("Congo") → auto-skip banner, not picker
- "Not this?" → returns to picker
- Generate → stub `/job/:id` page renders

**Phase 2+:** See §16 of SPEC.md for phase-specific test lists.

**Golden-set regression** (run after any prompt edit):
```bash
python scripts/run_golden_set.py --model claude-sonnet-4-6
```
All 10 works must have 100% `spoiler_level` coverage and zero flagged fabrications before committing a prompt change.

---

## Known Quirks

- **lfc ports:** API `127.0.0.1:8202`, frontend `127.0.0.1:8201`. Port 8200 was already taken by `signal-ingest-api` (signal-newsletter project). Verify these are free on lfc before first deploy.
- **SSE behind nginx:** `proxy_buffering off` and `proxy_read_timeout 5m` are required on the VPS nginx block for SSE to work. See `charactermap.torgersen.ai.conf`.
- **PDF headshots:** pandoc + LaTeX cannot fetch remote URLs. Headshots must be downloaded to `/tmp` first and passed as local file paths. See Phase 4 in §16.
- **TMDb image proxy:** the `proxy_cache_path` zone (`tmdb_images`) must be added to the VPS nginx `http {}` block — not the server block. Done in Phase 7.
- **TitleSearch is explicit-trigger only.** No debounced-on-keystroke autocomplete. The resolve call fires on Enter or Search button click only.
- **Acknowledgement checkbox is never persisted to localStorage.** The user re-confirms every session. Model, formats, and type toggle are persisted; email and acknowledgement are not.
- **Alembic `server_default` for string columns needs inner quotes.** Use `server_default="'full'"` not `server_default="full"` — PostgreSQL interprets the unquoted form as an identifier, not a string literal.
- **SQLAlchemy ORM `__table_args__`:** CHECK constraints and partial indexes must appear in both `tables.py` AND the Alembic migration. If only in the migration, `alembic --autogenerate` will produce spurious DROP/ADD diffs.
- **deploy.sh builds on lfc directly** (git pull → docker compose build). Does NOT push to a container registry. Phase 7 will add GHCR push/pull via GitHub Actions. See comment in deploy.sh.
- **Planka MCP API quirks:** `cards update` requires `position` alongside `listId` when moving between lists (422 without it). `cards create` requires `type: "project"` (400 without it).
- **`max_tokens` has three separate defaults** — `base.py`, `anthropic_client.py`, AND `pipeline.py`'s `call_and_validate`. All must be kept in sync. `pipeline.py`'s default is the one that actually matters at runtime (it's passed through to the client). Currently 16384. 4096 was too small for large works (Dune 6139t, García Márquez 6461t).
- **Golden set title:** "Marekors" (Norwegian) → model refuses as `low_confidence`. Use "The Devil's Star" (English title of Jo Nesbø's Harry Hole #5, 2003).
- **Running scripts inside the container:** `docker exec -e PYTHONPATH=/app charmap_api python scripts/run_golden_set.py ...` — the scripts directory is NOT copied into the image; copy with `docker cp` first. Set `PYTHONPATH=/app` so `app.*` imports resolve.
- **`.env` on lfc must include** `POSTGRES_PASSWORD`, `DATABASE_URL=postgresql+asyncpg://charactermap:charactermap@postgres:5432/charactermap`, and `REDIS_URL=redis://redis:6379/0` — not just the API keys.
- **PDF rendering needs `lmodern`** in the worker image, not just `texlive-latex-base` + `texlive-fonts-recommended`. `lmodern.sty` lives in its own apt package. Without it pandoc fails with "File `lmodern.sty' not found".
- **`pdflatex` skipif in test:** `tests/unit/test_pdf_renderer.py` gates on `which pandoc` AND `which pdflatex`. Pandoc alone (often present on dev machines) isn't enough — tests will error rather than skip. They run inside the Docker container where both are installed.
- **Vite caching can produce stale bundles.** After a `npm run build`, the output hash may not change even when source did — Vite reuses cached output. If a frontend edit doesn't appear in the browser after rebuild, `rm -rf frontend/dist && npm run build` to force a clean build. Then `docker compose build frontend && docker compose up -d frontend`.
- **Docker frontend container has no hot reload.** Every frontend code change requires `docker compose build frontend && docker compose up -d frontend` to be visible at `http://localhost:8201`. The container serves the static `dist/` baked at build time — there is no bind mount.
- **React Flow node `parentId`:** when a node has a `parentId`, its `position` is *relative* to the parent. Dragging the parent moves children. We use this for faction-group dragging in `src/layout/layout.ts`. The character node's `style.width` must match the layout's `NODE_WIDTH` constant or the faction box height calculations will be wrong (text wraps without the width constraint).
- **React Flow edge `zIndex` controls line AND label together.** To get edges below nodes (`zIndex 0`) but labels above nodes when toggled on, we recompute edges in `liveEdges = useMemo` with `zIndex: showLabels ? 10 : 0`. There is no separate label-zindex setting.
- **Edge handles recompute live in CharacterMapCanvas.** `pickHandles` is exported from `layout.ts` and called inside the `liveEdges` useMemo over a `centers` map derived from current node positions. Dragging a faction group swings its edges to the facing handles immediately — no manual Reset layout needed. (Was a build-time-only computation through Session 4.)
- **Coverage banner dismiss persists per job** via `localStorage` key `cm-coverage-dismissed-<jobId>`. Don't reset on reload.
- **TMDB credits fuzzy match runs post-LLM in `app/metadata/enrichment.py`.** Threshold 0.65; matches against the credited *character* name first (real actor name is a weighted fallback). One cast member per character (greedy). Misses are normal — TMDB credits often disagree with how the LLM names characters (e.g. Buttercup is credited as "The Princess Bride"). Future ActorOverridePopover (deliverable #30) is the manual-correction path.
- **`media_type` is persisted on `Job.resolved_meta`** so the worker knows whether to call `/movie/{id}/credits` or `/tv/{id}/credits`. For books, it's pulled from `resolved.adaptation.media_type` when present (currently always null until book→adaptation cast wiring lands).
- **CreatorPill is rendered absolute-positioned inside the React Flow container**, not as a React Flow node. This keeps it out of `fitView` calculations and immune to drag/zoom. Render condition: `charMap.creator` truthy.
- **Vitest 4 is incompatible with Vite 5.4** (needs esbuild ≥0.27, Vite ships 0.21). Pin to `vitest@^3` for this project; revisit when bumping to Vite 6+.
- **Haiku 4.5 wraps JSON output in ```json fences**, fails Pydantic validation on both first try and retry. Sonnet 4.6 does not. Until the retry prompt is hardened to strip fences (or the system prompt is more emphatic), only `claude-sonnet-4-6` and `claude-opus-4-7` are reliable for end-to-end generation. Filed as bug.
- **`character_map` field on Job stores the model's output as JSONB.** The frontend casts it `as unknown as CharacterMap` in `JobView.tsx`. There is no runtime validation of stored maps — they're trusted because they passed Pydantic validation when written.
- **Artifact files are written by the worker but served by the API.** Both containers mount the same `artifacts` named volume at `/var/lib/charactermap/artifacts`. If the volume is missing on one side, signed URLs will return 404 even though the file exists on the other.
- **Cache hits set `Job.model = cached.model`**, NOT the user's requested model. The UI currently has no signal of this — a Phase 4 follow-up card will surface a "cached from <model> · $0" hint.
