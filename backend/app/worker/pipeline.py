import json
import structlog
from pydantic import ValidationError

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
    max_tokens: int = 4096,
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
