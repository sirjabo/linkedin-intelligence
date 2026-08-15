"""LLMProvider protocol and Anthropic implementation.

All agents must use this layer — never import the anthropic SDK directly in agent code.
"""
from typing import Any, AsyncGenerator, Protocol, runtime_checkable
import anthropic
from pydantic import BaseModel

from app.core.config import settings
from app.core.logging import get_logger
from app.services.ai.cost_tracker import track_call, COST_PER_MILLION_TOKENS

logger = get_logger(__name__)


@runtime_checkable
class LLMProvider(Protocol):
    async def generate(
        self,
        system: str,
        messages: list[dict[str, str]],
        model: str,
        max_tokens: int = 4096,
    ) -> str: ...

    async def structured_output(
        self,
        system: str,
        messages: list[dict[str, str]],
        schema: type[BaseModel],
        model: str,
        max_tokens: int = 4096,
    ) -> BaseModel: ...

    async def stream(
        self,
        system: str,
        messages: list[dict[str, str]],
        model: str,
        max_tokens: int = 4096,
    ) -> AsyncGenerator[str, None]: ...


class AnthropicProvider:
    def __init__(self) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    async def generate(
        self,
        system: str,
        messages: list[dict[str, str]],
        model: str,
        max_tokens: int = 4096,
    ) -> str:
        response = await self._client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
        )
        input_tok = response.usage.input_tokens
        output_tok = response.usage.output_tokens
        track_call(model=model, input_tokens=input_tok, output_tokens=output_tok)
        logger.info(
            "llm_call",
            model=model,
            input_tokens=input_tok,
            output_tokens=output_tok,
            cost_usd=_estimate_cost(model, input_tok, output_tok),
        )
        return response.content[0].text

    async def structured_output(
        self,
        system: str,
        messages: list[dict[str, str]],
        schema: type[BaseModel],
        model: str,
        max_tokens: int = 4096,
    ) -> BaseModel:
        """Use Anthropic tool_use to return a validated Pydantic model."""
        tool_def = _pydantic_to_tool(schema)
        response = await self._client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
            tools=[tool_def],
            tool_choice={"type": "tool", "name": tool_def["name"]},
        )
        input_tok = response.usage.input_tokens
        output_tok = response.usage.output_tokens
        track_call(model=model, input_tokens=input_tok, output_tokens=output_tok)
        logger.info(
            "llm_structured_call",
            model=model,
            schema=schema.__name__,
            input_tokens=input_tok,
            output_tokens=output_tok,
            cost_usd=_estimate_cost(model, input_tok, output_tok),
        )
        for block in response.content:
            if block.type == "tool_use":
                return schema.model_validate(block.input)
        raise RuntimeError(f"No tool_use block in response for schema {schema.__name__}")

    async def stream(
        self,
        system: str,
        messages: list[dict[str, str]],
        model: str,
        max_tokens: int = 4096,
    ) -> AsyncGenerator[str, None]:
        async with self._client.messages.stream(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
        ) as stream:
            async for chunk in stream.text_stream:
                yield chunk


def _pydantic_to_tool(schema: type[BaseModel]) -> dict[str, Any]:
    """Convert a Pydantic model to an Anthropic tool definition."""
    json_schema = schema.model_json_schema()
    return {
        "name": schema.__name__,
        "description": schema.__doc__ or f"Return a {schema.__name__} object",
        "input_schema": json_schema,
    }


def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    rates = COST_PER_MILLION_TOKENS.get(model, {"input": 3.0, "output": 15.0})
    return (input_tokens * rates["input"] + output_tokens * rates["output"]) / 1_000_000


# Singleton instance — import this in agents
default_provider = AnthropicProvider()
