# Design: GoT-scale maps — completeness, POV stars, layout, fullscreen

**Date:** 2026-05-29
**Status:** Approved (brainstorm) — pending spec review
**Topic:** Make large-ensemble maps complete and legible: grounded retrieval that
hits the full major cast, POV characters marked with a star, no overlapping
cards, and a fullscreen map mode.

---

## 1. Context / problem

A `A Game of Thrones` map generated on Opus 4.8 at `character_cap=150` came back
with only **31 characters / 24 relationships**, looked cramped (cards overlapping
inside faction boxes), wasted ~45% of the viewport on title/description/sidebar
chrome, and gave no visual signal for the books' defining structural feature —
POV (viewpoint) characters.

Root causes (verified):

- **Thin cast:** `_run_grounded` Stage 1 (the `web_search` analysis call) is **not
  cap-aware** — it loads the analysis prompt with no target and runs `max_searches=3`
  (the hardcoded default). It enumerates ~30 "structurally important" characters
  regardless of cap. Stage 2 (structuring) *is* cap-aware but can only structure
  what Stage 1 found, so the cap is a **ceiling, never a floor**. (Earlier gpt-5.5
  ungrounded run produced 50; grounded Opus produced 31.)
- **Overlap:** `layout.ts` positions cards on a grid using a fixed
  `NODE_HEIGHT = 96`, but rendered card height grows with name/role/description
  text. Taller cards overflow into the row below.
- **Chrome:** title + author + description + collapsible "Setting" block + right
  sidebar + minimap squeeze the canvas into a fraction of the screen.
- **No POV signal:** the data model has no notion of a viewpoint character.

## 2. Goals / acceptance criteria

1. A grounded `GoT` request at `cap≥50` surfaces **all 50 characters** in the
   reference roster (Appendix A), grouped sensibly.
2. The **8 recurring AGoT POV characters** (Appendix B) render with a **★** marker;
   non-POV characters do not. The prologue POV (Will) is starred if surfaced.
3. **No overlapping cards** at any faction size.
4. A **fullscreen toggle** expands the canvas to fill the viewport (chrome hidden,
   minimal floating controls), exitable via ✕ or `Esc`.
5. **No correctness regressions:** golden-set re-run keeps 100% `spoiler_level`
   coverage and zero flagged fabrications across all 10 works; 210 unit tests pass.
6. **Dynamic per work (not GoT-specific):** the numbers above are *acceptance
   fixtures for the GoT test only*. Roster size scales to the requested cap and
   to what each work verifiably supports — the cap is a **ceiling, never a
   quota**, and padding is forbidden (a 12-character novella returns 12). POV
   stars appear **only** when a work has named viewpoint structure; zero POVs is
   the common, correct case. Verified against a contrasting small-cast / no-POV
   work (Congo): real cast size, not padded; POV count 0.

## 3. Non-goals (YAGNI)

- No decluttering of the *default* JobView layout (fullscreen toggle only — user
  decision).
- No hard per-work `web_search` domain allowlist wired on by default (soft prompt
  guidance instead; the client param is added but unused).
- No change to the faction grouping scheme (the LLM still chooses factions; the
  location-grouping in the cheat sheet already maps to `home_region` / Geographic view).
- POV detection beyond ASOIAF-style named viewpoint chapters is out of scope; the
  field simply stays `false` for works without that structure.

---

## 4. Design

### ① Stage-1 grounded retrieval — cap-aware, sourced, POV-aware

**Files:** `backend/app/worker/pipeline.py`, `backend/app/llm/anthropic_client.py`,
`backend/prompts/character_map_analysis.md`.

- Make Stage 1 **cap-aware**: render the analysis prompt through the existing
  `_render_system_prompt(template, cap)` (`{CHAR_CAP}` substitution) so the prompt
  states a target count.
- **Scale search budget with the cap** via a helper
  `_searches_for_cap(cap)` → `cap<=50 ? 4 : cap<=100 ? 8 : 12`; pass it as
  `max_searches` into `client.generate_with_web_search(...)` from `_run_grounded`
  (currently relies on the default 3).
- **Broaden enumeration** in the analysis prompt: for large-ensemble works, include
  recurring supporting cast (household, advisers, bodyguards, wards, named
  retainers), not just plot-pivotal figures. Keep the "omit when uncertain" rule —
  only characters verifiable via search.
- **Source of truth:** instruct Stage 1 to seek the work's dedicated comprehensive
  wiki, naming `awoiaf.westeros.org` as authoritative for A Song of Ice and Fire /
  Game of Thrones.
- **POV identification:** Stage 1's Cast section flags which characters are
  narrative-viewpoint characters (chapters/sections told from their perspective),
  grounded from the source.
- `generate_with_web_search` gains an optional `allowed_domains: list[str] | None`
  param threaded into the tool config (`{"type": "web_search_20250305", ...,
  "allowed_domains": [...]}` when provided). Default `None` → unchanged behavior.

### ② POV characters — data + visual

**Files:** `backend/app/models/character_map.py`,
`frontend/src/types/characterMap.ts`, `backend/prompts/character_map_structuring.md`,
`frontend/src/components/CharacterCard.tsx`, Legend component.

- Add `is_pov: bool = False` to the `Character` Pydantic model and `is_pov?: boolean`
  to the TS `Character` type. Lives in the `character_map` JSONB blob — **no DB
  migration** (same as `home_region`).
- Stage 2 structuring prompt populates `is_pov` from Stage 1's POV flags under the
  closed-list rule: `true` only for genuine viewpoint characters, default `false`,
  never invented.
- Frontend renders a **gold ★** on POV cards (badge near the name) and adds a
  Legend row: "★ POV character".

### ③ Card-overlap fix — uniform card height

**Files:** `frontend/src/layout/layout.ts`, `frontend/src/components/CharacterCard.tsx`.

- Make cards a **true uniform height**: enforce a fixed height on the card and
  `line-clamp` the description (~2 lines, overflow hidden) so rendered height always
  equals the layout's `NODE_HEIGHT`. The grid math then never collides.
- Re-confirm / adjust `NODE_HEIGHT` so name + role + clamped description fit at the
  current font sizes (DPI bump is `17px` root). The card's `style.width` must stay
  equal to `NODE_WIDTH` (existing constraint).
- Rejected alternative: variable per-row heights from estimated text size — fragile
  because React Flow positions are computed before render; estimation drift
  reintroduces overlap.

### ④ Fullscreen toggle

**Files:** `frontend/src/components/CharacterMapCanvas.tsx` (or JobView), new state +
keyboard handler.

- A **⛶ maximize button** on the canvas. Toggling on renders the React Flow
  container as a `fixed inset-0 z-50` overlay filling the viewport; header, Setting
  block and sidebar are not shown.
- A minimal floating control cluster remains: **Exit (✕)**, zoom controls, Reset
  layout, Connections toggle. The minimap stays.
- `Esc` or ✕ exits to the normal view. **In-app overlay**, not the browser
  Fullscreen API (keeps our controls, integrates cleanly with React Flow). Body
  scroll locked while active.

---

## 5. Validation plan

- **GoT acceptance:** regenerate `A Game of Thrones` grounded at `cap=50` (and a
  spot check at `cap=150`); assert all 50 Appendix-A characters present and the 8
  Appendix-B POVs flagged `is_pov`.
- **Golden-set regression** (mandatory — Stage 1 prompt edited):
  `python scripts/run_golden_set.py --model claude-sonnet-4-6` — 100% `spoiler_level`
  coverage, zero fabrications, no character-count regressions on the other 9 works.
- **Unit tests:** existing 210 pass; add tests for `is_pov` round-trip
  (schema + structuring), `buildLayout` produces no overlapping card rects, and the
  fullscreen toggle mounts/unmounts the overlay + `Esc` handler.
- **Cost/latency budget:** Stage 1 on large-cap jobs ≈ doubles (more searches +
  output tokens); GoT cap=50 ≈ $0.50–0.80 and +60–120s. Accepted.

## 6. Risks

- **Fabrication under pressure:** pushing for more characters could tempt
  invention. Mitigated by keeping the grounded "verifiable only" rule and grading
  against a fixed roster; golden set is the backstop.
- **Search-budget cost creep:** capped by `_searches_for_cap`; daily cost guard
  remains.
- **POV misclassification:** for non-ASOIAF works the model could over-flag.
  Mitigated by the default-`false` closed-list rule and the prompt scoping POV to
  works with named viewpoint structure.
- **lfc deploy:** no migration needed; `deploy.sh` rebuilds + `alembic upgrade head`
  (no-op here). Frontend rebuild required.

---

## Appendix A — GoT acceptance roster (50, source: cheat sheet + awoiaf)

- **Winterfell (15):** Eddard "Ned" Stark, Catelyn Stark, Jon Snow, Robb Stark,
  Sansa Stark, Arya Stark, Bran Stark, Rickon Stark, Osha, Theon Greyjoy, Old Nan,
  Rodrik Cassel, Jory Cassel, Maester Luwin, Hodor.
- **The Wall (4 + Jon Snow):** Benjen Stark, Alliser Thorne, Samwell Tarly,
  Jeor Mormont.
- **The Eyrie (3):** Jon Arryn, Lysa Arryn, Robin Arryn.
- **King's Landing (22):** Robert Baratheon, Cersei Lannister, Stannis Baratheon,
  Renly Baratheon, Davos Seaworth, Melisandre, Joffrey Baratheon, Myrcella Baratheon,
  Tommen Baratheon, Tywin Lannister, Jaime Lannister, Tyrion Lannister, Petyr
  Baelish, Loras Tyrell, Maester Pycelle, Varys, Barristan Selmy, Bronn, Gregor
  "The Mountain" Clegane, Sandor "The Hound" Clegane, Syrio Forel, Gendry.
- **The East (6):** Rhaegar Targaryen, Viserys Targaryen, Daenerys Targaryen,
  Jorah Mormont, Doreah, Khal Drogo.

## Appendix B — AGoT POV characters (starred)

Eddard Stark, Catelyn Stark, Sansa Stark, Arya Stark, Bran Stark, Jon Snow,
Tyrion Lannister, Daenerys Targaryen (8 recurring) — plus the prologue POV
**Will** if surfaced. Source of truth: `https://awoiaf.westeros.org/index.php/Portal:Characters`.
