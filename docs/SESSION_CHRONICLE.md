# Session Chronicle

Character Map Generator · Chronological build log — appended at the end of each session.

Last updated: Session 2 · 2026-05-18 (wrapup)

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
