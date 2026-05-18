import openai
import structlog

from app.llm.base import LLMResult

log = structlog.get_logger()

# Cost per 1M tokens (MTok), USD. Best-effort defaults — verify against the
# OpenAI pricing page before any public deploy with traffic. The daily cost
# guard is the real safety net regardless.
_COST_PER_MTOK = {
    "gpt-5.5":   {"input": 1.25,  "output": 10.00},
    "gpt-5":     {"input": 1.25,  "output": 10.00},
    "gpt-5-mini":{"input": 0.25,  "output": 2.00},
}
_DEFAULT_COST = {"input": 1.25, "output": 10.00}

# GPT-5 family rejects `max_tokens` and only accepts `max_completion_tokens`.
# We pass the latter unconditionally for OpenAI clients.


class OpenAIClient:
    def __init__(self, model: str, api_key: str) -> None:
        self.model = model
        self._client = openai.AsyncOpenAI(api_key=api_key)

    async def generate_character_map(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 16384,
    ) -> LLMResult:
        # response_format={"type": "json_object"} forces well-formed JSON output.
        # OpenAI requires the prompt to mention "JSON" somewhere — ours does
        # (the prompt's rule 11 and user_message both name it).
        completion = await self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            max_completion_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
        choice = completion.choices[0]
        text = choice.message.content or ""
        input_tokens = completion.usage.prompt_tokens
        output_tokens = completion.usage.completion_tokens
        cost = self._compute_cost(input_tokens, output_tokens)
        log.info(
            "llm_call",
            model=self.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            finish_reason=choice.finish_reason,
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
