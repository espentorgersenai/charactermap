# Session Chronicle

Character Map Generator · Chronological build log — appended at the end of each session.

Last updated: Session 8 · 2026-05-19 (wrapup)

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

## Session 6 — 2026-05-18

### What We Built

**Phase 4 deliverable #29 finished — MD + PDF headshots:**
- Markdown renderer now emits inline `![Char as played by Actor](url)` images, a creator credit line above the blurb (`**By:** {author}` for books, `**Directed by:** ![…](url) {director}` for film/TV), and a TMDb attribution sentence in the footer when the map uses any TMDb data.
- PDF renderer downloads every remote image to a `TemporaryDirectory`, rewrites the markdown to point at local paths with a pandoc `{ width=2.5cm }` size hint, then runs pandoc. Atomic cleanup via the context manager. Failed downloads degrade to bracketed alt text.

**Phase 4 deliverable #31 — adaptations cast endpoint:**
- New `backend/app/routes/adaptations.py`: `GET /api/adaptations/{tmdb_id}/cast?media_type=movie|tv` returning sorted cast (`CastMemberPublic` / `AdaptationCastResponse` Pydantic models).
- Refactored `tmdb.py`: extracted `_parse_cast(data, limit)` shared helper, added `fetch_cast_strict()` (raises on TMDB failure; the route uses it for proper 404/503 status mapping). Existing `get_credits()` stays best-effort.
- 8 unit tests covering happy path, null profile_path, 422 on bad media_type, 503 on misconfig + 5xx, 404 on unknown id, 200 on empty cast.
- Unblocks the still-pending frontend ActorOverridePopover (#30).

**Multi-film cast aggregation (was Phase 4 nice-to-have):**
- `fetch_collection_cast(tmdb_id, media_type)` detects `belongs_to_collection` on a movie, fetches each part's credits, merges via `_merge_casts` (dedupe by `tmdb_person_id`, lowest billing order wins, capped at 50).
- `get_credits` got `aggregate_collection=True` opt-in; `_enrich_with_credits` calls it for all movie enrichment.
- Live evidence on The Hobbit: The Desolation of Smaug: 30 → 50 cast, 22 sibling-film bonus characters including Gollum, Saruman, Frodo. Eagles still missing — TMDb data limitation, not aggregation bug.

**TMDb image proxy (Phase 4 #27 / Phase 7 prep):**
- New `backend/app/routes/images.py`: `GET /images/tmdb/{filename}` with regex whitelist `^[A-Za-z0-9._-]+\.(jpg|jpeg|png|webp)$`, atomic write to `settings.image_cache_path/w185/`, `Cache-Control: public, max-age=31536000, immutable`, `X-Cache: HIT|MISS`. Status: 400 / 404 / 502 mapping. 8 unit tests.

**LLM provider expansion:**
- **OpenAI:** `OpenAIClient` using `AsyncOpenAI` + `chat.completions` + `response_format={"type":"json_object"}` + `max_completion_tokens` (GPT-5 family rejects `max_tokens`). Live verified end-to-end with `gpt-5.5` on Congo + Pulp Fiction; quality on par with Sonnet, including Vincent Vega correctly flagged dead.
- **Gemini:** `GeminiClient` using `google-genai`'s `client.aio.models.generate_content` + `response_mime_type="application/json"` + `system_instruction`. Supports both API-key (AI Studio) and Vertex AI / ADC modes via `GOOGLE_CLOUD_PROJECT` env. Live verified with `gemini-2.5-pro` once user enabled billing on the AI Studio side. Caught Herkermer Homolka name (Sonnet had Rudolph), Captain Muguru, Original Zinj Expedition. Quality in the Sonnet / GPT-5.5 league.
- **Defensive `_strip_fences`** in `call_and_validate` — runs on both first-try and retry text before `_check_refusal` and `model_validate_json`. Catches the markdown-fence wrapping Haiku produces; also defends against future small-tier OpenAI/Google models. Retry message hardened: "Return only the raw JSON object — no \`\`\`json fences, no preamble, no trailing prose."
- **Haiku 4.5 removed** from `VALID_MODELS`, frontend dropdown, and `MODEL_ETAS` after side-by-side evals on Congo and Pulp Fiction showed it fabricating ("Taman Harper", "Trudi Styler"), getting deceased flags wrong on Munro and Vincent Vega, and omitting Marvin entirely. Kept in `_MODEL_QUALITY_ORDER` and cost table for historical dev-DB rows.

**Public deploy of charactermap.torgersen.ai:**
- Cloudflare DNS A record (DNS-only / grey cloud, matching radio/kanban) → 204.168.184.185.
- VPS nginx (single monolithic config in `usv_nginx` Docker container): added `charactermap.torgersen.ai` to the port-80 server_name list for ACME, then appended a full 443 server block modeled on radio's pattern (lfc backend at 10.0.0.2, SSE-friendly `/api/jobs/`, image-proxy block with the `tmdb_images` cache zone).
- `proxy_cache_path /var/cache/nginx/tmdb levels=1:2 keys_zone=tmdb_images:10m inactive=30d max_size=5g;` added to the `http{}` block.
- Let's Encrypt cert issued via certbot HTTP-01 webroot, copied into the bind-mount as `charactermap.fullchain.pem` / `charactermap.privkey.pem`.
- `docker-compose.yml` on lfc: api + frontend now bind on **both** `127.0.0.1:8201/8202` (local dev) **and** `10.0.0.2:8201/8202` (WireGuard tunnel from VPS).
- End-to-end live: frontend 200, `/api/health` ok, `/api/resolve` returned 5 Congo candidates, `/api/adaptations/680/cast` returned full Pulp Fiction cast, `/images/tmdb/…` HIT on both lfc backend cache and VPS nginx cache.

**Planka backlog brought up to SPEC parity:**
- Filed 15 new cards covering SPEC §16 deliverables #35-53 that weren't tracked yet (Phase 5 Turnstile/rate-limits/cost-guard/limits-endpoint, Phase 6 email/error-states/privacy/analytics/golden-set/fabrication-audit/prompt-iteration, Phase 7 .env-audit/GHCR/Grafana/Alertmanager/retention).

### Key Decisions

- **Haiku 4.5 is out.** Fence-strip alone wasn't the problem — even with fences handled, side-by-side evaluation showed Haiku violates the "omit when uncertain" prime directive: fabricated characters, wrong deceased flags on plot-pivot characters (Vincent Vega alive!), missed major characters (Marvin from Pulp Fiction). The CLAUDE.md rule says a thin correct map beats a complete invented one. Haiku produces complete invented ones. Kept in cost/quality-order tables (historical dev jobs), removed from user-facing input.
- **Three-provider parity, one fence-strip.** OpenAI's `response_format=json_object` and Gemini's `response_mime_type=application/json` both natively prevent fence-wrapping. Anthropic doesn't have an equivalent. The `_strip_fences` is provider-agnostic and runs on all paths — defensive even when not strictly needed.
- **GPT-5.5 pricing is a placeholder.** Used $1.25/$10 per MTok based on GPT-5 launch rates. Verified against actual generation costs to within rounding. Real rates need confirmation before public traffic; filed as Planka card.
- **Vertex AI fallback wired but dormant.** `GeminiClient` checks for `GOOGLE_CLOUD_PROJECT` — if set, uses ADC + Vertex AI; otherwise uses API key. Built in case the user's org policy ever blocks API keys. Currently the API-key path is active (after billing was enabled on the AI Studio side).
- **Collection aggregation defaults to on.** Pipeline calls `get_credits(..., aggregate_collection=True)` always. Standalone movies fall through to single-cast inside the function — no behavior change. The only cost is one extra `/movie/{id}` API call to check `belongs_to_collection`; cached by Redis under the existing `_tmdb_get` cache key.
- **Backend image proxy is the source of truth; VPS nginx is a second tier.** Both have their own cache. lfc cache persists across deploys (Docker volume); nginx cache is ephemeral inside the `usv_nginx` container. If the nginx cache is wiped, the next request to a previously-seen image is one round-trip slower but still cheap.
- **Docker single-file bind mounts pin to the original inode.** Editing nginx.conf with `awk > tmp && mv tmp orig` changed the inode; `usv_nginx` kept serving the kanban cert via SNI fallback because it still saw the old file. `docker restart usv_nginx` re-resolved the bind. Documented as a feedback memory + CLAUDE.md quirk so future sessions don't burn time on it.
- **`docker compose restart` doesn't re-read `env_file`.** When the user added a new Google API key, the container kept its old empty value until `up -d --force-recreate`. Documented.
- **VPS access pattern reused.** `ssh espen@torgersen.ai`, dockerized nginx, monolithic config + Let's Encrypt webroot + WireGuard to lfc — same as kanban/radio. Captured in `reference_vps_access.md` memory so future agents inherit the layout.

### Test Status

- **135 backend unit tests passing.** New additions: 8 markdown headshot/attribution tests, 5 PDF rewrite tests, 13 pipeline fence-strip tests, 8 collection-cast tests, 8 adaptations-route tests, 8 images-route tests.
- **Live verified end-to-end through the public URL** (https://charactermap.torgersen.ai/): frontend 200, API health ok, resolve returns candidates, adaptations cast returns 30 Pulp Fiction members, image proxy HIT on both cache tiers.
- Generation quality verified live for Congo + Pulp Fiction across all three providers (Anthropic Sonnet, OpenAI GPT-5.5, Google Gemini 2.5 Pro).

---

## Session 7 — 2026-05-19

### What We Built

**Phase 5 + 6 backend** (SPEC §16 deliverables #35–39, #42):
- **Daily cost guard** (`app/cost/__init__.py`): `get_today_cost` / `record_cost` against `daily_costs`. `POST /api/jobs` returns 503 `DAILY_BUDGET_EXHAUSTED` when at limit. Pipeline debits after success only — Opus runs can't pre-empt the budget. Cache hits bypass the gate ($0 cost).
- **Sliding-window rate limits** (`app/security/rate_limit.py`): per-IP sorted-set log in Redis. 2/min, 5/hr, 15/day on jobs; 30/min, 200/day on resolve. Blocked attempts not recorded so spammers can't extend their own block. 429 with `Retry-After`.
- **`GET /api/limits`**: read-only `peek_remaining` for both endpoints plus daily-cost remaining.
- **Turnstile** (`app/security/turnstile.py`): server-side siteverify with fail-closed behavior. Skipped in dev when `TURNSTILE_SECRET_KEY` is empty.
- **Analytics** (`app/analytics/__init__.py`, `app/routes/analytics.py`): `POST /api/analytics` with §14.2 enum validation. Server-side emissions wired from jobs route (`form_submit`) + resolve route (`resolve_hit`/`no_results`) + pipeline (`job_done`/`failed`/`refused` with `duration_ms`).
- **Resend email** (`app/email/mailer.py`): HTML+text body, PDF attached, share link, TMDb attribution (conditional), "what this is" honesty footer, delete-my-map mailto. Inline 600px PNG deferred (no server-side React Flow renderer).
- Added `fakeredis` dev dep + per-test conftest fixture isolating the limiter.
- **173 backend unit tests passing** (was 135). New suites: cost_guard, rate_limits, limits_route, turnstile, analytics_route, analytics_emissions, email, pipeline_cost, resolve_resilience.

**Phase 5 + 6 frontend:**
- `Turnstile.tsx` — vanilla CF script loader, single-use token reset on submit, dev-skipped when env key absent.
- `useLimits` hook + "N generations left today" hint above Generate (hides at full quota, shows "Daily limit reached" at zero).
- Friendly error copy mapping (`RATE_LIMITED` / `DAILY_BUDGET_EXHAUSTED` / `TURNSTILE_FAILED`). `cycleModel=1` retry path from refused JobView actually cycles through `MODEL_CYCLE` and re-prefills the search box via new `TitleSearch.initialValue` prop.
- `AttributionFooter` (TMDb + Open Library) + `CookieBanner` (one-time, dismissed in localStorage). Both rendered site-wide except JobView.
- `/privacy` + `/terms` filled to SPEC §15 — per-vendor privacy-policy links, Hetzner specificity, "no tracking/advertising" section, TMDB+OL attribution section on Terms.
- `trackEvent` helper in `api/client.ts`. `share_click` from `ShareButton`, `recent_map_click` from the recent-maps list.

**Bugs squashed in production:**
- **Resolve route 500 on short queries.** Open Library returns 422 for "It", TMDb 5xx during outages; both propagated as 500, WebKit fetch showed "Load failed". Now `search_books` + `_tmdb_get` catch `HTTPStatusError` and return empty.
- **VPS nginx 301 on `POST /api/jobs`.** `location /api/jobs/` (trailing slash) for SSE made nginx auto-301 `POST /api/jobs` to `/api/jobs/`; WebKit refuses to replay POST across 301 and surfaces "Load failed". Fixed by scoping SSE block to `~ ^/api/jobs/[^/]+/stream$`. Latent on all desktop browsers (they follow 301-on-POST de-facto) — iPad caught it.
- **Vite cache-collision + Docker build-arg.** Frontend wasn't picking up `VITE_TURNSTILE_SITE_KEY` because docker-compose `build: ./frontend` had no `args:`. Wired ARG → ENV through Dockerfile and `${TURNSTILE_SITE_KEY:-}` through compose.

**UX polish:**
- Title search wrapped in real `<form>` with `autoComplete="on"` + `name` + `type="search"` + `enterKeyHint="search"` so mobile keyboards surface previously-typed titles natively.
- Spoiler-warning checkbox hidden (WhatThisIsBanner already sets expectations); `acknowledged_spoilers: true` hardcoded in `createJob`. Backend gate kept.

### Key Decisions

- **Cache hits bypass the cost guard, NOT the rate limiter.** A $0 cached response is fine to serve over budget; the rate limit still protects against scrapers cycling cached titles.
- **Guard order in `POST /api/jobs`:** rate-limit → Turnstile → spoiler-ack → cache → cost-guard → queue. A user at the daily limit who hits a cached title still gets the map; one who misses cache gets 503.
- **Blocked rate-limit attempts are NOT recorded.** Otherwise spammers extend their own block window indefinitely.
- **Server-side PNG render deferred.** Email ships without the inline 600px preview that §10.5 promises. Two viable paths in the follow-up card (frontend POSTs PNG to backend, or Playwright server render). Path 1 is cheaper.
- **Turnstile is OFF in production right now.** Widget got stuck at "verifying" on iPad — root cause is `charactermap.torgersen.ai` is on Cloudflare DNS-only (grey cloud), but Turnstile requires the domain to be proxied (orange cloud) so `/cdn-cgi/*` traffic terminates at CF edge. Re-enabling requires the CF-proxy tradeoff decision. Both keys blanked in lfc `.env`.
- **Vite content-hash collisions are real.** The no-site-key build produced the same `index-5rcX9ZZy.js` hash as a much earlier build — `--no-cache` Docker rebuild didn't change the hash because the bundle bytes were identical. Bust at the browser level (private window) when this happens.
- **Browser-native form history beats a custom dropdown.** Wrapping the title input in a real form with `name` + `autoComplete` is one diff, zero new code, surfaces previous titles directly in the iOS/Chrome keyboard suggestion bar.
- **iPad UX is the real test environment.** All three of today's production bugs (resolve 500, nginx 301-on-POST, Turnstile orange-cloud requirement) were invisible on desktop and only manifested on iOS WebKit. Worth running new features through an iPad before declaring done.
- **66% TMDB-cast match rate on Pillars is normal.** 19 of 30 characters got a headshot; the 11 without are children, minor monks, and historical cameos that the 2010 miniseries didn't credit. The honest "no headshot" UI (initials) is better than a fake match.

### Test Status

- **173 backend unit tests passing** (was 135). 8 skipped (PDF — requires pdflatex). 19/19 frontend vitest passing. TypeScript clean, vite build clean.
- **Live verified:** /api/health 200, /api/limits returns full structure, /api/jobs accepts POSTs returning 202 + job_id, full resolve→generate→render flow tested with Pillars of the Earth (Opus + Sonnet), iPad end-to-end working.
- **Not verified yet:** golden-set across all 10 works, fabrication audit on *A Fire Upon the Deep*. These are #43 + #44 (manual, by the user).

---

## Session 8 — 2026-05-19

### What We Built

**TV credits use `/aggregate_credits` instead of `/credits`** (commit b78a950). User reported low headshot coverage on The Night Manager (2/16 matches — only Tom Hiddleston + Hugh Laurie, who bridge both seasons). TMDB's `/tv/{id}/credits` returns only the current main cast — for S2 (2025) of Night Manager that's a near-disjoint cast from S1, so the LLM's S1 character names (Burr, Jed, Corky, Sandy, Daniel Roper) never matched. `/aggregate_credits` returns 134 cast entries spanning all seasons, with `roles: [{character, episode_count}, ...]` per actor. `_parse_cast` now flattens per-role so each (actor, character) is independently fuzzy-matchable. cast_limit bumped 30→80 for enrichment. Result on Night Manager: 16/16 headshots.

**PDF photo-left, text-right character layout** (commits d2b7123 + 5d434d5). User wanted photo+text side-by-side instead of stacked. Went through three iterations:
1. Minipages with `\hfill` — worked but looked identical to "photo above text" because nothing forced the visual difference.
2. `wrapfig` — true magazine-style text wrap, but threaded figures through paragraphs in a way that detached them from their heading. User saw 6 names but 4 photos with no clear pairing.
3. Top-aligned minipages with `\hspace` — `[t]` alignment guarantees photo-top = heading-top by construction. Each character is a self-contained block with `\par\vspace{1.6em}` between. Final answer.

Fixed a pre-existing silent failure: pdflatex can't render ⚠ (U+26A0). Any map with a coverage_note rendered no PDF artifact at all — only markdown landed, no error surfaced to the user. `_strip_pdf_unsafe_chars` maps ⚠ → `!` before pandoc. Also required: `header-includes=\\usepackage{graphicx}` because the character-block rewriter consumes all markdown image syntax, so pandoc no longer auto-loads graphicx.

**Rate limits loosened for dev iteration** (commit 5d434d5). User hit "Sending requests too quickly" while iterating. `JOBS_WINDOWS` bumped from 2/5/15 to 8/30/60 with a comment marking it as pre-launch temporary. Tests now read the limit from `JOBS_WINDOWS` (was hardcoded), so the next change is a one-line edit.

**Planka:** filed TV season selector card (the deeper feature underneath the Night Manager issue — pick S1 vs S2, pin generation to a specific season).

### Key Decisions

- **`/aggregate_credits` is correct, default to it for TV.** Even for single-season shows the endpoint behaves identically to `/credits`. No reason to keep the broken path around. Movies stay on `/credits` (no `aggregate_credits` equivalent for film).
- **Top-aligned minipages beat wrapfig.** `wrapfig` threads figures through paragraph structure; it's correct LaTeX behavior for magazine-style flow but wrong for "trading card" layout. The 2-minipage pattern with `[t]` is the right tool — photo and heading-line are siblings in the same box, photo never escapes into the adjacent character's text.
- **Don't switch to lualatex.** Considered it for full UTF-8 support; would have required `texlive-fonts-extra` + `texlive-luatex` Docker deps and lmodern OTF font setup. `_strip_pdf_unsafe_chars` is a 2-line fix for the one char we actually emit. Add to the fallback map as more cases emerge.
- **Sanitize at the boundary, not the source.** Could have stripped ⚠ in `markdown.py` so the .md file never has it either. Chose to leave .md clean (⚠ is correct for markdown viewers) and only sanitize in the pdf.py pre-processor. Mirrors the existing `_REMOTE_IMAGE_RE` pattern (PDF-only rewrites stay in pdf.py).
- **Dev rate limits are public-launch debt.** 8/30/60 will burn 80% of the cost cap in a single bad day if a script gets at it before launch. Acceptable for now because the daily cost guard is a hard backstop, but tighten back to 2/5/15 before opening up.

### Test Status

- **186 backend unit tests passing** (was 173). 8 skipped (pdflatex-gated). New: `test_tv_aggregate_credits.py` (6 tests covering /aggregate_credits routing + role flattening), `test_pdf_character_blocks.py` (7 tests for the regex + LaTeX escape + minipage rewriter).
- Existing rate-limit + limits-route tests updated to read from `JOBS_WINDOWS` instead of hardcoded 2/5/15.
- **Live verified:** Night Manager re-render returned 16/16 headshots. Pillars PDF re-render: 18 headshots in side-by-side layout, no silent failure on the coverage-note ⚠.

---

## Session 9 — 2026-05-19

### What We Built

**Two-stage grounded character map pipeline** (commits 1ba31d0, 7f2adca, 8fb0e76). The session began as prompt iteration — added explicit anti-fabrication rules (name-source check, faction-padding test, antagonist/climax-reveal check, under-fill rule) to `character_map.md`, threaded `--char-cap` through `dev-generate.py` and `run_golden_set.py`, ran a four-way A/B (baseline vs v1 vs v2 vs GPT-5.5) on Congo and Devil's Star. Result: prompt iteration halved fabrication count but did not reach zero. The user-provided Congo ground-truth list (Karen Ross, Peter Elliot, Amy, Travis, Munro, Kahega, Jan Kruger, Misulu) exposed a knowledge-ceiling: no model recalled Jan Kruger or Misulu from memory regardless of prompting effort.

Pivoted to web-search grounding after user feedback (*"it is disappointing that a good old google search gives you better answers"*). Considered a bespoke-scraper architecture (Wikipedia + Wikidata + Goodreads clients + orchestrator, ~700 lines of plan) — abandoned in favor of Anthropic's `web_search_20250305` tool, which collapses the same idea into one provider feature. Two-stage shape:

- **Stage 1** (`character_map_analysis.md`): claude-sonnet-4-6 with `web_search` enabled produces verified Cast + True Final Resolution + Adaptation prose with cited URLs. The closed list is the Stage 1 output, not a hand-built data fetch.
- **Stage 2** (`character_map_structuring.md`): same model converts the analysis into `CharacterMap` JSON, treating Cast section names as a closed list. Names are *inputs*, not predictions.

Smoke-tested on Congo end-to-end (Jan Kruger + Misulu both present, zero fabrications, full adaptation_note). Ran the 10-work golden set: 0 closed-list violations, +50 real characters recovered vs the cap=20 ungrounded baseline. Discovered and fixed a Stage 2 over-trim bug — the bidirectional closed-list rule needed to spell out *don't drop* as explicitly as *don't add* — then re-ran cleanly. Total session run cost: ~$11.79 across 54 LLM calls.

**Pipeline integration + production deploy** (commits 7f2adca, 8fb0e76). Wired the two-stage path into `run_pipeline` behind `settings.enable_grounding=True` (default). Anthropic-only for now — OpenAI/Gemini stay on the legacy single-stage path. Stage 1 prompt uses `cache_control: ephemeral` so warm-cache cost is ~$0.18/job (vs ~$0.66 cold). Added new refusal code `grounding_failed`. Extended `CharacterMap` schema with optional `adaptation_note` field (populated when Stage 1 surfaces a Key Adaptation Differences section). Hit and fixed RQ's default 180s `job_timeout` (grounded jobs run 90-200s easily) — bumped to 600s. End-to-end Tokyo Express on production verified: Yasuda correctly as antagonist, Ryōko's late-act twist at sp=3, all victims marked dead.

**Live stage labels on the in-progress view** (commit 32acc76). Replaced the static "Generating your map…" with stage-aware copy that reflects what the worker is doing. Added `Job.progress_stage` column (migration `0004`) with codes `searching | structuring | enriching | rendering`. Worker updates it at each pipeline transition; SSE carries it; frontend maps to user-facing copy via `getStageLabel()`. Progress bar fill mapped per-stage (searching=25%, structuring=65%, etc.). `MODEL_ETAS` refreshed to grounded reality: Sonnet 4.6 = "90–180s (web-grounded)". Also restructured `run_pipeline` so `status='done'` flips AFTER artifact rendering completes — eliminated a latent race where the frontend could fetch artifacts before the worker wrote them.

**Time-tuning ledger** (commits 95ce8c6, c06185f → b708669, ebbb604, 6cd8653 → d5a746f). User asked to cut "serious time" off the ~236s baseline. One-at-a-time protocol: change a knob, measure, KEEP if quality survives else REVERT.

| Step | Change | Wall (Embassy) | Cost | Verdict |
|---|---|---:|---:|---|
| 1 | `max_searches: 8 → 3` | 204s | $0.18 | KEEP ✓ |
| 2 | Stage 2 → Haiku 4.5 | 174s | $0.11 | REVERT ✗ (fabricated `JoaQuin` via WikiWord pattern-completion) |
| 3a | Drop "Structural Metaphors" + "Systemic Nuance" sections | output -22% | $0.16 | KEEP ✓ |
| 4 | Single-stage (eliminate Stage 2) | 102s on Embassytown | $0.085 | PROVISIONAL |
| 5a | Single-stage validation on Congo + Tokyo Express | — | — | REVERT step 4 ✗ |

Step 4 looked like a 50% win on Embassytown but Step 5a's cross-validation found catastrophic regression — single-stage on Congo missed **Munro, Kahega, Misulu** and invented **"Charles Travis"** (a Munro+Travis composite) and **"Ghost Tribe Member (Uncredited)"** (film-credits leakage). On Tokyo Express it missed **Yasuda (the actual killer), Mihara, Sayama, Ryōko** and filled with invented Japanese-sounding names. Reverted to Step 3a state. Net session win: cost down ~20% from baseline ($0.20 → $0.16), wall time ~unchanged after noise.

### Key Decisions

- **The closed list is the cache, not the contract.** We never built the bespoke Wikipedia/Wikidata/Goodreads scrapers from the original grounding plan (now sitting uncommitted at `docs/superpowers/plans/2026-05-19-grounding-pipeline.md`). Anthropic's `web_search_20250305` tool collapsed three custom modules + an orchestrator into one client method. The grounding plan file is preserved as a record of the road not taken; if Anthropic's tool ever stops being good enough we have the design.
- **Two-stage is load-bearing, not just decorative.** The Step 5a regression proved this. The prose intermediate isn't there for users to read — it's there to *commit the model to a verified cast list before it structures it*. Stage 1 = retrieval (with the analyst freedom to reason about source credibility). Stage 2 = structured projection under a closed-list rule. Collapsing them produces composites (Charles Travis) and silent omissions (Yasuda) because the model has too many concurrent constraints. Don't reattempt single-stage without a different mitigation; `_run_grounded_single_stage` stays in the code as a reference implementation with a comment explaining why it isn't wired.
- **Haiku 4.5 fabricates even under closed-list.** The JoaQuin failure on Step 2 was diagnostic. Haiku's `name_evidence` literally cited the WikiWord naming convention as evidence — pattern-completion masquerading as source-grounding. The earlier removal from `VALID_MODELS` (Session 5/6) was for ungrounded fabrication; closed-list doesn't save it. Sonnet stays on Stage 2.
- **Never delete maps from `jobs.character_map`.** Each map is a free serving entry for `find_best_cached_job`. Memorialized in `feedback_never_delete_maps.md`. The existing `Job.deleted_at` column stays for explicit user-initiated deletion only; nothing else writes to it. The `artifact_retention_days: 30` setting in `config.py` is dead code — it referenced nothing and was *not* about map JSON, only the MD/PDF artifacts on disk.
- **`status='done'` flips last.** Reordered `run_pipeline`'s else branch so `done` is committed AFTER markdown + PDF artifacts are on disk. Without this, the SSE stream's `done` event can fire while the worker is still rendering; the frontend then 404s on artifact fetches. Pre-existing latent bug — new progress flow made it impossible to ignore.
- **Cost is dominated by output tokens, not search latency.** Three searches at $0.01 each = $0.03; Stage 1's 5600 output tokens at $15/M = $0.084. The wall-time win from `max_searches: 8 → 3` was 13%, not 50%, because search count was never the bottleneck — output prose was. Step 3a's `-22% output tokens` is the more durable win even if a single sample was noisy.
- **Embassytown was a softball.** It has a clean Wikipedia article that dominates web search. Single-stage looked great on it. Congo and Tokyo Express have noisy mixed signals (film extras pages, older Japanese sources). One-work validation is insufficient — any future grounding change needs at least Congo + Tokyo Express + Embassytown as a regression triple.

### Test Status

- **186 backend unit tests still passing** (no test regression across the session). 8 skipped (pdflatex). Tests not yet written for the new grounded path (`_run_grounded`, `_run_grounded_single_stage`, web_search code path, progress_stage transitions) — covered live by production smoke tests but no unit harness yet. Worth filing.
- **Production verified end-to-end** (commits deployed via `./deploy.sh`):
  - Embassytown grounded job ran clean, all key characters present, adaptation_note empty (no adaptation), 4 minutes total.
  - Tokyo Express grounded job: 11 characters, Yasuda as antagonist, Ryōko at sp=3, adaptation_note populated about the 1958 Toei film.
  - Stage transitions visible in SSE: `searching → structuring → enriching → rendering → done`.
- **Cumulative session LLM spend: ~$11.79** across 54 calls (1.95M input tokens, 351K output, 72 web_search calls). Detailed breakdown saved at `tuning/run-2026-05-19-searchcount/` (mixed Embassytown step-by-step artifacts and the full 10-work golden batch under `tuning/run-2026-05-19-full2/`).

## Session 10 — 2026-05-29

### What We Built

**Merged the web-client backlog, fixed a launch-blocking bug, built (but held) the GoT-scale map feature, and spun out a new companion app.**

- **Merged two web-authored PRs to `main` + deployed to lfc.** PR #1 — drop the deprecated `temperature=` from the `web_search` call (it 400s on Sonnet 4.6 / Opus 4.7+). PR #2 (`claude/got-actor-photos`) — Claude **Opus 4.8** as the top-tier model, a GoT-scale **Westeros geographic view**, and a Wikipedia actor-photo fallback. Folded the dev-script `temperature` removal into PR #2 before merging.
- **Fixed `JOB_CREATE_FAILED`** (systematic debugging → root cause): PR #2 widened `VALID_CHARACTER_CAPS` to `{…,100,150}` in the Pydantic validator + frontend dropdown but left the DB `ck_jobs_character_cap` CHECK at `{10..50}` with no migration, so cap=100/150 INSERTs hit `CheckViolationError`. Shipped migration `0005`, the matching `tables.py` constraint, and a regression test (`test_db_cap_constraint_matches_valid_caps`) asserting the constraint == `VALID_CHARACTER_CAPS`. Deployed (alembic at 0005).
- **Built the GoT-scale map feature on `feat/got-scale-maps`** (brainstorm → spec → plan → subagent-driven, 10 tasks): `is_pov`; cap-aware Stage-1 retrieval (`_searches_for_cap` = 4/8/12 by cap); Stage-1 prompt roster-completeness + awoiaf source + a `Viewpoint (POV)` section; Stage-2 populates `is_pov`; fixed-height cards (overlap fix); POV ★; in-app fullscreen toggle; **streaming Stage-2** (`_max_tokens_for_cap` + `messages.stream` above 16384 — large rosters were truncating to `invalid_json`); **versioned cache key** (`PIPELINE_VERSION`).
- **Validated live** (Opus 4.8): GoT cap=50 → 48 chars (fresh, cache-versioning confirmed); cap=100 → 83 via streaming; Congo → 13 chars / 0 POVs (dynamic scaling). **POV-via-LLM was unreliable** (missed Tyrion, false-flagged Tywin, varied run-to-run) → branch **HELD undeployed**.
- **Spun out `../westeros-companion`** — a standalone GoT/ASOIAF companion that grounds per-chapter maps deterministically in awoiaf (exact POVs, free serving). Reuses only this app's React Flow canvas. See that repo's own chronicle.

### Key Decisions

- **Cap is a ceiling, not a quota; POV stars only when a work has viewpoint structure.** Roster size + POV count scale to each work — GoT's 50/8 were test fixtures, never hardcoded. Saved as a cross-session memory.
- **Two validation-found issues drove design changes:** Stage-2 output truncation → stream the structuring call with cap-scaled `max_tokens`; cache staleness (cache keyed on work+cap, not model/prompt) → version the cache key so improvements aren't masked by stale maps. Old maps are never deleted — they just stop matching.
- **POV accuracy belongs to deterministic wiki grounding, not the LLM.** This untangled the general app's deploy decision from POV-perfection and motivated the separate companion app.
- **The awoiaf per-chapter idea is a different product** (no title search / LLM / cost) → new repo, reusing only the canvas.

### Test Status

- `feat/got-scale-maps`: **217 backend + 26 frontend tests pass**; new coverage for `is_pov`, `_searches_for_cap`/`_max_tokens_for_cap`, the streaming path, cache-versioning, and a no-overlap layout invariant. Validated live but **not deployed**.
- `main` (deployed): cap-constraint migration `0005` + regression test green; `JOB_CREATE_FAILED` resolved in production.
