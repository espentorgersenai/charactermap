import json
import structlog
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4
from pydantic import ValidationError

from app.config import settings
from app.db.session import async_session_factory
from app.db.tables import Artifact, Job
from app.llm.anthropic_client import AnthropicClient
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
}


class RefusalError(Exception):
    def __init__(self, refusal_code: str) -> None:
        self.refusal_code = refusal_code
        super().__init__(refusal_code)


def _check_refusal(text: str) -> None:
    """Raise RefusalError if the text is a refusal JSON token."""
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return  # not JSON, let Pydantic handle it
    if isinstance(data, dict) and "refusal" in data:
        raise RefusalError(data["refusal"])


async def _enrich_with_credits(char_map: CharacterMap, job: Job) -> None:
    """Best-effort: populate Character.actor (fuzzy-matched) and char_map.creator.

    For film/tv: pull TMDB credits for `job.resolved_id`. For book: surface the
    author from resolved_meta (no headshot lookup yet — adaptation cast is a
    follow-up). Never raises — enrichment failures are logged and swallowed.
    """
    meta = job.resolved_meta or {}
    author_name = meta.get("author")
    director = None

    if job.work_type == "film_tv":
        media_type = meta.get("media_type")
        if media_type in ("movie", "tv"):
            try:
                tmdb_id = int(job.resolved_id)
            except (TypeError, ValueError):
                log.warning("enrichment_bad_tmdb_id", job_id=str(job.id), resolved_id=job.resolved_id)
            else:
                try:
                    cast, director = await get_credits(tmdb_id, media_type)
                    matched = match_cast_to_characters(char_map.characters, cast)
                    log.info(
                        "enrichment_cast_matched",
                        job_id=str(job.id),
                        cast_size=len(cast),
                        matched=matched,
                        total_chars=len(char_map.characters),
                    )
                except Exception as e:
                    log.warning("enrichment_credits_failed", job_id=str(job.id), error=str(e))
        else:
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
    _check_refusal(raw.text)
    try:
        result = CharacterMap.model_validate_json(raw.text)
        return result, raw
    except ValidationError as first_error:
        log.warning("llm_output_invalid_retrying", error=str(first_error))
        retry_message = (
            user_message
            + f"\n\nYour previous output was invalid. Validation error:\n{first_error}"
            + "\n\nFix the output and return only valid JSON conforming to the schema."
        )
        raw2 = await client.generate_character_map(system_prompt, retry_message, max_tokens)
        _check_refusal(raw2.text)
        result2 = CharacterMap.model_validate_json(raw2.text)  # raises if still invalid
        return result2, raw2


_PROMPT_PATH = Path(__file__).parent.parent.parent / "prompts" / "character_map.md"


def _load_prompt_template() -> str:
    return _PROMPT_PATH.read_text()


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
        f"<user_query>\n"
        f"{job.title_query}\n"
        f"</user_query>\n\n"
        f"Output a single JSON object matching the CharacterMap schema. No prose, no markdown fences."
    )


def get_llm_client(model: str) -> LLMClient:
    if model.startswith("claude-"):
        return AnthropicClient(model=model, api_key=settings.anthropic_api_key)
    raise NotImplementedError(f"Model {model!r} not yet wired (Phase 5 adds OpenAI + Google)")


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

        system_prompt = _load_prompt_template()
        user_message = _render_user_message(job)
        client = get_llm_client(job.model)

        try:
            char_map, llm_result = await call_and_validate(
                client, system_prompt, user_message
            )
            _sweep_spoiler_levels(char_map)
            await _enrich_with_credits(char_map, job)
        except RefusalError as e:
            job.status = "refused"
            job.error_code = e.refusal_code
            job.error_message = REFUSAL_MESSAGES.get(
                e.refusal_code, REFUSAL_MESSAGES["unknown_work"]
            )
            log.warning("pipeline_refused", job_id=job_id, code=e.refusal_code)
        except ValidationError as e:
            job.status = "failed"
            job.error_code = "invalid_json"
            job.error_message = "LLM output failed schema validation after retry."
            log.error("pipeline_validation_failed", job_id=job_id, error=str(e))
        except Exception as e:
            job.status = "failed"
            job.error_code = "llm_error"
            job.error_message = str(e)
            log.error("pipeline_error", job_id=job_id, error=str(e))
        else:
            job.status = "done"
            job.completed_at = datetime.now(tz=timezone.utc)
            job.character_map = char_map.model_dump()
            job.llm_input_tokens = llm_result.input_tokens
            job.llm_output_tokens = llm_result.output_tokens
            job.estimated_cost_usd = Decimal(str(llm_result.cost_usd))
            log.info("pipeline_done", job_id=job_id,
                     chars=len(char_map.characters), cost_usd=llm_result.cost_usd)

            # Render Markdown + PDF artifacts
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

        await session.commit()
