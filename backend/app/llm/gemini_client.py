from typing import Optional

import structlog
from google import genai
from google.genai import types

from app.llm.base import LLMResult

log = structlog.get_logger()

# Cost per 1M tokens (MTok), USD. Best-effort defaults — verify against
# Google's pricing page before any public deploy with traffic. Gemini 2.5 Pro
# also has a price tier above 200K input tokens which we ignore for now (the
# character-map prompt is <2K input).
_COST_PER_MTOK = {
    "gemini-2.5-pro":   {"input": 1.25, "output": 10.00},
    "gemini-2.5-flash": {"input": 0.30, "output": 2.50},
}
_DEFAULT_COST = {"input": 1.25, "output": 10.00}


class GeminiClient:
    def __init__(
        self,
        model: str,
        api_key: str = "",
        project: Optional[str] = None,
        location: str = "us-central1",
    ) -> None:
        self.model = model
        # google-genai's Client is sync at construction; async calls go via
        # client.aio.models.* — see _generate below.
        if project:
            # Vertex AI mode — uses ADC (gcloud auth application-default login
            # locally, or GOOGLE_APPLICATION_CREDENTIALS in containers). Some
            # orgs disallow API keys; Vertex/ADC is the only path there.
            self._client = genai.Client(vertexai=True, project=project, location=location)
        else:
            # AI Studio mode — direct API key against generativelanguage.googleapis.com.
            self._client = genai.Client(api_key=api_key)

    async def generate_character_map(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 16384,
    ) -> LLMResult:
        # response_mime_type="application/json" forces a JSON response. We do
        # not pass a response_schema because our schema relies on union types
        # (faction_id: string | null, etc.) that the Gemini schema validator
        # rejects with cryptic errors; Pydantic validation post-LLM is enough.
        response = await self._client.aio.models.generate_content(
            model=self.model,
            contents=user_message,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                max_output_tokens=max_tokens,
                response_mime_type="application/json",
            ),
        )
        text = response.text or ""
        usage = response.usage_metadata
        input_tokens = usage.prompt_token_count or 0
        output_tokens = usage.candidates_token_count or 0
        cost = self._compute_cost(input_tokens, output_tokens)
        log.info(
            "llm_call",
            model=self.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
        )
        return LLMResult(
            text=text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
        )

    def _compute_cost(self, input_tokens: int, output_tokens: int) -> float:
        rates = _COST_PER_MTOK.get(self.model, _DEFAULT_COST)
        return (input_tokens * rates["input"] + output_tokens * rates["output"]) / 1_000_000
