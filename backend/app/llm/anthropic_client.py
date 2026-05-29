import anthropic
import structlog

from app.llm.base import LLMClient, LLMResult

log = structlog.get_logger()

# Cost per 1M tokens (MTok), USD — update as prices change
_COST_PER_MTOK = {
    "claude-sonnet-4-6":         {"input": 3.00,  "output": 15.00},
    "claude-opus-4-7":           {"input": 15.00, "output": 75.00},
    "claude-haiku-4-5-20251001": {"input": 0.80,  "output": 4.00},
}
_DEFAULT_COST = {"input": 3.00, "output": 15.00}


class AnthropicClient:
    def __init__(self, model: str, api_key: str) -> None:
        self.model = model
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    async def generate_character_map(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 16384,
    ) -> LLMResult:
        message = await self._client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=[
                {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user_message}],
        )
        text = message.content[0].text
        input_tokens = message.usage.input_tokens
        output_tokens = message.usage.output_tokens
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

    async def generate_with_web_search(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 8192,
        max_searches: int = 3,
    ) -> LLMResult:
        """Call the model with the server-side web_search tool enabled and
        return the concatenated text-block content as analysis prose.

        Anthropic charges separately for web_search (~$0.01/search at current
        rates). We don't add it to `cost_usd` here; the daily cost guard is the
        real safety net and search count is logged for accounting.
        """
        # `temperature` was deprecated on Sonnet 4.6 / Opus 4.7 — sending it
        # returns a 400 invalid_request_error. Use the model's native default.
        message = await self._client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=[
                {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user_message}],
            tools=[
                {
                    "type": "web_search_20250305",
                    "name": "web_search",
                    "max_uses": max_searches,
                }
            ],
        )
        text_parts: list[str] = []
        search_count = 0
        for block in message.content:
            btype = getattr(block, "type", None)
            if btype == "text":
                text_parts.append(block.text)
            elif btype == "server_tool_use":
                search_count += 1
        text = "\n".join(text_parts)
        input_tokens = message.usage.input_tokens
        output_tokens = message.usage.output_tokens
        cost = self._compute_cost(input_tokens, output_tokens)
        log.info(
            "llm_call_with_search",
            model=self.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            search_count=search_count,
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
