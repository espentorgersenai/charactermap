# Next Session — Start Prompt

> Hand-off note from Session 6 wrapup. Paste the block below at the start of the next session to give the agent immediate context.

---

Goal: ship SPEC §16 deliverables #35–45 if context window allows. That's all of Phase 5 (#35-38) plus all the Phase 6 polish (#39-45) — making charactermap.torgersen.ai actually launch-ready with three working providers.

Site state at session start: live at charactermap.torgersen.ai/, all three providers verified (Sonnet 4.6, Opus 4.7, GPT-5.5, Gemini 2.5 Pro), 135 backend tests green. Frontend agent has been iterating on UI in parallel; treat `frontend/` as off-limits unless coordinating.

## The 11 deliverables, grouped by ownership

**Backend-only (mine, ~6):**
- **#37** Daily cost guard enforcement — highest-risk gap, financial kill-switch is currently inert
- **#36** Redis sliding-window rate limits (2/min, 5/hr, 15/day)
- **#38** `GET /api/limits` endpoint
- **#35** Turnstile backend token verification (frontend half is the other agent's)
- **#39** Resend email delivery — HTML + PDF attached + PNG preview
- **#42** Analytics events route + persistence

**Frontend-coordinated (only if the other agent is free):**
- **#41** `/privacy` + `/terms` full content + cookie banner
- **#40** Friendly error/refused/failed copy + retry buttons
- **#35** `Turnstile.tsx` widget

**Manual / user-driven (not coding):**
- **#43** Golden-set validation — run `scripts/run_golden_set.py` for all 10 works, review each output for fabrications + correctness
- **#44** Fabrication audit on *A Fire Upon the Deep* + one obscure work
- **#45** Workflow gate — close only after #43 and #44 are clean

## Suggested order if context permits everything

**Block 1 — defensive, no UI dependency (~1 hr):**
`#37` daily cost guard → `#36` rate limits → `#38` /api/limits → `#35` backend. Ship as one logical commit per piece, run unit tests between.

**Block 2 — delivery + observability (~45 min):**
`#42` analytics events → `#39` Resend email (test with real Congo + email).

**Block 3 — manual validation (~30 min interactive):**
`#43` golden-set run + review → `#44` fabrication audit. If either fails: edit prompt, re-run, repeat. Close `#45` when clean.

**Block 4 — coordinate with frontend agent:**
`#41` + `#40` — backend side may be near-zero work; mostly content + component scaffolding. Surface what backend needs.

**Other pre-launch (existing ToDo cards, not in 35-45 list but cheap):**
- Rotate `ARTIFACT_SIGNING_KEY` (1 min) before any block ships
- Verify GPT-5.5 + Gemini 2.5 Pro real pricing (5 min curl)

## Things to know

- **VPS:** `ssh espen@torgersen.ai`; `usv_nginx` is a Docker container; edit `/home/espen/ClaudeCode/UAV/usv-fleet-platform/usv-fleet/config/nginx.conf` **in-place** (single-file bind mounts pin to inode — see [[feedback-docker-bind-mount-inode]]).
- **lfc `.env` changes:** `docker compose up -d --force-recreate` (restart alone keeps stale env).
- **Frontend rebuilds:** ask first.

## If context runs short

The must-haves before any public traffic are `#37`, `#36`, `#41`, `#35`, plus Rotate `ARTIFACT_SIGNING_KEY` and the spoiler-ack revert. Everything else can slide to a session 8.
