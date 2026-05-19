# Next Session — Start Prompt

> Hand-off note from Session 7 wrapup. Paste the block below at the start of the next session.

---

## Where the project is

charactermap.torgersen.ai is live and end-to-end working — search → resolve → generate → render → download → email. All three providers verified (Sonnet 4.6, Opus 4.7, GPT-5.5, Gemini 2.5 Pro). 173 backend unit tests + 19 frontend vitest passing. iPad tested end-to-end (the real test environment — three production bugs squashed this session were invisible on desktop and only manifested on iOS WebKit).

Phase 5 + 6 backend deliverables (#35–39, #42) are shipped. Phase 5/6 frontend deliverables (#35 widget, #38 hint, #40 errors, #41 privacy/terms/cookies, #42 client analytics) are shipped. Two SPEC #-items remain to fully close Phase 6: **#43 golden-set validation** and **#44 fabrication audit** — both manual, user-driven.

## Top of the launch-readiness list

1. **Manual validation (the actual remaining blocker for v1).**
   - **#43:** Run `scripts/run_golden_set.py` for all 10 works against Sonnet 4.6. Review each output for accuracy + spoiler-level honesty + fabrications. Iterate prompt until clean. Save passing outputs to `tuning/exemplars/`.
   - **#44:** Fabrication audit on *A Fire Upon the Deep* + one obscure work you know intimately. Zero invented characters/relationships to pass.
   - **#45:** Close after #43 + #44 are clean.

2. **Cloudflare orange-cloud decision for Turnstile.** Currently OFF in production (both keys blanked in lfc `.env`). Re-enabling requires putting the domain behind CF proxy (orange cloud) so `/cdn-cgi/*` traffic terminates at CF edge. Infrastructure wiring already done — just flip the keys back and redeploy after the proxy decision. (Cost guard + rate limits cover most of the abuse surface even without it.)

3. **Pre-launch hygiene:** rotate `ARTIFACT_SIGNING_KEY` (still `'change-me-in-production'`), verify GPT-5.5 pricing against current OpenAI rates, audit other nginx prefix-locations for the 301-on-POST class of bug.

## What to know before touching anything

- **iPad first.** Test new features on iPad before declaring done. Desktop browsers silently follow 301-on-POST; iOS WebKit doesn't. Open Library 422s on short queries. CF Turnstile requires orange-cloud. None of these were caught on desktop.
- **Turnstile is wired but disabled.** Don't reintroduce it without addressing the orange-cloud decision first. Keys in `.env.bak.1779150643` on lfc.
- **Spoiler banner is gone in v1.** Backend hard-gate on `acknowledged_spoilers: true` is intact (still rejects false). Frontend hardcodes true. Reintroduce the banner when shipping v1.5 spoiler-safe mode.
- **VPS access:** `ssh espen@torgersen.ai`; `usv_nginx` is a Docker container; edit `/home/espen/ClaudeCode/UAV/usv-fleet-platform/usv-fleet/config/nginx.conf` **in-place** (single-file bind mounts pin to inode). Reload with `docker exec usv_nginx nginx -s reload` after `nginx -t`.
- **lfc `.env` changes:** `docker compose up -d --force-recreate <service>` — `restart` alone keeps stale env.
- **Frontend rebuilds:** Vite content-hashing can collide. If a rebuild produces the same bundle hash, the bundle bytes really are identical; check that, not the filename.

## How to start the next session

Read this file, scan the top 5 ToDo cards on Planka, and pick the most-impactful unblocked work. The launch-critical path is #43/#44 (manual) followed by the Turnstile orange-cloud decision. Everything else is post-launch polish.
