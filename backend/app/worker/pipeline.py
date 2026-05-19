import json
import re
import structlog
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4
from pydantic import ValidationError

from app.analytics import record_event
from app.config import settings
from app.cost import record_cost
from app.db.session import async_session_factory
from app.db.tables import Artifact, Job
from app.email.mailer import send_completion_email
from app.llm.anthropic_client import AnthropicClient
from app.llm.gemini_client import GeminiClient
from app.llm.openai_client import OpenAIClient
from app.metadata.enrichment import match_cast_to_characters, set_creator
from app.metadata.tmdb import get_credits
from app.renderers.markdown import render_markdown
from app.renderers.pdf import render_pdf
from app.llm.base import LLMClient, LLMResult
from app.models.character_map import CharacterMap

log = structlog.get_logger()

REFUSAL_MESSAGES = {
    "unknown_work": (
        "I couldn't confidently identify this work. "
        "Try adding the author/director name, or pick a different model."
    ),
    "low_confidence": (
        "Not enough is known about this work to map it reliably. "
        "Try a more widely-known title or pick a different model."
    ),
    "policy": "The model I chose declined to map this work. Try a different model.",
    "grounding_failed": (
        "We couldn't find enough authoritative character data for this work "
        "to build a reliable map. Try a more widely-known title."
    ),
}


class RefusalError(Exception):
    def __init__(self, refusal_code: str) -> None:
        self.refusal_code = refusal_code
        super().__init__(refusal_code)


# Haiku 4.5 (and likely future small-tier models / other providers) ignores the
# prompt's "no markdown fences" instruction and wraps JSON in ```json fences.
# Pydantic's JSON parser is strict — first non-whitespace must be `{` — so we
# strip a single outer fence defensively before validating. Provider-agnostic.
_FENCE_RE = re.compile(r"^```(?:json)?\s*\n?(.*?)\n?```\s*$", re.DOTALL)


def _strip_fences(text: str) -> str:
    stripped = text.strip()
    m = _FENCE_RE.match(stripped)
    return m.group(1) if m else stripped


def _check_refusal(text: str) -> None:
    """Raise RefusalError if the text is a refusal JSON token."""
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return  # not JSON, let Pydantic handle it
    if isinstance(data, dict) and "refusal" in data:
        raise RefusalError(data["refusal"])


def _build_source_url(job: Job) -> str | None:
    """Deep link to the source listing for this work (TMDB or OpenLibrary).
    None if we can't construct one (unknown source or missing id)."""
    meta = job.resolved_meta or {}
    src = meta.get("source")
    if src == "openlibrary" and job.resolved_id:
        return f"https://openlibrary.org/works/{job.resolved_id}"
    if src == "tmdb" and job.resolved_id:
        mt = meta.get("media_type")
        if mt in ("movie", "tv"):
            return f"https://www.themoviedb.org/{mt}/{job.resolved_id}"
    return None


async def _enrich_with_credits(char_map: CharacterMap, job: Job) -> None:
    """Best-effort: populate Character.actor (fuzzy-matched) and char_map.creator.

    - film_tv: pull credits for `job.resolved_id` (the TMDB id of the work itself).
    - book: if `resolved_meta.adaptation_tmdb_id` is present, pull credits from
      the adaptation and fuzzy-match against the book's characters. Creator is
      always the author for books (not the adaptation's director).

    Never raises — enrichment failures are logged and swallowed.
    """
    meta = job.resolved_meta or {}
    author_name = meta.get("author")
    director = None  # Used to populate creator on film/tv only

    tmdb_id: int | None = None
    media_type = meta.get("media_type")

    if job.work_type == "film_tv":
        try:
            tmdb_id = int(job.resolved_id)
        except (TypeError, ValueError):
            log.warning("enrichment_bad_tmdb_id", job_id=str(job.id), resolved_id=job.resolved_id)
    elif job.work_type == "book":
        adapt_id = meta.get("adaptation_tmdb_id")
        if adapt_id is not None:
            try:
                tmdb_id = int(adapt_id)
            except (TypeError, ValueError):
                log.warning("enrichment_bad_adaptation_id", job_id=str(job.id), adapt_id=adapt_id)

    if tmdb_id is not None and media_type in ("movie", "tv"):
        try:
            # aggregate_collection only matters for movies in a TMDB collection
            # (Hobbit trilogy, LOTR, Star Wars). Single-film movies and TV fall
            # back to single-cast inside fetch_collection_cast.
            # season pins TV credits to that season only (overrides
            # aggregate_credits union). None = aggregate as before.
            season = meta.get("season") if media_type == "tv" else None
            cast, director_credit = await get_credits(
                tmdb_id, media_type, aggregate_collection=True, season=season,
            )
            matched = match_cast_to_characters(char_map.characters, cast)
            log.info(
                "enrichment_cast_matched",
                job_id=str(job.id),
                work_type=job.work_type,
                cast_size=len(cast),
                matched=matched,
                total_chars=len(char_map.characters),
                season=season,
            )
            # Only film/tv creator comes from the director; books always use the author.
            if job.work_type == "film_tv":
                director = director_credit
        except Exception as e:
            log.warning("enrichment_credits_failed", job_id=str(job.id), error=str(e))
    elif job.work_type == "film_tv":
        log.info("enrichment_skipped_no_media_type", job_id=str(job.id))

    set_creator(char_map, job.work_type, author_name, director)


def _sweep_spoiler_levels(char_map: CharacterMap) -> None:
    """Default any None spoiler_level to 3 and log a warning (CLAUDE.md rule).

    Called by run_pipeline after call_and_validate returns — NOT inside
    call_and_validate itself, so tests can assert the pre-sweep None value.
    """
    for char in char_map.characters:
        if char.spoiler_level is None:
            log.warning("spoiler_level_missing", entity="character", id=char.id)
            char.spoiler_level = 3
    for rel in char_map.relationships:
        if rel.spoiler_level is None:
            log.warning("spoiler_level_missing", entity="relationship",
                        from_id=rel.from_id, to_id=rel.to_id)
            rel.spoiler_level = 3


async def call_and_validate(
    client: LLMClient,
    system_prompt: str,
    user_message: str,
    max_tokens: int = 16384,
) -> tuple[CharacterMap, LLMResult]:
    """Call the LLM, check for refusal, validate schema. Retry once on invalid JSON.

    Refusals are terminal and never retried. On two consecutive validation
    failures the second ValidationError propagates to the caller (run_pipeline).
    Spoiler-level sweeping is intentionally deferred to run_pipeline so callers
    can observe the raw None values.
    """
    raw = await client.generate_character_map(system_prompt, user_message, max_tokens)
    text = _strip_fences(raw.text)
    _check_refusal(text)
    try:
        result = CharacterMap.model_validate_json(text)
        return result, raw
    except ValidationError as first_error:
        log.warning("llm_output_invalid_retrying", error=str(first_error))
        retry_message = (
            user_message
            + f"\n\nYour previous output was invalid. Validation error:\n{first_error}"
            + "\n\nReturn only the raw JSON object — no ```json fences, no preamble,"
              " no trailing prose. The response must start with `{` and end with `}`."
        )
        raw2 = await client.generate_character_map(system_prompt, retry_message, max_tokens)
        text2 = _strip_fences(raw2.text)
        _check_refusal(text2)
        result2 = CharacterMap.model_validate_json(text2)  # raises if still invalid
        return result2, raw2


_PROMPT_PATH = Path(__file__).parent.parent.parent / "prompts" / "character_map.md"
_ANALYSIS_PROMPT_PATH = Path(__file__).parent.parent.parent / "prompts" / "character_map_analysis.md"
_STRUCTURING_PROMPT_PATH = Path(__file__).parent.parent.parent / "prompts" / "character_map_structuring.md"
_SINGLE_STAGE_PROMPT_PATH = Path(__file__).parent.parent.parent / "prompts" / "character_map_single_stage.md"


def _load_prompt_template() -> str:
    return _PROMPT_PATH.read_text()


def _load_analysis_prompt() -> str:
    return _ANALYSIS_PROMPT_PATH.read_text()


def _load_structuring_prompt() -> str:
    return _STRUCTURING_PROMPT_PATH.read_text()


def _load_single_stage_prompt() -> str:
    return _SINGLE_STAGE_PROMPT_PATH.read_text()


def _render_system_prompt(template: str, character_cap: int) -> str:
    """Substitute the runtime placeholders. We avoid `str.format` because the
    prompt contains literal `{` / `}` (the TypeScript schema block)."""
    return template.replace("{CHAR_CAP}", str(character_cap))


def _season_focus_block(job: Job) -> str:
    """When the job pins TV generation to a specific season, prepend a clear
    scope instruction. Empty string when no season is pinned."""
    meta = job.resolved_meta or {}
    season = meta.get("season")
    if not season:
        return ""
    return (
        f"<season_focus>\n"
        f"Focus ONLY on Season {season} of this series. Characters introduced "
        f"in earlier seasons but not present in Season {season} should be "
        f"omitted. Characters who first appear in Season {season} are the "
        f"primary subjects. Storylines, arcs, and relationships must reflect "
        f"Season {season} specifically — not the show overall.\n"
        f"</season_focus>\n\n"
    )


def _render_user_message(job: Job) -> str:
    meta = job.resolved_meta or {}
    author_or_director = meta.get("author") or meta.get("director") or "Unknown"
    return (
        f"<work_metadata>\n"
        f"title: {job.resolved_title}\n"
        f"year: {job.resolved_year or 'Unknown'}\n"
        f"author_or_director: {author_or_director}\n"
        f"type: {job.work_type}\n"
        f"</work_metadata>\n\n"
        f"{_season_focus_block(job)}"
        f"<user_query>\n"
        f"{job.title_query}\n"
        f"</user_query>\n\n"
        f"Output a single JSON object matching the CharacterMap schema. No prose, no markdown fences."
    )


def _render_analysis_user_message(job: Job) -> str:
    meta = job.resolved_meta or {}
    author_or_director = meta.get("author") or meta.get("director") or "Unknown"
    return (
        f"<work_metadata>\n"
        f"title: {job.resolved_title}\n"
        f"year: {job.resolved_year or 'Unknown'}\n"
        f"author_or_director: {author_or_director}\n"
        f"type: {job.work_type}\n"
        f"</work_metadata>\n\n"
        f"{_season_focus_block(job)}"
        f"Produce the analysis as specified."
    )


def _render_structuring_user_message(job: Job, analysis: str) -> str:
    meta = job.resolved_meta or {}
    author_or_director = meta.get("author") or meta.get("director") or "Unknown"
    return (
        f"<work_metadata>\n"
        f"title: {job.resolved_title}\n"
        f"year: {job.resolved_year or 'Unknown'}\n"
        f"author_or_director: {author_or_director}\n"
        f"type: {job.work_type}\n"
        f"</work_metadata>\n\n"
        f"{_season_focus_block(job)}"
        f"<analysis>\n{analysis}\n</analysis>\n\n"
        f"Output a single JSON object matching the CharacterMap schema. "
        f"No prose, no markdown fences."
    )


async def _set_progress_stage(session, job: Job, stage: str | None) -> None:
    """Write a fine-grained sub-stage code to the job row. The SSE stream picks
    this up on its next 1s poll and surfaces it to the frontend.

    Stage codes are deliberately short and machine-readable:
      searching     — Stage 1 web_search analysis (grounded path, the longest stage)
      structuring   — Stage 2 closed-list JSON structuring (grounded path)
      generating    — single-call LLM (ungrounded fallback path)
      enriching     — post-LLM TMDB cast + creator enrichment
      rendering     — markdown + PDF render
    """
    job.progress_stage = stage
    await session.commit()


async def _run_grounded(
    session, client: AnthropicClient, job: Job
) -> tuple[CharacterMap, LLMResult, LLMResult]:
    """Two-stage grounded path:
       Stage 1: web_search-enabled analysis call → prose Cast + Resolution + nuance.
       Stage 2: closed-list structuring call → CharacterMap JSON.

    Writes `progress_stage` transitions on `session` so the SSE stream surfaces
    "searching" then "structuring" to the frontend. Returns
    (char_map, stage1_result, stage2_result). Stage 2 honors RefusalError via
    the existing call_and_validate path (e.g. `grounding_failed` when the
    analysis has too few characters).
    """
    analysis_system = _load_analysis_prompt()
    analysis_user = _render_analysis_user_message(job)
    await _set_progress_stage(session, job, "searching")
    stage1 = await client.generate_with_web_search(analysis_system, analysis_user)
    log.info(
        "grounded_stage1_done",
        job_id=str(job.id),
        analysis_chars=len(stage1.text),
    )

    # Tried Stage 2 on Haiku 4.5 (Session 9 Step 2) — even with the closed-list
    # rule, Haiku pattern-completed a fabricated character "JoaQuin" from the
    # CalVin/MagDa/EzRa naming convention. Reverted; Stage 2 stays on Sonnet
    # for now. If we revisit, try Opus or a different cheap-fast option.
    structuring_system = _render_system_prompt(
        _load_structuring_prompt(), job.character_cap
    )
    structuring_user = _render_structuring_user_message(job, stage1.text)
    await _set_progress_stage(session, job, "structuring")
    char_map, stage2 = await call_and_validate(
        client, structuring_system, structuring_user
    )
    return char_map, stage1, stage2


async def _run_grounded_single_stage(
    session, client: AnthropicClient, job: Job
) -> tuple[CharacterMap, LLMResult]:
    """Single-stage grounded path: web_search-enabled LLM call emits the
    CharacterMap JSON directly. Skips the prose Stage 1 + structuring Stage 2
    split. Trades two-pass discipline for one call's worth of wall time and
    cost.

    No retry on invalid JSON — web_search is expensive, and a retry would
    redo all searches. Validation errors propagate as job failures.
    """
    system_prompt = _render_system_prompt(
        _load_single_stage_prompt(), job.character_cap
    )
    user_message = _render_analysis_user_message(job)
    await _set_progress_stage(session, job, "searching")

    raw = await client.generate_with_web_search(system_prompt, user_message)
    text = _strip_fences(raw.text)
    _check_refusal(text)

    # Defensively extract the JSON object: even with strict instructions, the
    # model may surround the JSON with commentary. Find the outermost braces.
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError(
            f"single-stage output contained no JSON object: {text[:200]!r}"
        )
    json_text = text[start:end + 1]

    char_map = CharacterMap.model_validate_json(json_text)
    return char_map, raw


def get_llm_client(model: str) -> LLMClient:
    if model.startswith("claude-"):
        return AnthropicClient(model=model, api_key=settings.anthropic_api_key)
    if model.startswith("gpt-"):
        return OpenAIClient(model=model, api_key=settings.openai_api_key)
    if model.startswith("gemini-"):
        return GeminiClient(
            model=model,
            api_key=settings.google_api_key,
            project=settings.google_cloud_project or None,
            location=settings.google_cloud_location,
        )
    raise NotImplementedError(f"Model {model!r} not yet wired")


async def run_pipeline(job_id: str) -> None:
    """Full generation pipeline: LLM call → validate → write DB."""
    async with async_session_factory() as session:
        job = await session.get(Job, UUID(job_id))
        if not job:
            log.error("pipeline_job_not_found", job_id=job_id)
            return

        job.status = "generating"
        await session.commit()
        log.info("pipeline_started", job_id=job_id, model=job.model)
        started_at = datetime.now(tz=timezone.utc)

        client = get_llm_client(job.model)
        use_grounded = settings.enable_grounding and isinstance(client, AnthropicClient)

        try:
            if use_grounded:
                # Step 4 single-stage was reverted: catastrophic regression on
                # Congo and Tokyo Express (real characters dropped, fabricated
                # composite names like "Charles Travis", Yasuda missing as
                # antagonist). The two-stage architecture's prose intermediate
                # is load-bearing for closed-list discipline. See ledger
                # comment in pipeline.
                char_map, stage1, stage2 = await _run_grounded(session, client, job)
                llm_result = LLMResult(
                    text="",
                    input_tokens=stage1.input_tokens + stage2.input_tokens,
                    output_tokens=stage1.output_tokens + stage2.output_tokens,
                    cost_usd=stage1.cost_usd + stage2.cost_usd,
                )
                log.info(
                    "pipeline_grounded_path",
                    job_id=job_id,
                    mode="two_stage",
                    stage1_cost=stage1.cost_usd,
                    stage2_cost=stage2.cost_usd,
                )
            else:
                await _set_progress_stage(session, job, "generating")
                system_prompt = _render_system_prompt(_load_prompt_template(), job.character_cap)
                user_message = _render_user_message(job)
                char_map, llm_result = await call_and_validate(
                    client, system_prompt, user_message
                )
            await _set_progress_stage(session, job, "enriching")
            _sweep_spoiler_levels(char_map)
            await _enrich_with_credits(char_map, job)
            char_map.source_url = _build_source_url(job)
        except RefusalError as e:
            job.status = "refused"
            job.error_code = e.refusal_code
            job.error_message = REFUSAL_MESSAGES.get(
                e.refusal_code, REFUSAL_MESSAGES["unknown_work"]
            )
            log.warning("pipeline_refused", job_id=job_id, code=e.refusal_code)
            await record_event(
                session,
                "job_refused",
                {"model": job.model, "error_code": e.refusal_code},
                job_id=UUID(job_id),
            )
        except ValidationError as e:
            job.status = "failed"
            job.error_code = "invalid_json"
            job.error_message = "LLM output failed schema validation after retry."
            log.error("pipeline_validation_failed", job_id=job_id, error=str(e))
            await record_event(
                session,
                "job_failed",
                {"model": job.model, "error_code": "invalid_json"},
                job_id=UUID(job_id),
            )
        except Exception as e:
            job.status = "failed"
            job.error_code = "llm_error"
            job.error_message = str(e)
            log.error("pipeline_error", job_id=job_id, error=str(e))
            await record_event(
                session,
                "job_failed",
                {"model": job.model, "error_code": "llm_error"},
                job_id=UUID(job_id),
            )
        else:
            # Persist the map + cost + tokens up front (so the row is consistent
            # if rendering throws), but DELAY status='done' until after rendering
            # completes. This way the SSE 'done' event only fires when artifacts
            # are actually on disk — and the frontend gets 'rendering' as the
            # progress_stage during the MD+PDF phase.
            job.character_map = char_map.model_dump()
            job.llm_input_tokens = llm_result.input_tokens
            job.llm_output_tokens = llm_result.output_tokens
            job.estimated_cost_usd = Decimal(str(llm_result.cost_usd))
            await record_cost(session, Decimal(str(llm_result.cost_usd)))

            # Render Markdown + PDF artifacts
            await _set_progress_stage(session, job, "rendering")
            artifact_dir = Path(settings.artifact_storage_path) / job_id
            artifact_dir.mkdir(parents=True, exist_ok=True)
            md_text = None
            try:
                md_text = render_markdown(char_map)
                md_path = artifact_dir / "character_map.md"
                md_path.write_text(md_text, encoding="utf-8")
                session.add(Artifact(
                    id=uuid4(),
                    job_id=UUID(job_id),
                    format="markdown",
                    file_path=str(Path(job_id) / "character_map.md"),
                    file_size=len(md_text.encode()),
                ))
                log.info("markdown_rendered", job_id=job_id)
            except Exception as e:
                log.warning("markdown_render_failed", job_id=job_id, error=str(e))

            pdf_path: Path | None = None
            if md_text is not None:
                try:
                    pdf_path = render_pdf(md_text, job_id, artifact_dir)
                    session.add(Artifact(
                        id=uuid4(),
                        job_id=UUID(job_id),
                        format="pdf",
                        file_path=str(Path(job_id) / "character_map.pdf"),
                        file_size=pdf_path.stat().st_size,
                    ))
                    log.info("pdf_rendered", job_id=job_id)
                except Exception as e:
                    log.warning("pdf_render_failed", job_id=job_id, error=str(e))

            if job.email:
                try:
                    await send_completion_email(job, settings.base_url, pdf_path)
                except Exception as e:
                    log.warning("email_dispatch_error", job_id=job_id, error=str(e))

            # NOW the job is fully done — artifacts on disk, email dispatched.
            # Flip status='done' last so SSE only emits 'done' once the user
            # can actually fetch everything.
            job.status = "done"
            job.completed_at = datetime.now(tz=timezone.utc)
            duration_ms = int(
                (datetime.now(tz=timezone.utc) - started_at).total_seconds() * 1000
            )
            await record_event(
                session,
                "job_done",
                {
                    "model": job.model,
                    "character_count": len(char_map.characters),
                    "duration_ms": duration_ms,
                    "has_adaptation": bool(
                        job.adaptation_tmdb_id
                        or (job.resolved_meta or {}).get("adaptation_tmdb_id")
                    ),
                },
                job_id=UUID(job_id),
            )
            log.info("pipeline_done", job_id=job_id,
                     chars=len(char_map.characters), cost_usd=llm_result.cost_usd)

        await session.commit()
