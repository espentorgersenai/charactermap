from typing import Optional
from pydantic import BaseModel, field_validator

from app.models.api import ResolveCandidate

VALID_MODELS = {
    "claude-sonnet-4-6",
    "claude-opus-4-7",
    "gpt-5.5",
    "gemini-2.5-pro",
}

VALID_FORMATS = {"interactive", "png", "svg", "json", "markdown", "pdf"}
VALID_CHARACTER_CAPS = {10, 20, 30, 40, 50}


class JobCreateRequest(BaseModel):
    title_query: str
    resolved: ResolveCandidate
    model: str
    formats: list[str]
    email: Optional[str] = None
    acknowledged_spoilers: bool
    turnstile_token: Optional[str] = None
    character_cap: int = 20

    @field_validator("model")
    @classmethod
    def model_must_be_valid(cls, v: str) -> str:
        if v not in VALID_MODELS:
            raise ValueError(f"model must be one of {sorted(VALID_MODELS)}")
        return v

    @field_validator("formats")
    @classmethod
    def formats_must_be_nonempty(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("formats must contain at least one value")
        return v

    @field_validator("character_cap")
    @classmethod
    def cap_must_be_valid(cls, v: int) -> int:
        if v not in VALID_CHARACTER_CAPS:
            raise ValueError(f"character_cap must be one of {sorted(VALID_CHARACTER_CAPS)}")
        return v


class JobCreateResponse(BaseModel):
    job_id: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    # Fine-grained sub-stage code within status='generating'. Frontend maps
    # the short code to user-facing copy ('searching the web', 'rendering', …).
    # Values: searching | structuring | generating | enriching | rendering | None
    progress_stage: Optional[str] = None
    character_map: Optional[dict] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
