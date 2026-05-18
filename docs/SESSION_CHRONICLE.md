# Session Chronicle

Character Map Generator · Chronological build log — appended at the end of each session.

Last updated: Session 1 · 2026-05-18 (wrapup)

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
