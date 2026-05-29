# GoT-scale Maps Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make large-ensemble character maps complete and legible — grounded retrieval that hits the full major cast, POV characters marked with a ★, no overlapping cards, and an in-app fullscreen map mode.

**Architecture:** Four mostly-independent changes. Backend: make the grounded Stage-1 analysis call cap-aware and scale its web-search budget, add a `Viewpoint (POV)` section to the analysis prompt and an `is_pov` field through Stage-2 structuring + the schema. Frontend: give character cards a fixed height (kills the overflow-into-next-row overlap), render a ★ on POV cards, and add a fullscreen toggle that hides all chrome.

**Dynamic per work — not GoT-specific.** Nothing here hardcodes 50 characters or 8 POVs. Roster size scales to the *requested cap* and to *what each work verifiably supports* — the cap is a ceiling, never a quota, and padding is forbidden (a 12-character novella returns 12). POV stars appear *only* when a work has named viewpoint structure; the common case is zero POVs. The GoT 50-character roster and 8 POVs are **acceptance fixtures for the GoT test (Task 8)**, not values in code or prompts. Task 8 also verifies a contrasting small-cast / no-POV work to guard against padding and spurious stars.

**Tech Stack:** Python 3.12 / FastAPI / Pydantic / Anthropic SDK (`web_search` tool), React 18 / TS / React Flow / Tailwind 3.4, Vitest 3, pytest.

---

## Dev loop (how to run tests)

**Backend tests run inside the `charmap_api` container** (the host has no backend deps). Sync the working tree into the running container, then run the target test:

```bash
# Reusable: sync working tree → container and run one test file
docker cp backend/app charmap_api:/app/app && docker cp backend/tests charmap_api:/app/tests \
  && docker exec charmap_api python -m pytest tests/unit/<file>.py -q
```

**Frontend tests run on the host:**

```bash
cd frontend && npx vitest run src/layout/layout.test.ts
```

**Branch:** do this work on `feat/got-scale-maps` (cut from `main`), commit per task, open a PR + deploy at the end (Task 8).

---

## File structure

| File | Responsibility | Change |
|---|---|---|
| `backend/app/models/character_map.py` | Pydantic schema | Add `is_pov` to `Character` |
| `backend/app/worker/pipeline.py` | Grounded pipeline | `_searches_for_cap`; cap-aware Stage-1; scaled searches |
| `backend/app/llm/anthropic_client.py` | Anthropic client | `allowed_domains` param on `generate_with_web_search` |
| `backend/prompts/character_map_analysis.md` | Stage-1 prompt | Cap target, broaden enumeration, awoiaf source, Viewpoint section |
| `backend/prompts/character_map_structuring.md` | Stage-2 prompt | `is_pov` in schema + populate rule |
| `frontend/src/types/characterMap.ts` | TS types | Add `is_pov?` |
| `frontend/src/layout/layout.ts` | Layout math | Bump `NODE_HEIGHT`; set node `height` |
| `frontend/src/components/CharacterCardNode.tsx` | Card render | Fixed height + clamp (overlap fix) + ★ |
| `frontend/src/components/CharacterMapCanvas.tsx` | Canvas chrome | Fullscreen toggle + POV legend row |
| `backend/tests/unit/test_character_map_schema.py` | Schema tests | `is_pov` round-trip |
| `backend/tests/unit/test_grounded_retrieval.py` | New | `_searches_for_cap` + prompt-contract guards |
| `frontend/src/layout/layout.test.ts` | Layout tests | Fixed-height invariant |

---

## Task 1: `is_pov` on the data model

**Files:**
- Modify: `backend/app/models/character_map.py:27-44` (the `Character` class)
- Modify: `frontend/src/types/characterMap.ts:28-39`
- Test: `backend/tests/unit/test_character_map_schema.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/unit/test_character_map_schema.py`:

```python
def test_is_pov_defaults_false():
    from app.models.character_map import Character
    c = Character.model_validate({
        "id": "ned", "name": "Eddard Stark", "role": "Lord",
        "description": "Warden of the North.", "faction_id": "stark",
        "importance": "protagonist", "is_deceased_in_work": False,
        "spoiler_level": 0,
    })
    assert c.is_pov is False


def test_is_pov_accepts_true():
    from app.models.character_map import Character
    c = Character.model_validate({
        "id": "ned", "name": "Eddard Stark", "role": "Lord",
        "description": "Warden of the North.", "faction_id": "stark",
        "importance": "protagonist", "is_deceased_in_work": False,
        "spoiler_level": 0, "is_pov": True,
    })
    assert c.is_pov is True
```

- [ ] **Step 2: Run to verify it fails**

```bash
docker cp backend/tests charmap_api:/app/tests \
  && docker exec charmap_api python -m pytest tests/unit/test_character_map_schema.py -q
```
Expected: FAIL — `is_pov` rejected as extra field / attribute missing.

- [ ] **Step 3: Add the field**

In `backend/app/models/character_map.py`, inside `class Character`, after the `home_region` field (line ~44) add:

```python
    # True only for narrative viewpoint (POV) characters — chapters/sections
    # told from their perspective (e.g. ASOIAF POV chapters). Populated by
    # Stage 2 from the analysis's Viewpoint section; default False.
    is_pov: bool = False
```

- [ ] **Step 4: Mirror in the TS type**

In `frontend/src/types/characterMap.ts`, inside `interface Character`, after `home_region?: string | null` (line 38) add:

```ts
  is_pov?: boolean
```

- [ ] **Step 5: Run to verify pass**

```bash
docker cp backend/app charmap_api:/app/app && docker cp backend/tests charmap_api:/app/tests \
  && docker exec charmap_api python -m pytest tests/unit/test_character_map_schema.py -q
```
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/character_map.py frontend/src/types/characterMap.ts backend/tests/unit/test_character_map_schema.py
git commit -m "feat(schema): add is_pov to Character (backend + TS type)"
```

---

## Task 2: Cap-aware Stage-1 retrieval + scaled search budget

**Files:**
- Modify: `backend/app/worker/pipeline.py` (add `_searches_for_cap`; edit `_run_grounded` at lines 385-388)
- Modify: `backend/app/llm/anthropic_client.py:62-95` (`generate_with_web_search`)
- Test: `backend/tests/unit/test_grounded_retrieval.py` (new)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/test_grounded_retrieval.py`:

```python
from app.worker.pipeline import _searches_for_cap, _load_analysis_prompt


def test_searches_for_cap_scales_with_cap():
    assert _searches_for_cap(10) == 4
    assert _searches_for_cap(20) == 4
    assert _searches_for_cap(50) == 4
    assert _searches_for_cap(100) == 8
    assert _searches_for_cap(150) == 12


def test_analysis_prompt_is_cap_aware():
    # Must contain the {CHAR_CAP} placeholder so _render_system_prompt can
    # inject the target roster size into Stage 1.
    assert "{CHAR_CAP}" in _load_analysis_prompt()
```

- [ ] **Step 2: Run to verify it fails**

```bash
docker cp backend/tests charmap_api:/app/tests \
  && docker exec charmap_api python -m pytest tests/unit/test_grounded_retrieval.py -q
```
Expected: FAIL — `_searches_for_cap` not defined; `{CHAR_CAP}` not in analysis prompt yet.

- [ ] **Step 3: Add `_searches_for_cap` and make Stage 1 cap-aware**

In `backend/app/worker/pipeline.py`, add this helper just above `_run_grounded` (line ~372):

```python
def _searches_for_cap(cap: int) -> int:
    """Web-search budget scales with the requested cap. Small/default maps need
    only a few searches; large-ensemble works (cap 100/150) need enough passes
    to enumerate the deep cast. Stage 1 latency tracks output tokens more than
    search count, so this stays modest."""
    if cap <= 50:
        return 4
    if cap <= 100:
        return 8
    return 12
```

Then in `_run_grounded`, replace lines 385-388:

```python
    analysis_system = _load_analysis_prompt()
    analysis_user = _render_analysis_user_message(job)
    await _set_progress_stage(session, job, "searching")
    stage1 = await client.generate_with_web_search(analysis_system, analysis_user)
```

with:

```python
    analysis_system = _render_system_prompt(_load_analysis_prompt(), job.character_cap)
    analysis_user = _render_analysis_user_message(job)
    await _set_progress_stage(session, job, "searching")
    stage1 = await client.generate_with_web_search(
        analysis_system,
        analysis_user,
        max_searches=_searches_for_cap(job.character_cap),
    )
```

- [ ] **Step 4: Add `allowed_domains` param to the client**

In `backend/app/llm/anthropic_client.py`, change the `generate_with_web_search` signature (line 62) to add the param:

```python
    async def generate_with_web_search(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 8192,
        max_searches: int = 3,
        allowed_domains: list[str] | None = None,
    ) -> LLMResult:
```

Then replace the inline `tools=[...]` block (lines ~89-95) with a tool dict that conditionally carries the allowlist:

```python
        web_search_tool: dict = {
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": max_searches,
        }
        if allowed_domains:
            web_search_tool["allowed_domains"] = allowed_domains
        message = await self._client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=[
                {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user_message}],
            tools=[web_search_tool],
        )
```

(Leave the `temperature`-removed comment above `messages.create` in place. `allowed_domains` is unused by default — it exists for future per-work scoping.)

- [ ] **Step 5: Run to verify the `_searches_for_cap` test passes**

```bash
docker cp backend/app charmap_api:/app/app && docker cp backend/tests charmap_api:/app/tests \
  && docker exec charmap_api python -m pytest tests/unit/test_grounded_retrieval.py::test_searches_for_cap_scales_with_cap tests/unit/test_anthropic_client.py -q
```
Expected: `_searches_for_cap` test PASS; existing `test_anthropic_client.py` still PASS. (`test_analysis_prompt_is_cap_aware` still fails — fixed in Task 3.)

- [ ] **Step 6: Commit**

```bash
git add backend/app/worker/pipeline.py backend/app/llm/anthropic_client.py backend/tests/unit/test_grounded_retrieval.py
git commit -m "feat(grounding): cap-aware Stage-1 + scaled web_search budget + allowed_domains hook"
```

---

## Task 3: Stage-1 analysis prompt — target size, breadth, source, POV

**Files:**
- Modify: `backend/prompts/character_map_analysis.md`
- Test: `backend/tests/unit/test_grounded_retrieval.py` (extend)

- [ ] **Step 1: Write the failing contract tests**

Append to `backend/tests/unit/test_grounded_retrieval.py`:

```python
def test_analysis_prompt_names_canonical_wiki_source():
    assert "awoiaf" in _load_analysis_prompt().lower()


def test_analysis_prompt_has_viewpoint_section():
    assert "Viewpoint" in _load_analysis_prompt()
```

- [ ] **Step 2: Run to verify they fail**

```bash
docker cp backend/tests charmap_api:/app/tests \
  && docker exec charmap_api python -m pytest tests/unit/test_grounded_retrieval.py -q
```
Expected: FAIL on the three prompt-content tests (`{CHAR_CAP}`, `awoiaf`, `Viewpoint`).

- [ ] **Step 3: Edit the analysis prompt**

In `backend/prompts/character_map_analysis.md`:

a) In rule 1 (the web-search rule), append this sentence:

```
For works with a dedicated comprehensive fan-wiki, treat it as a primary source for the *complete* character roster — e.g. for A Song of Ice and Fire / Game of Thrones, https://awoiaf.westeros.org (and its Portal:Characters index) is authoritative.
```

b) Add a new rule 6 (after the current rule 5 "Faction-padding is forbidden"):

```
6. **Roster completeness — target up to {CHAR_CAP} characters.** Enumerate as close to {CHAR_CAP} *verified* characters as the work genuinely supports. "Structural importance" is NOT just the leads: for large-ensemble works (epic fantasy, sprawling sagas, big-cast films) include recurring supporting cast — household members, advisers, bodyguards, wards, named retainers, faction officers, mentors. Do not stop at the obvious 20–30 when the source names more. This never overrides rule 1: only enumerate characters you can verify via search — never invent to reach the number. The cap is a **ceiling, not a quota**: if the work only has, say, 12 verifiable named characters, return 12 — a thin accurate roster beats a padded one. Scale to the work, not to the number.
```

c) In the "Cast (verified via web search)" section, change the line "Include every named character of structural importance." to:

```
Include every named character the sources support, up to {CHAR_CAP}, prioritising by narrative importance when you must choose. If a faction's members are unnamed in source, list the faction as a single collective entry rather than inventing names.
```

d) Add a new output section immediately after the Cast section (before "True Final Resolution / Ending"):

```
**Viewpoint (POV) characters**
If the work uses named POV / viewpoint chapters or sections (e.g. A Song of Ice and Fire, where each chapter is told through one character's eyes), list those POV characters by name here, one per line, verified against the source. Do NOT infer POV from prominence — list only characters whose perspective actually narrates a chapter/section. Most works have NO formal POV structure (third-person omniscient, a single first-person narrator) — for those, "n/a" is the common and correct answer. The POV count is whatever the work genuinely has: 0, 1, 8, or more — never a fixed number. If the work has no such structure, write "n/a".
```

- [ ] **Step 4: Run to verify pass**

```bash
docker cp backend/app charmap_api:/app/app \
  && docker exec charmap_api python -m pytest tests/unit/test_grounded_retrieval.py -q
```
Expected: all PASS (`{CHAR_CAP}`, `awoiaf`, `Viewpoint` now present).

- [ ] **Step 5: Commit**

```bash
git add backend/prompts/character_map_analysis.md backend/tests/unit/test_grounded_retrieval.py
git commit -m "feat(prompt): Stage-1 roster completeness, canonical wiki source, POV section"
```

---

## Task 4: Stage-2 structuring prompt — populate `is_pov`

**Files:**
- Modify: `backend/prompts/character_map_structuring.md`
- Test: `backend/tests/unit/test_grounded_retrieval.py` (extend)

- [ ] **Step 1: Write the failing contract test**

Append to `backend/tests/unit/test_grounded_retrieval.py`:

```python
def test_structuring_prompt_documents_is_pov():
    from app.worker.pipeline import _load_structuring_prompt
    text = _load_structuring_prompt()
    assert "is_pov" in text
    assert "Viewpoint" in text
```

- [ ] **Step 2: Run to verify it fails**

```bash
docker cp backend/tests charmap_api:/app/tests \
  && docker exec charmap_api python -m pytest tests/unit/test_grounded_retrieval.py::test_structuring_prompt_documents_is_pov -q
```
Expected: FAIL — `is_pov` not in structuring prompt.

- [ ] **Step 3: Edit the structuring prompt**

In `backend/prompts/character_map_structuring.md`:

a) Add a new rule 8b (after rule 8a "Home region"):

```
8b. **POV characters.** If the `<analysis>` contains a *Viewpoint (POV) characters* section listing names, set `is_pov: true` on exactly those characters (match by name) and `is_pov: false` on all others. If that section says "n/a" or is absent, set `is_pov: false` on every character. Never infer POV from `importance` — POV comes only from the analysis's Viewpoint list.
```

b) In the `interface Character` block of the OUTPUT SCHEMA, after the `home_region?` line (line ~84) add:

```
  is_pov: boolean;     // true ONLY for narrative viewpoint characters per the analysis's Viewpoint (POV) section; false otherwise.
```

- [ ] **Step 4: Run to verify pass**

```bash
docker cp backend/app charmap_api:/app/app \
  && docker exec charmap_api python -m pytest tests/unit/test_grounded_retrieval.py -q
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/prompts/character_map_structuring.md backend/tests/unit/test_grounded_retrieval.py
git commit -m "feat(prompt): Stage-2 populates is_pov from the analysis Viewpoint section"
```

---

## Task 5: Fix card overlap — fixed-height cards

**Files:**
- Modify: `frontend/src/layout/layout.ts:5` (`NODE_HEIGHT`) and the character-node push (lines 154-170)
- Modify: `frontend/src/components/CharacterCardNode.tsx:30-71`
- Test: `frontend/src/layout/layout.test.ts`

- [ ] **Step 1: Write the failing test**

In `frontend/src/layout/layout.test.ts`, add inside the `describe('buildLayout', ...)` block:

```ts
  it('gives each character node a fixed height equal to NODE_HEIGHT', () => {
    const f = faction('f')
    const c = character('c1', 'f')
    const { nodes } = buildLayout(map({ factions: [f], characters: [c] }))
    const charNode = nodes.find(n => n.id === 'c1')!
    const style = charNode.style as { width: number; height: number }
    expect(style.width).toBe(NODE_WIDTH)
    expect(style.height).toBe(NODE_HEIGHT)
  })
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd frontend && npx vitest run src/layout/layout.test.ts
```
Expected: FAIL — character node style has no `height` (currently only `width`).

- [ ] **Step 3: Set a fixed node height in the layout**

In `frontend/src/layout/layout.ts`, bump the constant (line 5):

```ts
export const NODE_HEIGHT = 116
```

Then in the character node push (line ~166), change the style to include height:

```ts
        style: { width: NODE_WIDTH, height: NODE_HEIGHT },
```

- [ ] **Step 4: Make the card fill that box and clamp text**

In `frontend/src/components/CharacterCardNode.tsx`, change the card root `<div>` (line 30-33) to fill the node and hide overflow:

```tsx
      <div
        style={{ borderColor: colour }}
        className="h-full overflow-hidden flex items-center gap-3.5 bg-[#1e1e1e] rounded-[10px] border-[1.5px] px-4 py-3 cursor-grab active:cursor-grabbing hover:shadow-[0_0_0_2px_rgba(255,255,255,0.1)] transition-shadow select-none"
      >
```

Then change the name + role block (lines 67-70) to clamp long text (Tailwind 3.4 has `line-clamp`):

```tsx
        {/* Name + role */}
        <div className="min-w-0">
          <div className="text-[22px] font-bold text-white leading-snug line-clamp-2">{c.name}</div>
          <div className="text-[18px] text-[#9ca3af] mt-0.5 line-clamp-1">{c.role}</div>
        </div>
```

- [ ] **Step 5: Run to verify the layout test passes**

```bash
cd frontend && npx vitest run src/layout/layout.test.ts
```
Expected: PASS (existing tests still green — `factionSize` already uses `NODE_HEIGHT`).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/layout/layout.ts frontend/src/components/CharacterCardNode.tsx frontend/src/layout/layout.test.ts
git commit -m "fix(layout): fixed-height cards with clamped name/role — kills row overlap"
```

---

## Task 6: POV ★ on cards + legend

**Files:**
- Modify: `frontend/src/components/CharacterCardNode.tsx` (name block)
- Modify: `frontend/src/components/CharacterMapCanvas.tsx` (`LegendPanel`)

- [ ] **Step 1: Render a gold ★ on POV cards**

In `frontend/src/components/CharacterCardNode.tsx`, change the name line to prepend a star when `c.is_pov`:

```tsx
          <div className="text-[22px] font-bold text-white leading-snug line-clamp-2">
            {c.is_pov && (
              <span title="POV character" style={{ color: '#D4AF37' }} className="mr-1">★</span>
            )}
            {c.name}
          </div>
```

- [ ] **Step 2: Add a POV row to the legend**

In `frontend/src/components/CharacterMapCanvas.tsx`, inside `LegendPanel`, just before the closing `</div>` of the panel (after the `EDGE_LEGEND.map(...)` block, line ~51), add:

```tsx
      <div className="mt-2 pt-2 border-t border-[#2a2a2a] flex items-center gap-2">
        <span style={{ color: '#D4AF37' }} className="text-[13px]">★</span>
        <span className="text-[13px] text-[#ccc]">POV character</span>
      </div>
```

- [ ] **Step 3: Verify visually (build + screenshot)**

Built and verified in Task 8 against the real GoT regen (★ on Ned/Catelyn/Sansa/Arya/Bran/Jon/Tyrion/Daenerys, none elsewhere).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/CharacterCardNode.tsx frontend/src/components/CharacterMapCanvas.tsx
git commit -m "feat(ui): star POV characters on the card + legend entry"
```

---

## Task 7: Fullscreen map toggle

**Files:**
- Modify: `frontend/src/components/CharacterMapCanvas.tsx` (`InnerCanvas`)

- [ ] **Step 1: Add fullscreen state + Esc handler**

In `frontend/src/components/CharacterMapCanvas.tsx`, change the React import (line 1) to include `useEffect`:

```tsx
import { useState, useMemo, useCallback, useEffect } from 'react'
```

Inside `InnerCanvas`, after the `showLegend` state (line ~80) add:

```tsx
  const [fullscreen, setFullscreen] = useState(false)
  useEffect(() => {
    if (!fullscreen) return
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setFullscreen(false) }
    window.addEventListener('keydown', onKey)
    document.body.style.overflow = 'hidden'
    return () => {
      window.removeEventListener('keydown', onKey)
      document.body.style.overflow = ''
    }
  }, [fullscreen])
```

- [ ] **Step 2: Make the container an overlay in fullscreen, and hide chrome**

Change the outer wrapper `<div>` (line 148) from:

```tsx
    <div className="flex flex-col h-full bg-[#111]">
```

to:

```tsx
    <div className={fullscreen ? 'fixed inset-0 z-50 flex flex-col bg-[#111]' : 'flex flex-col h-full bg-[#111]'}>
```

Wrap the **Title strip** block (lines 150-183), the **Optional banners** block (lines 215-227), and the **Setting** block (lines 229-233) each so they only render when not fullscreen — change each opening guard. For the title strip, wrap it:

```tsx
      {!fullscreen && (
      <div className="bg-[#161616] border-b border-[#222] px-6 py-3 flex-shrink-0">
        {/* ...unchanged title strip contents... */}
      </div>
      )}
```

For the coverage banner, change `{charMap.coverage_note && !coverageDismissed && (` to `{!fullscreen && charMap.coverage_note && !coverageDismissed && (`. For the setting block, change `{charMap.setting_preamble && (` to `{!fullscreen && charMap.setting_preamble && (`.

- [ ] **Step 3: Add the ⛶ button to the toolbar and conditionally hide the toolbar**

Wrap the **Top toolbar** block (lines 186-212) in `{!fullscreen && (...)}`, and add a Fullscreen button just after the "Reset layout" button (before the toolbar's closing `</div>` at line 212):

```tsx
        <button
          onClick={() => setFullscreen(true)}
          title="Fullscreen map (Esc to exit)"
          className="px-4 py-2 text-sm font-semibold text-[#e5e7eb] border-[1.5px] border-[#444] rounded-lg bg-transparent hover:border-[#666] transition-colors"
        >
          ⛶ Fullscreen
        </button>
```

- [ ] **Step 4: Add a floating exit/controls cluster shown only in fullscreen**

Inside the React Flow container `<div className="flex-1 relative">` (line 236), just after the closing `</ReactFlow>` tag (line 258) and before the Legend toggle block, add:

```tsx
        {fullscreen && (
          <div className="absolute top-3.5 right-3.5 z-10 flex items-center gap-2">
            <button
              onClick={() => setShowEdges(v => !v)}
              title="Toggle relationship lines"
              className={`px-3 py-1.5 text-[12px] font-semibold rounded-lg border-[1.5px] transition-colors ${
                showEdges
                  ? 'bg-[#D4AF37] text-[#0D0B09] border-[#D4AF37]'
                  : 'bg-[#1a1a1a] text-[#aaa] border-[#2a2a2a] hover:border-[#555]'
              }`}
            >
              Connections
            </button>
            <button
              onClick={resetLayout}
              className="px-3 py-1.5 text-[12px] font-semibold text-[#e5e7eb] border-[1.5px] border-[#444] rounded-lg bg-[#1a1a1a] hover:border-[#666] transition-colors"
            >
              Reset layout
            </button>
            <button
              onClick={() => setFullscreen(false)}
              title="Exit fullscreen (Esc)"
              className="px-3 py-1.5 text-[12px] font-semibold text-[#e5e7eb] border-[1.5px] border-[#444] rounded-lg bg-[#1a1a1a] hover:border-[#666] transition-colors"
            >
              ✕ Exit
            </button>
          </div>
        )}
```

(The React Flow `<MiniMap>`, `<Controls>` zoom cluster, `<Background>`, and the Legend toggle stay inside the container, so they remain available in fullscreen.)

- [ ] **Step 5: Verify the frontend still builds + typechecks**

```bash
cd frontend && npx vitest run && npm run build
```
Expected: tests PASS, build succeeds (no TS errors).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/CharacterMapCanvas.tsx
git commit -m "feat(ui): fullscreen map toggle — hide chrome, floating exit/controls, Esc to exit"
```

---

## Task 8: Build, full verification, regenerate GoT, deploy

**Files:** none (verification + deploy)

- [ ] **Step 1: Full backend unit suite (in the worker container — it has pandoc+pdflatex for the PDF tests)**

```bash
docker cp backend/app charmap_worker:/app/app && docker cp backend/tests charmap_worker:/app/tests \
  && docker exec charmap_worker python -m pytest tests/unit -q
```
Expected: all pass (210 prior + new `is_pov`/`grounded_retrieval` tests).

- [ ] **Step 2: Full frontend suite + build**

```bash
cd frontend && npx vitest run && rm -rf dist node_modules/.vite && npm run build
```
Expected: all Vitest pass, clean build (clears stale Vite cache per CLAUDE.md).

- [ ] **Step 3: Rebuild + recreate all containers locally**

```bash
docker compose build api worker frontend && docker compose up -d api worker frontend
```

- [ ] **Step 4: Regenerate the GoT map at cap=50 (grounded, Opus 4.8) and grade against the roster**

Use the app at `http://localhost:8201` (A Game of Thrones, model Opus 4.8, cap 50). When done, count + inspect:

```bash
docker exec charmap_postgres psql -U charactermap -d charactermap -tAc \
 "SELECT jsonb_array_length(character_map->'characters'), \
  (SELECT count(*) FROM jsonb_array_elements(character_map->'characters') e WHERE (e->>'is_pov')::bool) \
  FROM jobs WHERE resolved_title ILIKE '%game of thrones%' ORDER BY created_at DESC LIMIT 1;"
```
Expected: character count **≥ 50**, POV count **= 8** (Ned, Catelyn, Sansa, Arya, Bran, Jon, Tyrion, Daenerys). Spot-check the roster against Appendix A of the spec; ★ render verified visually on the map; fullscreen toggle + Esc verified in the browser; no overlapping cards.

- [ ] **Step 5: Golden-set regression (Stage-1 prompt changed — mandatory)**

```bash
docker cp scripts charmap_api:/app/scripts \
  && docker exec -e PYTHONPATH=/app charmap_api python scripts/run_golden_set.py --model claude-sonnet-4-6
```
Expected: 100% `spoiler_level` coverage, zero flagged fabrications, no character-count regression on the other 9 works.

- [ ] **Step 5b: Contrast-work check — no padding, no spurious POVs**

Regenerate a small-cast, third-person (non-POV) golden work — **Congo** (Crichton) at cap=50 — and confirm the changes degrade gracefully for works unlike GoT:

```bash
docker exec charmap_postgres psql -U charactermap -d charactermap -tAc \
 "SELECT jsonb_array_length(character_map->'characters'), \
  (SELECT count(*) FROM jsonb_array_elements(character_map->'characters') e WHERE (e->>'is_pov')::bool) \
  FROM jobs WHERE resolved_title ILIKE '%congo%' ORDER BY created_at DESC LIMIT 1;"
```
Expected: character count reflects Congo's real cast (well under 50 — **not** padded toward the cap), and **POV count = 0** (Congo has no viewpoint-chapter structure). This is the regression guard for the dynamic-scaling principle: the cap is a ceiling, and POV stars only appear when a work actually has them.

- [ ] **Step 6: Open PR, merge, deploy to lfc**

```bash
git push -u origin feat/got-scale-maps
gh pr create --base main --head feat/got-scale-maps --title "feat: GoT-scale maps — completeness, POV stars, layout fix, fullscreen" --body "Implements docs/superpowers/specs/2026-05-29-got-scale-maps-design.md"
# after review/merge:
./deploy.sh
```
Expected: `deploy.sh` rebuilds + `alembic upgrade head` (no new migration — `is_pov` is JSONB). Verify `https://charactermap.torgersen.ai/` serves and a fresh GoT map shows ≥50 chars with starred POVs.

- [ ] **Step 7: Planka** — move/închide any matching card; if none, file a `feature` card (`svc:llm` · `svc:frontend` · `phase:4`) marked Completed, summarizing the four changes.

---

## Self-review notes

- **Spec coverage:** ① retrieval → Tasks 2+3+8(step4,5); ② POV → Tasks 1,3,4,6; ③ overlap → Task 5; ④ fullscreen → Task 7; validation → Task 8. All covered.
- **Type consistency:** `is_pov` is `bool`/`boolean` everywhere; `_searches_for_cap` / `_render_system_prompt` / `_load_analysis_prompt` / `_load_structuring_prompt` names match the existing pipeline. `NODE_HEIGHT` exported from `layout.ts` and consumed by `factionSize` + the card node box.
- **No migration:** `is_pov` lives in the `character_map` JSONB blob (same as `home_region`).
- **Out of scope (follow-up):** POV is wired only in the grounded (Anthropic) path; the ungrounded single-call prompt (`character_map.md`, OpenAI/Gemini) leaves `is_pov=false`. No hard `web_search` domain allowlist on by default.
