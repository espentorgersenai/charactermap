# Phase 2 — Generation Pipeline: Design

**Date:** 2026-05-18  
**Status:** Approved  
**Spec reference:** SPEC.md §16 Phase 2 (deliverables 8–16), §5.1–5.5, §7.3–7.4, §8.1, §11.2, §19.2–19.3

---

## Scope

Phase 2 wires the full generation pipeline: POST a job, enqueue it to RQ, run the LLM, validate the output, persist to the DB, stream status back via SSE, and display all five job states in the frontend. It also completes `dev-generate.py` and adds `run_golden_set.py` + `tuning/golden_set.yaml`.

Phase 2 does **not** include: canvas rendering (Phase 3), actor headshots (Phase 4), Turnstile verification (Phase 5), rate limits (Phase 5), email (Phase 6). Turnstile is accepted but not verified in Phase 2.

---

## Build order (vertical slices)

1. **Deploy Phase 1 to lfc** — verify the scaffold runs clean before building on top of it.
2. **Pydantic models + LLM client** — `CharacterMap` schema, `LLMClient` protocol, `AnthropicClient`. Testable via `dev-generate.py`.
3. **Worker pipeline** — `pipeline.py` + `tasks.py` + prompt template. End-to-end: enqueue → LLM → validate → DB.
4. **POST /api/jobs + GET /api/jobs/:id** — API layer. Integration test passable here.
5. **GET /api/jobs/:id/stream SSE** — status streaming layer on top of working pipeline.
6. **JobView UI** — five states wired to SSE hook.
7. **run_golden_set.py + golden_set.yaml** — baseline run.

---

## Files created / modified

### New backend files

| File | Purpose |
|------|---------|
| `backend/app/llm/base.py` | `LLMResult` dataclass + `LLMClient` Protocol |
| `backend/app/llm/anthropic_client.py` | Anthropic SDK async implementation |
| `backend/app/models/character_map.py` | Pydantic `CharacterMap` / `Character` / `Faction` / `Relationship` |
| `backend/app/models/job.py` | `JobCreateRequest` / `JobCreateResponse` Pydantic models |
| `backend/app/worker/pipeline.py` | Orchestration: prompt render → LLM call → refusal check → validate → retry → write DB |
| `backend/app/worker/tasks.py` | RQ task entry point: `generate_character_map_task(job_id)` |
| `backend/app/routes/jobs.py` | `POST /api/jobs`, `GET /api/jobs/:id` (status + character_map when done), `GET /api/jobs/:id/stream` |
| `backend/prompts/character_map.md` | Prompt template with all §5.1 guardrails |

### New scripts + tuning

| File | Purpose |
|------|---------|
| `scripts/run_golden_set.py` | Batch runner: iterates `golden_set.yaml`, saves timestamped outputs, prints summary table |
| `tuning/golden_set.yaml` | 10 works from §19.3 |

### Modified files

| File | Change |
|------|--------|
| `backend/pyproject.toml` | Add `anthropic>=0.50` |
| `backend/app/main.py` | Include jobs router |
| `scripts/dev-generate.py` | Replace Phase 1 stub with real LLM client call |
| `frontend/src/routes/JobView.tsx` | Implement all 5 UI states + SSE subscription |

---

## Data flow

```
POST /api/jobs
  → validate body (acknowledged_spoilers gate)
  → INSERT job (status=queued)
  → rq.enqueue(generate_character_map_task, job_id)
  → return {job_id}

RQ worker: generate_character_map_task(job_id)
  → UPDATE job SET status='generating'
  → render prompt (template + work_metadata + user_query)
  → AnthropicClient.generate_character_map(prompt, max_tokens)
  → refusal check: {"refusal": str}? → status=refused, error_code=<reason>
  → Pydantic parse: CharacterMap.model_validate_json(text)
      → ValidationError? → retry once (prompt + error appended)
          → still invalid? → status=failed, error_code=invalid_json
  → spoiler_level sweep: missing/invalid → default 3, log warning
  → UPDATE job SET status='done', character_map=<jsonb>, token counts, cost

GET /api/jobs/:id/stream (SSE)
  → poll DB every 1s
  → emit "event: status" on each change
  → emit terminal event (done/refused/failed) and close
```

---

## Job status state machine

```
queued → generating → done
                    ↘ refused
                    ↘ failed
```

`resolving` and `rendering` states are Phase 4/3 respectively. Phase 2 goes straight queued → generating.

---

## SSE event format

Matches §7.4 of the spec exactly:

```
event: status
data: {"status": "generating", "progress": 0.4}

event: done
data: {"status": "done"}

event: error
data: {"error": "invalid_json", "message": "LLM output failed validation after retry"}
```

Progress fractions (approximated from status, not streaming tokens):
- `queued` → 0.05
- `generating` → 0.4
- `done/refused/failed` → 1.0

SSE state source: **DB polling at 1-second intervals**. The RQ worker is a separate process; it writes status to the DB. The SSE handler in FastAPI reads from the DB. No Redis pub/sub needed for Phase 2.

Fallback: if `EventSource` fails on the client, `useJob` falls back to polling `GET /api/jobs/:id` every 2 seconds.

---

## Pydantic schema

`CharacterMap` exactly mirrors §5 of the spec. Strict types throughout:

```python
spoiler_level: Literal[0, 1, 2, 3]
importance: Literal['protagonist', 'major', 'supporting', 'minor']
relationship.type: Literal['alliance', 'family', 'romantic', 'antagonism', 'professional', 'mentorship', 'criminal']
```

All required fields are non-optional — validation errors force a retry. Optional fields (`setting_preamble`, `coverage_note`, `actor`) use `Optional[...]`.

---

## Refusal handling

Checked **before** Pydantic validation. A `{"refusal": str}` shape is recognised and mapped:

| `refusal` value | `error_code` on job | User message |
|-----------------|---------------------|--------------|
| `unknown_work` | `unknown_work` | "I couldn't confidently identify this work. Try adding the author/director name, or pick a different model." |
| `low_confidence` | `low_confidence` | "Not enough is known about this work to map it reliably. Try a more widely-known title or pick a different model." |
| `policy` | `policy` | "The model I chose declined to map this work. Try a different model." |

Any other `refusal` value is treated as `unknown_work`.

---

## Retry logic

Lives in `pipeline.py`, not in the LLM client (client stays stateless):

```python
raw = await client.generate_character_map(prompt, max_tokens)
# refusal check ...
try:
    result = CharacterMap.model_validate_json(raw.text)
except ValidationError as e:
    prompt_with_error = prompt + f"\n\nYour previous output was invalid. Error:\n{e}\n\nFix it and output only valid JSON."
    raw2 = await client.generate_character_map(prompt_with_error, max_tokens)
    result = CharacterMap.model_validate_json(raw2.text)  # raises → pipeline catches → failed
```

On second failure: `status=failed`, `error_code=invalid_json`.

---

## spoiler_level fallback

After successful Pydantic parse, a sweep function checks every character and relationship. If `spoiler_level` is somehow missing (shouldn't happen post-validation, but belt-and-suspenders):

```python
if char.spoiler_level is None:
    char.spoiler_level = 3
    log.warning("spoiler_level_missing", character_id=char.id)
```

---

## Prompt template structure

`backend/prompts/character_map.md`:

```
<system_instructions>
  [All 11 behavioral rules from §5.1]
  [JSON schema as TypeScript interface block]
</system_instructions>

<work_metadata>
  title: {title}
  year: {year}
  author_or_director: {author_or_director}
  type: {work_type}
</work_metadata>

<user_query>
  {raw_title_query}
</user_query>

Output a single JSON object matching the CharacterMap schema. No prose, no markdown fences.
```

The full CharacterMap TypeScript interface is embedded in the system instructions so the model has the exact expected shape in context. Template variables are filled by `pipeline.py` before the LLM call.

---

## LLMClient protocol

```python
@dataclass
class LLMResult:
    text: str
    input_tokens: int
    output_tokens: int
    cost_usd: float

class LLMClient(Protocol):
    async def generate_character_map(
        self,
        prompt: str,
        max_tokens: int = 4096,
    ) -> LLMResult: ...
```

`AnthropicClient` implements this using `anthropic.AsyncAnthropic`. Phase 5 adds `OpenAIClient` and `GoogleClient`.

---

## POST /api/jobs — hard gates

Per §7.3 and CLAUDE.md critical rules:

1. `acknowledged_spoilers` must be `true` (not false, not missing) — returns **400** otherwise. No exceptions.
2. Turnstile token is accepted in the request body but **not verified** in Phase 2. Phase 5 adds verification.
3. Request is validated against `JobCreateRequest` Pydantic model before any DB write.

---

## Frontend — 5 UI states (JobView.tsx)

| State | Trigger | UI |
|-------|---------|-----|
| Loading | First render, waiting for first SSE event | Spinner |
| In-progress | SSE `status: generating/queued` | Progress bar (0–100%) + elapsed timer + ETA hint |
| Done | SSE `done` event | Raw `character_map` JSON in `<pre>` block (canvas Phase 3) + "Back to home" |
| Refused | SSE `refused` event | Friendly message from §5.5 + "Try with a different model" button |
| Failed | SSE `error` event | Error code + "Try again" + "Report this" mailto |

`useJob` hook:
- Opens `EventSource` on `/api/jobs/:id/stream`
- On `onerror`: falls back to 2s polling `GET /api/jobs/:id`
- Writes `job_id` + title to `localStorage` on first `done` event (feeds `useRecentMaps`)

Per-model ETA hints (static map in `useJob` or a constants file):

| Model | ETA hint |
|-------|---------|
| claude-sonnet-4-6 | "Typically 30–45s" |
| claude-opus-4-7 | "Typically 60–90s" |
| claude-haiku-4-5-20251001 | "Typically 15–25s" |
| gpt-5.5 | "Typically 30–60s" |
| gemini-2.5-pro | "Typically 30–60s" |

---

## Tests

### Unit (pytest, no external calls)

| Test file | What it covers |
|-----------|---------------|
| `tests/unit/test_character_map_schema.py` | Pydantic accepts valid fixture; rejects missing `spoiler_level`; rejects wrong `importance` value; refusal tokens parse correctly |
| `tests/unit/test_pipeline_retry.py` | Mock client: bad JSON first → good JSON second; confirm retry fires once; confirm double-failure → `failed` status |
| `tests/unit/test_jobs_route.py` | `acknowledged_spoilers: false` → 400; missing field → 400; valid body → 202 + `job_id` |

### Integration (skipped without `ANTHROPIC_API_KEY`)

| Test file | What it covers |
|-----------|---------------|
| `tests/integration/test_congo.py` | POST `/api/jobs` → poll `GET /api/jobs/:id` until `status=done`; assert `character_map.characters` non-empty; assert 100% `spoiler_level` coverage |

### Script smoke

```bash
python scripts/dev-generate.py \
  --title "Congo" --author "Michael Crichton" --year 1980 --work-type book \
  | python -m json.tool   # must not error
```

### Baseline golden-set run

```bash
python scripts/run_golden_set.py --model claude-sonnet-4-6
# outputs saved to tuning/baseline/
# target: 100% spoiler_level coverage on all 10 works
```

---

## Out of scope for Phase 2

- Canvas rendering (Phase 3)
- Actor headshots / TMDb (Phase 4)
- Turnstile verification, rate limits, cost guard (Phase 5)
- Email delivery (Phase 6)
- OpenAI / Google LLM clients (Phase 5) — `AnthropicClient` only for now
- `resolving` and `rendering` job statuses (Phases 4/3)
