# Next Session — Hand-off (Session 9 → 10)

**Last chronicle:** Session 9 — 2026-05-19 (`docs/SESSION_CHRONICLE.md`)

**State of `main`:**
- Two-stage grounded pipeline live in production on lfc.
- Final tuning state: `max_searches=3` (down from 8), Stage 1 trimmed (dropped "Structural Metaphors" + "Systemic Nuance" sections), Stage 2 unchanged. ~$0.16-0.20/job warm cache. Wall time ~200s on Embassytown-class works.
- Step 4 single-stage was reverted after Step 5a regression on Congo + Tokyo Express. `_run_grounded_single_stage` stays in `pipeline.py` as a reference implementation — **do not rewire without rethinking the closed-list mitigation**.
- Live progress UI shows stage-aware labels (`searching → structuring → enriching → rendering`).
- All 186 unit tests pass.

## Top ToDo (Planka, post-Session-9)

### New cards filed this session (all `phase:7`)
1. **Pre-generate maps for top-N popular works** (`feature`, `svc:worker`, `svc:db`) — the architectural cost lever. Curate ~100-1000 popular books/films, run worker pipeline once per (resolved_id, cap=20), $200 one-time investment → most user requests become $0 DB cache hits.
2. **Wire web_search for OpenAI + Gemini** (`feature`, `svc:llm`) — currently only Anthropic models get grounding; GPT/Gemini fall through to legacy.
3. **LLMResult cost tracking** (`tech-debt`, `svc:llm`) — include `cache_creation_input_tokens`, `cache_read_input_tokens`, web_search per-call cost. Current reporting under-counts by ~30%.
4. **Decouple character_cap from full-map cache identity** (`feature`, `svc:worker`, `svc:db`) — generate at cap=50, trim to user's cap post-hoc. Makes cache hit rate ~5x better.
5. **Bump DAILY_COST_LIMIT_USD before public launch** (`infra`, `svc:api`) — current $5 covers ~25 grounded jobs/day, too tight.

### Pre-existing cards still in ToDo (highest activity)
- Phase 7: Production .env audit on lfc (#46)
- Phase 7: GitHub Actions deploy workflow (#50)
- Phase 7: Grafana ops + product dashboards (#51)
- Phase 7: Prometheus Alertmanager (#52)
- Phase 7: Retention cron jobs (#53) — *but per Session 9 policy, retention does NOT apply to the `character_map` JSONB; only to MD/PDF artifacts on disk.*
- Verify GPT-5.5 pricing before public deploy
- Rotate ARTIFACT_SIGNING_KEY before production launch
- Cert renewal deploy hook
- Cache-hit UX hint
- iPad UX polish; Re-enable Turnstile; TV season selector; Bias LLM toward credited cast names; latent nginx-301 audit

### In Progress
- (none)

## Open threads from Session 9 that aren't cards

- **The grounding plan at `docs/superpowers/plans/2026-05-19-grounding-pipeline.md` is intentionally uncommitted.** It's the abandoned bespoke-scrapers design. Either delete or leave for the record — your call.
- **Embassytown's single-stage win was an outlier.** Any future grounding architecture change needs at minimum the Congo + Tokyo Express + Embassytown triple as a regression set. One-work validation is insufficient.
- **Cost picture.** With current pipeline + DB cache for repeats, effective per-job cost depends entirely on cache hit rate. Open question: do you want to pre-populate the cache now (cheap, ~$200 one-time) or wait for real traffic to reveal what users actually request?

## Suggested start for Session 10

You said "i need to think" — so reasonable first move is to **just look at production** before picking the next thread. Useful commands:

```bash
# Production health
ssh lfc 'curl -sf http://127.0.0.1:8202/api/health && docker ps --filter name=charmap'

# Most recent jobs
ssh lfc "docker exec charmap_postgres psql -U charactermap -d charactermap -c \
  \"SELECT id, resolved_title, status, model, character_cap, estimated_cost_usd, created_at FROM jobs ORDER BY created_at DESC LIMIT 10;\""

# Visit a recent map in browser
# https://charactermap.torgersen.ai/job/<id>
```

If the data tells you traffic is mostly popular works → start with the **Pre-generate maps** card. If you want a quick correctness win first → **LLMResult cost tracking** (one file, ~30 lines).
