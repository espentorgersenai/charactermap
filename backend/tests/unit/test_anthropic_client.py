import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.llm.anthropic_client import AnthropicClient
from app.llm.base import LLMResult


@pytest.fixture
def mock_message():
    msg = MagicMock()
    msg.content = [MagicMock(text='{"title": "Congo"}')]
    msg.usage = MagicMock(input_tokens=100, output_tokens=200)
    return msg


@pytest.mark.asyncio
async def test_generate_returns_llm_result(mock_message):
    with patch("app.llm.anthropic_client.anthropic.AsyncAnthropic") as mock_cls:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_message)
        mock_cls.return_value = mock_client

        client = AnthropicClient(model="claude-sonnet-4-6", api_key="sk-test")
        result = await client.generate_character_map(
            system_prompt="You are a generator.",
            user_message="Generate Congo.",
        )

    assert isinstance(result, LLMResult)
    assert result.text == '{"title": "Congo"}'
    assert result.input_tokens == 100
    assert result.output_tokens == 200
    assert result.cost_usd >= 0


@pytest.mark.asyncio
async def test_generate_passes_system_and_user(mock_message):
    with patch("app.llm.anthropic_client.anthropic.AsyncAnthropic") as mock_cls:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_message)
        mock_cls.return_value = mock_client

        client = AnthropicClient(model="claude-sonnet-4-6", api_key="sk-test")
        await client.generate_character_map(
            system_prompt="system",
            user_message="user",
        )

        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs["model"] == "claude-sonnet-4-6"
        # system content passed as list for prompt caching
        assert call_kwargs["system"][0]["text"] == "system"
        assert call_kwargs["messages"][0]["content"] == "user"
