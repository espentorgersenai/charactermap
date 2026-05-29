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
- **SSE location MUST be regex-anchored to the stream path, NOT a `location /api/jobs/` prefix.** With `location /api/jobs/` (trailing slash), nginx auto-301s `POST /api/jobs` → `/api/jobs/`, and WebKit on iOS refuses to replay POST across the 301 and surfaces "Load failed" with no useful error. Use `location ~ ^/api/jobs/[^/]+/stream$ {...}` instead — POST submits then fall through to the general `/api/` block cleanly. Chrome/Firefox/desktop Safari silently follow 301 on POST (de-facto, not per RFC), so this latent bug only manifests on iPad/iPhone.
- **PDF headshots:** pandoc + LaTeX cannot fetch remote URLs. `render_pdf` runs the markdown through `_REMOTE_IMAGE_RE`, downloads each remote image to a `TemporaryDirectory` (auto-cleaned), then rewrites the URLs to local paths plus a pandoc-markdown `{ width=2.5cm }` width attribute. The width attribute is *only* added during PDF rewriting — vanilla markdown viewers would render `{ width=2.5cm }` as literal text, so the MD artifact stays clean. Failed downloads degrade to bracketed alt text rather than failing the whole PDF.
- **PDF character layout: top-aligned minipages (photo left, text right).** `_rewrite_character_blocks` in `pdf.py` matches each character-with-headshot block via `_CHAR_BLOCK_RE` and replaces it with raw LaTeX `\begin{minipage}[t]{2.5cm}\includegraphics{...}\end{minipage}\hspace{0.5cm}\begin{minipage}[t]{...}...\end{minipage}` plus `\par\vspace{1.6em}` between blocks. `[t]` guarantees photo-top = heading-top. Tried `wrapfig` first for magazine-style text wrap but it threaded figures through paragraphs and detached them from their heading — don't go back to wrapfig. Descriptions are LaTeX-escaped (no markdown inside the minipage); LLM descriptions are plain prose so this is fine. Characters without a headshot don't match the regex and stay in the default stacked layout.
- **PDF needs `header-includes=\usepackage{graphicx}`.** Pandoc only auto-loads graphicx when it sees at least one markdown `![]()` image in the document. The character-block rewriter consumes all those into raw `\includegraphics`, so pandoc skips loading graphicx and the whole PDF fails with "Undefined control sequence" unless we request it explicitly via `--variable header-includes=...`.
- **`pdflatex` silently kills PDFs with non-Latin1 unicode.** ⚠ (U+26A0), used by `markdown.py` in the coverage-note line, has no entry in pdflatex's default `inputenc` table. The whole PDF render fails (`Unicode character ⚠ not set up for use with LaTeX`) and the worker logs `pdf_render_failed` while the user gets only a markdown artifact. `_strip_pdf_unsafe_chars` in `pdf.py` replaces ⚠ → `!` before pandoc runs. Add to `_UNICODE_FALLBACKS` as new offending chars surface. Switching to lualatex would handle full UTF-8 but requires `texlive-luatex` + `texlive-fonts-extra` Docker deps; not worth it yet.
- **TMDb attribution sentence** appears in the markdown footer only when the map actually uses TMDb data (`_uses_tmdb_data`: any character has an `actor`, or `creator.kind == "director"`). A pure book without an adaptation skips it. PDF inherits from the same markdown.
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
- **Movie cast is collection-aware.** `_enrich_with_credits` calls `get_credits(..., aggregate_collection=True)`. For films in a TMDB collection (Hobbit trilogy, LOTR, Star Wars), `fetch_collection_cast` pulls `/collection/{id}` and merges cast across every part (dedupe by `tmdb_person_id`, lowest billing order wins, capped at 50). Per-part failures are individually swallowed so one bad sibling doesn't break the rest. Standalone movies fall through to single-film cast — no behavior change. TV bypasses entirely (no collection concept). Live evidence: Hobbit DoS goes from 30 cast → 50 with 22 sibling-film bonus chars including Gollum and Saruman.
- **TV credits come from `/tv/{id}/aggregate_credits`, NOT `/credits`.** The latter only returns the current main cast — biased toward the latest season. For shows with significant cast turnover between seasons (Night Manager: S1 has Olivia Colman as Burr, S2 a near-disjoint cast), aggregate_credits returns the union across all seasons with each actor's `roles: [{character, episode_count}, ...]` array. `_parse_cast` flattens those roles so each (actor, character) pair is independently fuzzy-matchable. Movie /credits' single-`character`-per-entry shape is also handled by the same parser. cast_limit is 80 in the enrichment path (was 30) to accommodate the larger aggregate pool; `fetch_cast_strict` (used by the public adaptation-cast endpoint) stays at 30.
- **TMDb image proxy** (`/images/tmdb/{filename}` → `app/routes/images.py`) caches at `settings.image_cache_path/w185/{filename}` and serves with `Cache-Control: public, max-age=31536000, immutable` + `X-Cache: HIT|MISS` for observability. Filename validator: `^[A-Za-z0-9._-]+\.(jpg|jpeg|png|webp)$` — rejects shell metacharacters and any extension off the whitelist. Atomic write (tmp + rename) prevents a half-written file from being served. The `image_cache` Docker volume in `docker-compose.yml` is mounted on api+worker. Phase 7 still needs VPS-nginx `proxy_cache_path` zone in `http{}` block + `proxy_pass /images/tmdb/` — the backend cache is the source of truth; nginx is a second tier.
- **`media_type` is persisted on `Job.resolved_meta`** so the worker knows whether to call `/movie/{id}/credits` or `/tv/{id}/credits`. For books, it's pulled from `resolved.adaptation.media_type` when present (currently always null until book→adaptation cast wiring lands).
- **CreatorPill is rendered absolute-positioned inside the React Flow container**, not as a React Flow node. This keeps it out of `fitView` calculations and immune to drag/zoom. Render condition: `charMap.creator` truthy.
- **Vitest 4 is incompatible with Vite 5.4** (needs esbuild ≥0.27, Vite ships 0.21). Pin to `vitest@^3` for this project; revisit when bumping to Vite 6+.
- **Haiku 4.5 removed from `VALID_MODELS`** (Session 5/6). Reason wasn't the fenced-JSON parse bug — that's fixed by `_strip_fences` in `pipeline.py` — but factual quality: on Congo and Pulp Fiction, Haiku flagged surviving characters as deceased (Munro, Vincent Vega), fabricated characters and deaths ("Taman Harper", "Trudi Styler"), and omitted plot-pivot characters (Marvin, Drake). Violates the SPEC §5.1 "omit when uncertain" prime directive. Kept in `_MODEL_QUALITY_ORDER` and cost table so historical dev-DB jobs still rank and price correctly; removed from `VALID_MODELS` (input gate), the frontend dropdown, and `MODEL_ETAS`. Still selectable via `scripts/dev-generate.py --model` for prompt iteration.
- **Defensive fence-strip in `call_and_validate`** (`pipeline.py::_strip_fences`). Matches `^```(?:json)?\n?...\n?```$` and runs on both first-try and retry output before `_check_refusal` and `model_validate_json`. Provider-agnostic — also covers GPT-mini / Gemini-Flash tier when Phase 5 wires them in. The retry message also names the failure mode explicitly: "no ```json fences, no preamble, no trailing prose."
- **OpenAIClient uses `max_completion_tokens`, not `max_tokens`.** GPT-5 family rejects the legacy `max_tokens` field. Also uses `response_format={"type": "json_object"}` which forces well-formed JSON output (no fences observed in practice — the strip is still in place as defense). JSON mode requires the prompt to mention "JSON" somewhere; ours does (prompt rule 11 + user-message footer).
- **Docker Compose `env_file` reads first-wins for duplicate keys.** An empty `OPENAI_API_KEY=` earlier in `.env` shadows a real value appended later. Symptom: `settings.openai_api_key` is empty despite the right value being visibly in the file. Same applies to any duplicate. Audit with `awk -F= '/_API_KEY=/ {printf "line %d: %s len=%d\n", NR, $1, length($0)-length($1)-1}' .env`.
- **`docker compose restart` does NOT re-read `env_file`.** Env values are baked into the container at *creation* time. After changing `.env`, use `docker compose up -d --force-recreate <service>` to recreate the container so new values take effect. `restart` alone leaves the container running with its stale env. Verify with `docker exec <container> printenv <VAR>`.
- **GPT-5.5 pricing in `openai_client.py::_COST_PER_MTOK` is a placeholder** ($1.25 in / $10 out per MTok, based on GPT-5 launch rates). Verify against the OpenAI pricing page before any public-deploy traffic. Daily cost guard is the real safety net.
- **`gemini-2.5-pro` needs billing on the AI Studio side** — billing on a GCP project alone doesn't flow through to the AI Studio API (`generativelanguage.googleapis.com`), even though both use the same model. The fix is to enable pay-as-you-go on the AI Studio key directly (https://aistudio.google.com → billing) — *not* by adding a GCP project to the same key. Symptom of getting it wrong: `429 RESOURCE_EXHAUSTED` with `free_tier_requests: limit: 0`. Free-tier Gemini covers Flash/Flash-Lite only, and those produce Haiku-tier output (verified: fabricated characters, demoted protagonists). For Vertex AI / ADC routing the SDK supports `GOOGLE_CLOUD_PROJECT` env — code in `GeminiClient.__init__` switches automatically.
- **GeminiClient skips `response_schema`** — `response_mime_type="application/json"` is enough. Passing a schema that includes union types (`faction_id: string | null`) gets rejected by Gemini's stricter validator. Pydantic validation post-LLM is the source of truth.
- **google-genai SDK uses `client.aio.models.generate_content`** for async — the bare `client.models.generate_content` is sync and will block the event loop. Same client object works for both.
- **Character cap is user-tunable (10/20/30/40/50/100/150, default 20)** and persisted as `jobs.character_cap` (column added in migration `0003`; the 100/150 options + relaxed CHECK constraint in migration `0005`). The prompt template uses a `{CHAR_CAP}` placeholder; `_render_system_prompt` substitutes via `str.replace` (NOT `str.format`, because the prompt's TypeScript schema block has literal `{` / `}`). Cache key includes the cap — a cap=10 request will never serve a cap=50 cached map.
- **The allowed cap set lives in FOUR places that must agree** — `VALID_CHARACTER_CAPS` (`models/job.py`, Pydantic gate), `CHARACTER_CAPS` (frontend dropdown), the `ck_jobs_character_cap` CHECK in `tables.py`, and the Alembic migration. Session 10 shipped 100/150 in the first two but not the constraint/migration → cap=100/150 INSERTs threw `CheckViolationError` (surfaced as `JOB_CREATE_FAILED`). `tests/unit/test_job_models.py::test_db_cap_constraint_matches_valid_caps` now asserts the constraint enumerates exactly `VALID_CHARACTER_CAPS` — when you change the cap set, ship a migration + update `tables.py` in the same change or that test fails.
- **TMDB wins the naming discussion.** When `match_cast_to_characters` finds a confident match it overwrites `character.name` with the credited name (`Winston Wolfe` → `The Wolf`, `Bard` → `Bard / Girion` for dual-role credits). Relationships unaffected (they reference by id). Markdown/PDF read the same field so they get the credit name too. Side effect: book characters lose their LLM-canonical name (`Bilbo Baggins` → `Bilbo` if TMDB credits the adaptation that way) — acceptable for v1.
- **Fuzzy match uses three signals.** Full-string ratio, best-pairwise token ratio (×0.85 discount, tokens ≥4 chars), and actor-name ratio (×0.5). Leading articles (`the`, `a`, `an`) are stripped during normalization so `"The Joker"` matches `"Joker"`. Token-level was added in Session 5 after Pulp Fiction's Harvey Keitel ("The Wolf" credit) missed Winston Wolfe.
- **Edge labels are NOT rendered on the canvas.** Inside dense factions the bezier midpoint usually lands on an adjacent card no matter how cleverly positioned. The relationship label is preserved in the data model (markdown/PDF exports show it); the canvas just shows the line. Replaced the old `Labels` toolbar toggle with a `Connections` toggle (default on) that hides the lines entirely.
- **Layout `MAX_COLS = 3` per faction.** Was 2 through Session 4; bumped after Hobbit's 13-dwarf Company faction went 9 rows tall in 2 cols. 3-col grid keeps even big factions visually compact. `MAX_COLS` is exported from `layout.ts` so tests use the constant.
- **DPI fix lives at the root.** `frontend/src/index.css` sets `html { font-size: 17px }` (≈+6% vs the 16px Tailwind default) for high-DPI screens. Rem-based Tailwind classes scale automatically; explicit `text-[Npx]` values were bumped individually (character card name 14→16, role 11→14, title `text-lg` → `text-xl`, subtitle/blurb 12→13, etc.).
- **`CharacterMap.source_url`** is populated by `_build_source_url(job)` in the pipeline after enrichment. Format: `https://openlibrary.org/works/{ol_id}` for books, `https://www.themoviedb.org/{movie|tv}/{tmdb_id}` for film/TV. The title in the canvas header strip renders as an anchor when present. For cache hits the URL inherits from the cached `character_map` since `resolved_id` matches.
- **Download filenames are slugified twice.** `artifacts.py::_slugify` runs server-side (NFKD → ASCII → dash-sep, capped 60 chars) and sets the `Content-Disposition` filename for API-served formats (MD/PDF). `ExportMenu.tsx::slugify` mirrors the rule in TypeScript for client-side exports (PNG/SVG/JSON). On-disk filename stays `character_map.<ext>`; only the download name carries the title (e.g. `pulp-fiction-character-map.pdf`).
- **Spoiler acknowledgement banner is hidden in v1.** `Home.tsx` no longer renders the spoiler-warning checkbox; `acknowledged_spoilers: true` is hardcoded in `createJob`. The WhatThisIsBanner already sets expectations. Backend still hard-rejects `acknowledged_spoilers: false` on `POST /api/jobs` — keep that gate when re-introducing the banner for spoiler-safe mode (v1.5).
- **Rate limits are loosened for dev iteration.** `JOBS_WINDOWS` in `app/security/rate_limit.py` is 8/min · 30/hr · 60/day, NOT the SPEC §10.2 baseline (2/5/15). The comment in the file marks this. Tighten back to the baseline before public traffic. Tests read the limit from `JOBS_WINDOWS` (not hardcoded numbers), so the next adjustment is a one-line change.
- **Home.tsx now actually creates jobs.** Was the Phase 1 stub through Session 4 (navigated to `/job/stub-phase-1`). Session 5 wired `createJob` → `POST /api/jobs` → navigate to live job id with `?model=&title=` query params.
- **`character_map` field on Job stores the model's output as JSONB.** The frontend casts it `as unknown as CharacterMap` in `JobView.tsx`. There is no runtime validation of stored maps — they're trusted because they passed Pydantic validation when written.
- **Artifact files are written by the worker but served by the API.** Both containers mount the same `artifacts` named volume at `/var/lib/charactermap/artifacts`. If the volume is missing on one side, signed URLs will return 404 even though the file exists on the other.
- **Cache hits set `Job.model = cached.model`**, NOT the user's requested model. The UI currently has no signal of this — a Phase 4 follow-up card will surface a "cached from <model> · $0" hint.
- **Two-stage grounded pipeline (Session 9).** When `settings.enable_grounding=True` (default) and the client is Anthropic, `run_pipeline` calls `_run_grounded` instead of the legacy single-call path. Stage 1 = `character_map_analysis.md` + `web_search_20250305` tool → prose Cast with cited URLs. Stage 2 = `character_map_structuring.md` (no tools) → CharacterMap JSON, closed-list against Stage 1's Cast section. Stage 1 system prompt uses `cache_control: ephemeral` so warm-cache cost is ~$0.18/job, cold-cache ~$0.66. Default `max_searches=3` (Session 9 Step 1 tuned this down from 8 — searches aren't the latency bottleneck, output tokens are). New refusal code `grounding_failed` when grounded retrieval can't seed enough characters. The single-stage helper `_run_grounded_single_stage` exists as a reference but is NOT wired — see next quirk.
- **Single-stage grounded is a footgun, even though it looks faster.** Tried in Session 9 Step 4 — collapsed Stage 1 prose + Stage 2 JSON into one `web_search`-enabled call with the combined `character_map_single_stage.md` prompt. Won on Embassytown (102s vs 204s), failed catastrophically on Congo and Tokyo Express: missed Munro/Kahega/Misulu, invented "Charles Travis" (Munro+Travis composite) and "Ghost Tribe Member (Uncredited)" (TMDB film-extras leakage), and on Tokyo Express dropped Yasuda — the actual unarrested killer — and filled with invented Japanese-sounding names. The two-stage prose intermediate is *load-bearing*: Stage 1 retrieves and reasons about source credibility, Stage 2 enforces closed-list under structured constraints. Collapsing them gives the model too many concurrent constraints. Do not rewire `_run_grounded_single_stage` without a different mitigation (e.g. constrained decoding, schema-locked tools).
- **Haiku 4.5 fabricates even under the closed-list rule.** Session 9 Step 2: pinned Stage 2 to Haiku to halve its wall time. On Embassytown it produced a character named `JoaQuin` with `name_evidence: "An Ambassador whose name follows the WikiWord convention denoting dual nature"` — pure pattern-completion from CalVin/MagDa/EzRa, not source-grounded. Reverted. Sonnet stays on Stage 2. Earlier removal from `VALID_MODELS` (Session 5/6) was for ungrounded fabrication; closed-list doesn't save Haiku.
- **`Job.progress_stage` (migration 0004) carries the sub-stage within `status='generating'`.** Codes: `searching | structuring | generating | enriching | rendering | NULL`. Worker writes via `_set_progress_stage(session, job, stage)` which commits a single column update — picked up by the SSE 1s poll loop. Frontend `getStageLabel()` in `hooks/useJob.ts` maps codes to user-facing copy. Progress bar fill mapped per-stage in `routes/jobs.py::_STAGE_TO_PROGRESS`.
- **`status='done'` flips AFTER artifact rendering.** `run_pipeline`'s `else:` branch was reordered in Session 9 so the markdown + PDF render block runs while `status='generating'` and `progress_stage='rendering'`. Only after rendering completes does `status='done'` + `completed_at` get set. Prevents the SSE `done` event firing before artifacts are on disk (which would race the frontend's artifact fetch).
- **RQ `job_timeout=600` for grounded jobs.** RQ's default 180s kills jobs mid-Stage-2 because Stage 1 alone routinely runs 90-150s on web_search. Set explicitly in `routes/jobs.py` at the `queue.enqueue(generate_character_map_task, job_id, job_timeout=600)` call. Don't drop below 300s without re-validating wall-time observations.
- **Cost-tracking under-reports.** `LLMResult.cost_usd` uses `message.usage.input_tokens` (uncached input only) and excludes `cache_creation_input_tokens` (+$3.75/M for Sonnet writes) + `cache_read_input_tokens` (+$0.30/M reads) + web_search per-call ($0.01/search). For Stage 1 with warm cache, the reported $0.10 cost is ~70% of the real ~$0.15. Daily cost guard is conservative (under-reports → guard trips later than it should) but not catastrophically wrong. There's a Planka card to fix this for public launch.
- **`adaptation_note` field on CharacterMap.** Optional 1-2 sentence summary of how an adaptation diverges from the source. Populated by Stage 2 when Stage 1's analysis includes a "Key Adaptation Differences" section. For pure books with no adaptation or pure films, the field is omitted. Real example from production Congo: *"The 1995 film... substantially restructures the novel: Travis becomes a tech CEO whose son led the first expedition... Karen destroys Travis's satellite in a final act of corporate rebellion."*
- **TV season pin lives in `resolved_meta['season']`, not a Job column.** Storing it in JSONB avoids a migration and parallels the existing `adaptation_tmdb_id` pattern. `find_best_cached_job` filters cached rows in Python (small N per resolved_id), so a Night Manager S2 request never serves an All-Seasons cached map and vice-versa. The frontend dropdown is populated eagerly during `/api/resolve` (one extra `/tv/{id}` TMDB call per TV candidate; 7-day Redis cached). `season` is only honored when `media_type == 'tv'` — movies and book→movie linkages discard it before the cache lookup so the field can't pollute keys. Backend enrichment swaps `/aggregate_credits` for `/tv/{id}/season/{n}/credits` when season is set; the LLM prompt gets a `<season_focus>` block telling it to scope characters to that season only.
- **Clearing a wrong book→film adaptation is a frontend-only operation.** The `×` button on the 🎬 chip in `SelectedCandidateExtras` mutates `selectedCandidate.adaptation = null` before `createJob` fires; backend just sees a candidate with no adaptation and skips the TMDB enrichment path entirely (no cast match, no director, no adaptation_note). Live example: Bomberen by Samuel Bjørk auto-pairs with the unrelated "American Manhunt: The Boston Marathon Bombing" — clearing yields a clean Holger Munch / Mia Krüger detective-novel map with no Boston cast leakage. The wrong link is the resolver's fault (`find_adaptation_for_book` picks the highest Bayesian-scored fuzzy match across TMDB, with no semantic check); cleaning that up at the LLM level is a separate, larger problem.
- **The grounding plan at `docs/superpowers/plans/2026-05-19-grounding-pipeline.md` is intentionally uncommitted.** It documented a bespoke Wikipedia + Wikidata + Goodreads scraper architecture that we abandoned in favor of Anthropic's `web_search` tool. Keep on disk as a record of the road not taken; if the API tool ever becomes insufficient, the plan is the fallback.
- **`character_cap` now includes 100 and 150** for very-large-ensemble works (GoT has ~120 recurring named chars across 8 seasons). Cost scales linearly with output tokens; cap=150 runs ~$0.50/job on Sonnet (warm cache). The 100/150 options exist mainly to unblock the geographic GoT special map — most works should stay at 20–50.
- **Wikipedia actor-photo fallback** (`backend/app/metadata/wikipedia_actor.py`) runs after TMDB fuzzy matching for any character still without an actor. Walks ≤ `MAX_WIKI_LOOKUPS` (60) unmatched characters; for each, asks `en.wikipedia.org/w/api.php` for a search-results extract, regexes out `portrayed/played/voiced/depicted by <Actor>`, then hits TMDB `/search/person` to resolve the actor to a tmdb_person_id + headshot. Pure best-effort: every step is try/except, missing matches stay as initials. Only runs on film/tv jobs (or books with a linked adaptation_tmdb_id) — pure book maps have no actors to look up. Recovery rate observed on GoT-scale ensembles: closes the long tail of supporting cast that TMDB's billing order pushes past the cast_limit cutoff.
- **TMDB `cast_limit` is now `max(80, character_cap * 3)`.** Top-80 by billing order is fine for cap=20, but cap=150 against GoT's aggregate_credits (hundreds of named roles) needs a 450-deep pool so recurring supporting cast aren't pre-truncated before fuzzy matching even runs. The pool growth is bounded by character_cap so cap=20 stays cheap.
- **`Character.home_region` is an optional geography string.** Free-form, populated by Stage 2 structuring when the analysis references a defined geography (Westeros/Essos, Middle-earth, real-world districts). The frontend's `resolveRegion()` in `src/geographic/westeros.ts` normalizes free-form input (strips leading articles, lowercases, drops non-alphanumeric) and maps it to a canonical anchor with fractional (0–1) backdrop coordinates. Unknown regions render in an "Unplaced" gutter rather than being dropped. No DB migration — sits inside the `character_map` JSONB blob.
- **Geographic view lives at `/geo/:jobId`.** Reads the same Job row as `/job/:jobId`, but renders character cards positioned over a backdrop image (`frontend/public/maps/westeros.jpg`, gitignored — drop your own). Anchors fan out into a 3-column grid per region so dense areas (Crownlands, North) don't pile on a single pixel. Sidebar links to/from the faction view; the link only appears in JobView when at least one character has a `home_region`. View is geography-aware only for Westeros right now; extending to Middle-earth / Dune would mean adding a sibling anchors file + a backdrop param to the route.
