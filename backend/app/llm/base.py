from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class LLMResult:
    text: str
    input_tokens: int
    output_tokens: int
    cost_usd: float


@runtime_checkable
class LLMClient(Protocol):
    async def generate_character_map(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 16384,
    ) -> LLMResult: ...
