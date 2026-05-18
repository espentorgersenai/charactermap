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
