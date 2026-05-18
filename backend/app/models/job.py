from typing import Optional
from pydantic import BaseModel, field_validator

from app.models.api import ResolveCandidate

VALID_MODELS = {
    "claude-sonnet-4-6",
    "claude-opus-4-7",
    "claude-haiku-4-5-20251001",
    "gpt-5.5",
    "gemini-2.5-pro",
}

VALID_FORMATS = {"interactive", "png", "svg", "json", "markdown", "pdf"}


class JobCreateRequest(BaseModel):
    title_query: str
    resolved: ResolveCandidate
    model: str
    formats: list[str]
    email: Optional[str] = None
    acknowledged_spoilers: bool
    turnstile_token: Optional[str] = None

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


class JobCreateResponse(BaseModel):
    job_id: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    character_map: Optional[dict] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
