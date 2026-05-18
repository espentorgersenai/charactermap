# Session Chronicle

Character Map Generator · Chronological build log — appended at the end of each session.

Last updated: Session 4 · 2026-05-18 (wrapup)

> **Backlog / open items / next steps → [kanban.torgersen.ai](https://kanban.torgersen.ai) — project: Character Map, board: Character Map.** This file is the *narrative archive* of what was built each session; no TODOs live here.

---

## Session 1 — 2026-05-18

### What We Built
- Deep pre-build interview covering infrastructure, UX, phases, and deployment.
- Resolved all major open questions before any code was written.
- Updated SPEC.md from v1.6 → v1.7 with all decisions incorporated.
- Bootstrapped project workflow via `/newproject`: CLAUDE.md, chronicle, docs/README.md, .gitignore, .mcp.json (Planka), SessionStart hook, Planka labels, initial commit.

### Key Decisions
- **Deployment target:** lfc (home GPU server), not VPS directly. Follows radio-station pattern. API on port 8200, frontend on 8201. VPS nginx proxies via WireGuard (10.0.0.2).
- **No nginx in docker-compose.** TLS termination stays with usv-fleet nginx.
- **Own postgres + redis containers** (not shared with fleet). Container prefix: `charmap_`.
- **TitleSearch:** explicit trigger only (Enter / Search button). No debounced keystroke autocomplete.
- **Dark/light mode:** system `prefers-color-scheme`.
- **TMDb in Phase 1:** adaptation lookup in candidate picker only. Full headshot pipeline is Phase 4.
- **Phase 1 terminal state:** Generate → stub `/job/:id` page with placeholder.
- **Phase 1 also includes:** stub `/privacy` + `/terms` routes, `dev-generate.py` skeleton, `deploy.sh`.
- **All banner links** (mailing list, "how this works") are placeholders for now.
- **Tracker:** [kanban.torgersen.ai](https://kanban.torgersen.ai), project *Character Map*, board *Character Map* (ID: 1777578866382997173).
- **Workflow:** SessionStart hook briefs from chronicle + Planka cards + recent commits. `/wrapup` closes each session.

### Spec Version
SPEC.md v1.7 — 7 phases, each with explicit test checkpoints. See §16 for full phase/test breakdown.

### Planka Setup
Board created (ID: 1777578866382997173) with 19 labels (6 categories + 6 svc:* + 7 phase:*) and three lists (ToDo / In Progress / Completed). 8 Phase 1 cards created in ToDo covering all deliverables from §16.

---

## Session 2 — 2026-05-18

### What We Built

Full Phase 1 implementation — all 8 Planka cards moved to Completed.

- **Backend scaffold:** `docker-compose.yml` (lfc pattern: charmap_api 8200, charmap_frontend 8201, charmap_postgres, charmap_redis, charmap_worker — no nginx), FastAPI app with CORS, `app/config.py` (all env vars including `DAILY_COST_LIMIT_USD`), SQLAlchemy ORM for all 4 tables (jobs, artifacts, daily_costs, analytics_events), Alembic initial migration with CHECK constraints and all indexes.
- **POST /api/resolve:** Open Library search + TMDb multi-search for film/TV + adaptation lookup for books. Confidence scoring (0.5×title_sim + 0.2×single_result + 0.15×popularity + 0.15×year_proximity). 16 unit tests passing (confidence formula, OL parser, TMDb Bayesian ranking).
- **React 18 + Vite frontend:** TypeScript strict, Tailwind `darkMode: 'media'`, TanStack Query, Zustand, react-router-dom v6. Routes: `/`, `/job/:id`, `/privacy`, `/terms`. Vite proxy: `/api` → `localhost:8200`.
- **Form components:** TitleSearch (explicit Enter/button trigger only — no debounce), ModelDropdown (5 models per §8.1, default `claude-sonnet-4-6`), FormatCheckboxes (6 formats), email field, type toggle, Turnstile placeholder.
- **Banners + modal:** WhatThisIsBanner (self-deprecating copy from §11.1), SpoilerWarningBanner (amber, acknowledgement checkbox — NOT persisted), HowThisWorksModal (two-paragraph explanation of resolve + LLM flow).
- **localStorage hooks:** `useFormPrefill` persists model/formats/workType only (email + acknowledgement excluded); `useRecentMaps` stores last 10 jobs keyed by jobId, deduplicates.
- **ResolveCandidatePicker + ResolveBanner:** auto-skip at `confidence_score >= 0.9` with auto-select; "not this?" resets to full picker; zero-results distinguished from pre-search state via `hasSearched` flag.
- **Stub pages:** `/job/:id` (shows job ID, Phase 2 placeholder), `/privacy` (GDPR content from §15.1), `/terms` (content from §15.2).
- **Operational artifacts:** `scripts/dev-generate.py` skeleton (all 8 flags from §19.2, prints "would call" to stderr, stub JSON to stdout), `deploy.sh` (git pull + build-on-lfc), `nginx/charactermap.torgersen.ai.conf` (exact §13.2 content with SSE block and tmdb_images cache).
- **GitHub repo created:** [github.com/espentorgersenai/charactermap](https://github.com/espentorgersenai/charactermap) — all commits pushed.
- **Phase 2 Planka cards created** (7 cards in ToDo, all labelled feature + phase:2 + svc:*).

### Key Decisions

- **deploy.sh strategy:** Changed from SPEC §13.3's build-local-push-to-registry approach to `git pull + docker compose build` on lfc directly. Registry (GHCR) is a Phase 7 concern. Comment in deploy.sh documents the intended Phase 7 upgrade path.
- **Alembic `server_default` for strings:** PostgreSQL requires inner quotes — `server_default="'full'"` not `server_default="full"`. Caught by code quality review.
- **ORM model vs migration:** CHECK constraints and partial index must appear in both `tables.py` `__table_args__` AND the Alembic migration to prevent autogenerate drift. Caught by spec review.
- **`hasSearched` state in `useResolve`:** Added to distinguish "never searched" (show hint) from "searched, zero results" (show no-results message). Caught by final code review.
- **Planka API quirks:** `update` card requires `position` alongside `listId` (422 without it); `create` card requires `type: "project"` (400 without it).

### Test Status

- 16 backend unit tests passing (`pytest tests/unit/`)
- Frontend: 0 TypeScript errors, clean Vite build (97 modules, 212 kB JS)
- Phase 1 manual smoke tests: ready to run once `.env` is configured on lfc

---

## Session 3 — 2026-05-18

### What We Built

**Phase 2 complete (generation pipeline)** — all 7 Planka cards moved to Completed.

- **Infrastructure fix:** Port 8200 was occupied by `signal-ingest-api`. API remapped to **8202**. Updated `docker-compose.yml`, nginx conf, `vite.config.ts`, `deploy.sh`, and `CLAUDE.md`.
- **CharacterMap + Job Pydantic models:** `CharacterMap`, `Faction`, `Character`, `Relationship`, `RefusalResponse` — `spoiler_level` is `Optional[Literal[0,1,2,3]]` so pipeline can detect and sweep missing values to 3. `JobCreateRequest` validates model name and non-empty formats.
- **LLMClient protocol + AnthropicClient:** `LLMResult` dataclass, `LLMClient` Protocol, `AnthropicClient` with `cache_control: ephemeral` on system prompt for Anthropic prompt caching. Per-model cost table.
- **`character_map.md` prompt template:** All 11 §5.1 guardrails — identity-from-metadata, omit-when-uncertain (3 tiers of certainty), full-spoiler, `spoiler_level` tiers, character cap (max 25), `setting_preamble` guidance, English output, library-card tone, 2–6 factions, user_query-as-data-only, JSON-only output. Full TypeScript schema embedded.
- **`call_and_validate` + pipeline orchestration:** Refusal detection (before Pydantic), retry-once-with-error-appended, `spoiler_level` sweep deferred to `run_pipeline`. `run_pipeline` uses `asyncio.run()` wrapper for the RQ task boundary. 8 unit tests for retry/refusal logic.
- **`POST /api/jobs` + `GET /api/jobs/:id`:** `acknowledged_spoilers: true` hard gate returns 400. `get_queue()` uses synchronous Redis connection (RQ requirement). Turnstile accepted but not verified (Phase 5). 4 unit tests including acknowledged_spoilers gate.
- **`GET /api/jobs/:id/stream` SSE:** DB polling at 1s intervals, status-to-progress fractions, terminal events (`done`/`refused`/`failed`).
- **JobView frontend — 5 states:** Loading, in-progress (progress bar + elapsed timer + per-model ETA), done (raw JSON — canvas Phase 3), refused (friendly message + "try different model"), failed (error + mailto). `useJob` hook with EventSource + 2s polling fallback.
- **`dev-generate.py` fully wired:** Calls `AnthropicClient` directly, prints stderr stats + stdout JSON. `run_golden_set.py` + `tuning/golden_set.yaml` (10 works from §19.3).
- **Integration test:** `test_congo.py` — POST → `run_pipeline()` directly → poll → assert `status=done` and `spoiler_level` on all characters/relationships.
- **Golden-set baseline run:** 10/10 works pass, 100% `spoiler_level` coverage. Key finding: `max_tokens=4096` too small for large works (Dune needs 6139 tokens, García Márquez 6461). Fixed to `16384` in `base.py`, `anthropic_client.py`, and `pipeline.py`.
- **Deployed to lfc** at port 8202. Acknowledged_spoilers gate verified live.

**Phase 3 design + plan produced** (not yet implemented):

- **Design doc:** `docs/superpowers/specs/2026-05-18-phase3-design.md`
- **Implementation plan:** `docs/superpowers/plans/2026-05-18-phase3-rendering.md` — 14 tasks
- **Visual companion session** used to validate canvas design

### Key Decisions

- **API port 8202** (8200 was taken by `signal-ingest-api` on lfc). All references updated.
- **`max_tokens` must be 16384**, not 4096. Three separate defaults existed (base.py, anthropic_client.py, pipeline.py) — all three must match or the pipeline.py default overrides the client default.
- **`call_and_validate` does NOT call `_sweep_spoiler_levels`** — sweep is deferred to `run_pipeline`. The retry tests verify this: after call_and_validate returns, `spoiler_level` is still `None` if the LLM omitted it; `run_pipeline` fills it in to 3.
- **`PYTHONPATH=/app` needed** when running `dev-generate.py` or `run_golden_set.py` inside the Docker container (`docker exec -e PYTHONPATH=/app charmap_api python scripts/...`).
- **Golden set title:** "Marekors" (Norwegian) refused as `low_confidence`. Replaced with "The Devil's Star" (English title of Jo Nesbø's Harry Hole #5).
- **Result caching (Phase 3):** Opus result trumps all — if any model has generated a map for a work, POST /api/jobs returns the best existing result instantly at $0 cost. Cache key: `(resolved_id, spoiler_mode)`. Model ranking: Opus 4.7 → Sonnet 4.6 → GPT-5.5 → Gemini 2.5 Pro → Haiku 4.5.
- **Canvas design choices (Phase 3):** Node style = horizontal pill (option B). Page layout = top toolbar + right sidebar. Badges (⚠ †) hidden by default with independent toolbar toggle. Legend collapsible independently at bottom-left.

### Test Status

- 48 backend unit tests passing (added models, pipeline, jobs route, LLM client tests)
- Integration test `test_congo.py`: PASSED (36s, $0.038, 10 chars)
- Golden-set baseline: 10/10 works, 100% spoiler_level coverage, $0.68 total
- Frontend: clean Vite build

---

## Session 4 — 2026-05-18

### What We Built

**Phase 3 implementation complete and verified end-to-end.** All 7 ToDo cards moved to Completed. The 14-task plan from session 3 was executed via subagent-driven development.

- **Backend rendering pipeline:** Markdown renderer (`backend/app/renderers/markdown.py`) with bleach XSS sanitisation (9 tests). PDF renderer (`renderers/pdf.py`) via pandoc subprocess with `--pdf-engine=pdflatex` (3 tests, skipped locally where pdflatex absent). Worker pipeline wired to render both after generation and write `Artifact` rows.
- **Dockerfile additions:** `pandoc`, `texlive-latex-base`, `texlive-fonts-recommended`, **and `lmodern`** (the last was a late discovery — `lmodern.sty` lives in its own apt package, not `texlive-fonts-recommended`).
- **Signed artifact URLs:** `backend/app/security/signed_urls.py` HMAC-SHA256 over `path:exp`, 7-day TTL (5 tests including expiry, tamper, invalid-exp).
- **Artifact endpoints:** `POST /api/jobs/:id/artifacts` (multipart upload from frontend), `GET /api/jobs/:id/artifacts` (returns signed URLs), `GET /api/artifacts/:job_id/:filename` (verifies sig+exp, serves file). 4 tests including mock DB session.
- **Result cache:** `find_best_cached_job()` in `routes/jobs.py` with model quality ranking (Opus 4.7 → Sonnet 4.6 → GPT-5.5 → Gemini 2.5 → Haiku 4.5). Cache-hit path clones `character_map` to new Job with `estimated_cost_usd=Decimal('0')`. 4 tests.
- **Alembic 0002:** Partial index `idx_jobs_cache` on `(resolved_id, spoiler_mode)` WHERE `status='done' AND deleted_at IS NULL`.
- **Frontend layout:** `src/layout/layout.ts` (renamed from `dagreLayout.ts` after dagre removed) — factions arranged in `ceil(√N)` × `ceil(N/cols)` grid; per-faction internal grid with `MAX_COLS=2`. Per-edge handle selection: each node has 8 invisible handles (4 source + 4 target on every side), `buildLayout` picks the facing-side pair from absolute node centers. Bezier (`type: 'default'`) edges with `zIndex: 0` (below nodes). Character nodes with `parentId: factionNodeId` and `draggable: false` so faction groups drag as units.
- **Canvas component:** `CharacterMapCanvas.tsx` with React Flow + MiniMap + Controls + Background. Three toolbar toggles (Badges, Labels, Reset layout) plus Share / Export. Labels off by default; when on, edges get `zIndex: 10` so labels float above nodes/boxes. Coverage note banner dismissable via × button.
- **Export + downloads:** `ExportMenu.tsx` (PNG/SVG/JSON via `html-to-image` + React Flow `toObject`), uploads each export to the artifact endpoint after download. `DownloadList.tsx` (sidebar) renders signed URLs returned by `GET /api/jobs/:id/artifacts`.
- **JobView done state:** Full-viewport canvas + 190px right sidebar with `DownloadList`.

**End-to-end verification (issue #1 from session-end review):**
- Generated fresh "Of Mice and Men" map: status `done` in 32s, $0.038, 11 characters across 3 factions
- Worker logged `markdown_rendered` + `pdf_rendered`; `artifacts` table has 2 rows (4381 + 112512 bytes)
- API container sees the same files (shared `artifacts` docker volume)
- Signed URL via `GET /api/artifacts/...?sig=...&exp=...` returns Markdown content correctly
- `DownloadList` sidebar populates with both items on the job page
- **Cache hit verified:** second POST for "Of Mice and Men" with `model=claude-haiku-4-5-20251001` returned status `done` instantly; API logged `job_cache_hit source_model=claude-sonnet-4-6`

**Dagre dead-dependency cleanup (issue #2):**
- Removed `dagre` + `@types/dagre` from `package.json` (never actually used after the layout was rewritten as plain grid math during the visual-iteration phase)
- Renamed `dagreLayout.ts` → `layout.ts`, updated one import in `CharacterMapCanvas.tsx`
- Added `smoke-*.png` and `.playwright-mcp/` to `.gitignore`

### Key Decisions

- **Layout: grid of factions, not single horizontal row.** Original plan put all factions at the same `y=48` in a single row. User feedback ("a square or circular shape is probably optimal") drove a redesign to a `ceil(√N)` column grid. For Congo's 5 factions: 3×2 grid, dramatically more compact and less wide.
- **Edge type: `default` (bezier), not `smoothstep` or `straight`.** Iterated through all three this session:
  - `smoothstep` (orthogonal grid) → multiple edges to the same target collapse into stacked rectangles
  - `straight` → no looping but feels mechanical, no curve at all
  - `default` (bezier) with explicit facing-side handle selection → natural curves that don't loop. **Final choice.**
- **8 handles per node.** Character cards have `Handle id={src,tgt}-{right,bottom,left,top}` for all 4 sides. `buildLayout` picks `sourceHandle` and `targetHandle` per edge based on `dx, dy` between absolute node centers (Math.abs comparison decides axis; sign decides side).
- **`parentId` for faction → character relationship.** Character node positions become *relative* to the faction group. Dragging the group moves all children with it. `draggable: false` on children prevents independent moves. `nodeCenters` map stores absolute positions captured at build time for handle selection.
- **Edges below nodes via `zIndex: 0`** (character cards at `zIndex: 2`, faction groups at `zIndex: 0`). Edge lines pass behind boxes — text always readable. When user toggles Labels on, `liveEdges` boosts `zIndex` to 10 so labels float above everything.
- **Result cache stores `model = cached.model`.** Documented in the design spec but invisible to user — a follow-up Planka card now exists to add a UI hint ("cached result from <model> · $0").
- **NODE_WIDTH 300, NODE_HEIGHT 76.** Long character names (e.g. "Morikawa / Consortium Field Leader") needed more than 240×64 to render without clipping faction boxes. Explicit `style: { width: NODE_WIDTH }` on character nodes forces React Flow to use the same width the layout assumed.
- **Toolbar uniformity:** All five buttons (Badges, Labels, Share, Export, Reset layout) use the same ghost-outline style when inactive. Toggles (Badges, Labels) go solid blue when active. Dropped the original blue-Share primary-button look.
- **Subagent-driven development for the 14-task plan.** Each task: dispatch implementer with full task text + context, verify outputs (test counts, build status), commit, move on. Total ~12 implementer dispatches across the plan plus an end-to-end deploy subagent.

### Test Status

- **73 backend unit tests passing**, 3 PDF tests skipped locally (no pdflatex outside Docker; they run in CI/container).
- **End-to-end pipeline verified live:** Of Mice and Men map generated with full renderer + artifact + cache-hit flow.
- **Frontend: zero tests** (gap surfaced in review; follow-up card created).
- Clean Vite build (425 kB JS, 137 kB gzip).
- Deployed to lfc and re-deployed multiple times during visual iteration.

---

## Session 5 — 2026-05-18

### What We Built

**Phase 3 polish (B-path) — all three follow-ups landed:**
- Edge handles recompute live as nodes move (`pickHandles` extracted from `buildLayout`, called inside `liveEdges` over a node-centers map that accounts for parent offsets). No more stale handles after dragging a faction.
- `cm-coverage-dismissed-${jobId}` localStorage key persists the coverage-note × dismiss across reloads.
- Vitest 3 wired with 19 unit tests for `buildLayout` + `pickHandles` (grid math, faction filtering, handle quadrants, edge dedup, MAX_COLS wrap). Vitest 4 is incompatible with Vite 5's bundled esbuild — pin to v3.

**Phase 4 tracer end-to-end (A-path), then made user-tunable:**
- `app/metadata/tmdb.py::get_credits` returns top-30 cast + director (with `profile_path` for headshot URL composition).
- `app/metadata/enrichment.py` does fuzzy-matching with three signals: full-string ratio, best-pairwise token ratio (×0.85, tokens ≥4 chars), actor-name ratio (×0.5). Leading-article stripping (`the`/`a`/`an`) and honorific stripping in normalization. Threshold 0.65.
- `_enrich_with_credits` runs post-LLM; works for both film/tv (credits from the work itself) and books (credits from `resolved_meta.adaptation_tmdb_id` if present). Creator stays the author for books, director for film/tv.
- **TMDB wins the naming discussion:** matched character's name overwrites the LLM's pick. *Winston Wolfe → The Wolf*, *Bard → Bard / Girion*, *Azog → Azog the Defiler*.
- Frontend: `CharacterCardNode` swaps to TMDB headshot when `actor.headshot_url` present, clickable to `themoviedb.org/person/<id>`. `CreatorPill` floats inline next to the title, links to TMDB (director) or Open Library author search; renders the director's headshot when available.
- Verified live: Princess Bride 12/13 → 13/13 → never mind, Pulp Fiction 16/16, The Hobbit 22/30 (the 8 remaining misses are characters from *other* films of the trilogy — filed as cap-aggregation card).

**User-tunable character cap (10 / 20 / 30 / 40 / 50):**
- New `CharacterCapDropdown` on the form, persisted via `useFormPrefill`, default 20.
- `JobCreateRequest.character_cap` validator restricts to the 5 values.
- Migration `0003`: `character_cap INT NOT NULL DEFAULT 20` on `jobs` + check constraint.
- Cache lookup keyed by `(resolved_id, spoiler_mode, character_cap)` — a cap=10 request never serves a cap=50 cached map.
- Prompt template uses `{CHAR_CAP}` placeholder; substituted via `str.replace` because the prompt has literal `{` / `}` in its TypeScript schema block (kills `str.format`).
- Sample run on The Hobbit: cap=20 → 17 chars / 4 183 tokens / $0.063 / 52 s. cap=50 → 30 chars / 6 239 tokens / $0.094 / 75 s. Sonnet 4.6 self-limits well below 50 (sized to narrative weight, not the cap).

**Home.tsx — actually creates jobs now:**
- Wires `createJob` → `POST /api/jobs` → navigate to `/job/<id>?model=&title=`. Was the Phase 1 stub through Session 4.

**Header strip + title affordances:**
- Title / subtitle / blurb in a header strip above the toolbar (was missing entirely).
- Title is an anchor when `CharacterMap.source_url` is set — deep-links to TMDB movie/tv page or Open Library work page. Backfilled all 10 existing done jobs.
- Creator pill moved inline next to the title (was floating top-left).

**Download filenames:**
- `artifacts.py` slugifies `job.resolved_title` into the `Content-Disposition` filename for API-served formats. On-disk file stays `character_map.<ext>`. Result: `pulp-fiction-character-map.md` instead of `character_map.md`.
- `ExportMenu` mirrors the slugify rule in TypeScript for client-side PNG / SVG / JSON exports.

**Subtraction:**
- Dropped the Badges feature entirely (toolbar button, on-card spoiler/death pips, Badges legend section). Underlying `spoiler_level` and `is_deceased_in_work` stay in the schema for MD/PDF.
- Dropped edge label rendering on the canvas. Tried bezier-midpoint chips, then per-edge stagger, then perpendicular offset + truncate; all worse than just hiding them. Labels stay in the data model so MD/PDF can show them. Replaced the `Labels` toolbar toggle with `Connections` (default on) that hides the lines entirely.

**DPI bump for 140-DPI displays:**
- `frontend/src/index.css`: `html { font-size: 17px }` (≈+6% global via rem).
- Character card name 14→16 px, role 11→14 px, title `text-lg` → `text-xl`, subtitle/blurb 12→13 px, CreatorPill headshot 28→32 px, etc.
- Layout `MAX_COLS = 2 → 3` so big factions stay compact (Hobbit's 13-dwarf Company: 9 rows → 6).

**CLAUDE.md got a Planka maintenance section.** Explicit agent responsibilities: move cards to Completed when work ships, file new cards for discovered work, bias toward filing.

### Key Decisions

- **TMDB wins the naming discussion.** When a fuzzy match clears threshold, the credited character name overwrites the LLM's name. Audience-recognizable, matches what's on the work itself, simpler frontend (no need for `display_as` field). Cost: books inherit adaptation-naming for matched characters; books without adaptations untouched.
- **Token-level fuzzy match.** Necessary to bind TMDB's nickname credits ("The Wolf") to LLM-canonical full names ("Winston Wolfe"). Token-only matches discounted to 0.85× to keep false positives down; min token length 4 chars excludes common short words.
- **Cap dropdown over hard-coded 25.** User wanted to feel the cost/density tradeoff. Pre-baked the five sensible options (10/20/30/40/50) rather than free-form input — keeps cache hit-rates sane (5 distinct caps × N works ≪ unlimited × N) and the dropdown carries cost hints so users self-throttle.
- **Edge labels go away on the canvas, stay in the data.** Three iterations on label positioning — bezier midpoint (collides with adjacent cards in dense factions), source-end stagger (lands on source's neighbours), perpendicular-offset + truncate (still messy). User called the last attempt "worst one so far" and asked to hide the toggle. Right call: relationships are easier to read as a list (MD/PDF) than as overlapping chips on a graph.
- **Slugify everywhere.** Both backend and frontend have a slugify helper because exports run in both places (API-served vs client-generated). The on-disk filename stays generic (`character_map.<ext>`) — only the download name carries the title. Easier to keep paths stable across renders.

### Test Status

- **90 backend unit tests passing** (+ 4 enrichment-token tests, + 1 TMDB-rename test, − 0).
- **19 frontend tests passing** (Vitest 3, MAX_COLS-aware).
- End-to-end runs verified live for Pulp Fiction (16/16 actors + The Wolf renamed), The Hobbit (22/30 matched, all 13 dwarves + Smaug + Bard + Azog), Of Mice and Men cap=10 (10/10, $0.0356, 37 s), Princess Bride.
- 6 commits this session: `d276ffb`, `5497b48`, `e1fc460`, `d1d937b`, `fc666ea`, `93c8b62`.
