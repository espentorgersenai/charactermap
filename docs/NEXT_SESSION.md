# Next Session — Start Prompt

> Hand-off note from Session 8 wrapup. Paste the block below at the start of the next session.

---

## Where the project is

charactermap.torgersen.ai is live and end-to-end working — search → resolve → generate → render → download → email. iPad tested end-to-end, including PDF export with side-by-side photo+text layout. 186 backend unit tests + 19 frontend vitest passing.

Phase 5 + 6 backend deliverables (#35–39, #42) are shipped. Phase 5/6 frontend deliverables (#35 widget, #38 hint, #40 errors, #41 privacy/terms/cookies, #42 client analytics) are shipped. TV cast matching now uses `/aggregate_credits` so multi-season shows match across all seasons (Night Manager went 2/16 → 16/16 headshots).

Two SPEC #-items remain to fully close Phase 6: **#43 golden-set validation** and **#44 fabrication audit** — both manual, user-driven.

## Top of the launch-readiness list

1. **Manual validation (the actual remaining v1 blocker).**
   - **#43:** Run `scripts/run_golden_set.py` for all 10 works against Sonnet 4.6. Review each output for accuracy + spoiler-level honesty + fabrications. Iterate prompt until clean. Save passing outputs to `tuning/exemplars/`.
   - **#44:** Fabrication audit on *A Fire Upon the Deep* + one obscure work you know intimately. Zero invented characters/relationships to pass.
   - **#45:** Close after #43 + #44 are clean.

2. **Pre-launch hygiene** (small, high-leverage):
   - **Rotate `ARTIFACT_SIGNING_KEY`** — still `'change-me-in-production'` on lfc. `openssl rand -hex 32` → edit `.env` → `docker compose up -d --force-recreate api worker`.
   - **#46 .env audit** on lfc — all keys present, no duplicates, `ENVIRONMENT=production`, `BASE_URL=https://charactermap.torgersen.ai`.
   - **Tighten rate limits back** from dev-loosened 8/30/60 to SPEC 2/5/15 in `app/security/rate_limit.py`.
   - **Verify GPT-5.5 pricing** in `openai_client.py::_COST_PER_MTOK`.
   - **Re-enable Turnstile** (after Cloudflare orange-cloud decision — see below).
   - **#32 TMDb attribution component** — legal pre-launch.

3. **Latent issues worth fixing soon:**
   - **Cert renewal deploy hook** — Let's Encrypt cert auto-renews in ~60 days; without a hook the renewed cert won't propagate to the bind-mount.
   - **nginx-301-on-POST audit** — fixed the SSE block in Session 7; other trailing-slash locations could have the same iPad-breaking failure mode.

## What to know before touching anything

- **iPad first.** Test new features on iPad before declaring done. Three production bugs in Session 7 + the headshot coverage issue in Session 8 were invisible on desktop and only manifested on iOS WebKit (or with a real adapted-from-TV work).
- **Turnstile is wired but disabled.** Cloudflare grey-cloud (DNS-only) makes Turnstile spin forever at "verifying" because `/cdn-cgi/*` traffic can't terminate at CF edge. Re-enable requires orange-clouding the domain or accepting Turnstile-off. Both keys stashed in `.env.bak.1779150643` on lfc.
- **Spoiler banner is gone in v1.** Backend hard-gate on `acknowledged_spoilers: true` is intact (still rejects false). Frontend hardcodes true. Reintroduce the banner when shipping v1.5 spoiler-safe mode.
- **Rate limits are dev-loosened.** 8/min · 30/hr · 60/day in production right now. Daily cost guard ($5/day) is the actual safety net. Tighten before public traffic.
- **PDF renderer assumes pdflatex + the regex pre-processor.** Adding new unicode chars to `markdown.py` may require adding them to `_UNICODE_FALLBACKS` in `pdf.py`. Adding new character-block markdown patterns may require updating `_CHAR_BLOCK_RE`.
- **TV multi-season shows mix timelines in one map.** `/aggregate_credits` matches across seasons but the LLM still treats the show as a single work — see TV season-selector card for the proper fix.
- **VPS access:** `ssh espen@torgersen.ai`; `usv_nginx` is a Docker container; edit `/home/espen/ClaudeCode/UAV/usv-fleet-platform/usv-fleet/config/nginx.conf` **in-place** (single-file bind mounts pin to inode). Reload with `docker exec usv_nginx nginx -s reload` after `nginx -t`.
- **lfc `.env` changes:** `docker compose up -d --force-recreate <service>` — `restart` alone keeps stale env.
- **Frontend rebuilds:** Vite content-hashing can collide. If a rebuild produces the same bundle hash, the bundle bytes really are identical; check that, not the filename.

## How to start the next session

Read this file, scan the top ToDo cards on Planka, and pick the most-impactful unblocked work. The launch-critical path is #43/#44 (manual) + the small pre-launch hygiene list above. Everything beyond that is post-launch polish.

The smallest meaningful v1 launch is: **#43 + #44 + ARTIFACT_SIGNING_KEY rotation + tighten rate limits + .env audit + #32 attribution + Turnstile decision.** That's the punch list.
