"""
Anthropic LLM provider using raw httpx (no anthropic SDK).
Default model: claude-sonnet-4-6.
Retries on 429/500/529 with exponential backoff.
"""
import asyncio
import json
from typing import Optional

import httpx

from app.llm.base import LLMProvider
from app.llm.types import Message, LLMResponse
from app.core.logging import get_logger

logger = get_logger(__name__)

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_API_VERSION = "2023-06-01"
DEFAULT_MODEL = "claude-sonnet-4-6"

# Pricing per million tokens (USD) — approximate at time of implementation
MODEL_PRICING: dict[str, tuple[float, float]] = {
    "claude-opus-4-6": (15.0, 75.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-3-5": (0.80, 4.0),
    "claude-3-opus-20240229": (15.0, 75.0),
    "claude-3-sonnet-20240229": (3.0, 15.0),
    "claude-3-haiku-20240307": (0.25, 1.25),
}

MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0  # seconds
RETRY_STATUSES = {429, 500, 529}  # 529 = Anthropic overloaded


class AnthropicProvider(LLMProvider):
    """
    Anthropic Messages API provider using raw HTTP via httpx.
    Supports claude-sonnet-4-6 (default) and other Claude models.
    """

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
        timeout: float = 60.0,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout = timeout

    def model_name(self) -> str:
        return self._model

    def provider_name(self) -> str:
        return "anthropic"

    def _calculate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """Calculate cost in USD based on token counts."""
        # Default to sonnet pricing if model not found
        input_price, output_price = MODEL_PRICING.get(self._model, (3.0, 15.0))
        input_cost = (prompt_tokens / 1_000_000) * input_price
        output_cost = (completion_tokens / 1_000_000) * output_price
        return round(input_cost + output_cost, 8)

    def _build_headers(self) -> dict[str, str]:
        return {
            "x-api-key": self._api_key,
            "anthropic-version": ANTHROPIC_API_VERSION,
            "content-type": "application/json",
        }

    def _split_system_messages(
        self, messages: list[Message]
    ) -> tuple[Optional[str], list[dict]]:
        """
        Anthropic requires system prompt as a top-level field.
        Extract system messages and return (system_text, user_assistant_messages).
        """
        system_parts = []
        conversation = []
        for m in messages:
            if m.role == "system":
                system_parts.append(m.content)
            else:
                conversation.append({"role": m.role, "content": m.content})
        system_text = "\n\n".join(system_parts) if system_parts else None
        return system_text, conversation

    def _build_payload(
        self,
        messages: list[Message],
        max_tokens: int,
    ) -> dict:
        system_text, conversation = self._split_system_messages(messages)
        payload: dict = {
            "model": self._model,
            "max_tokens": max_tokens,
            "messages": conversation,
        }
        if system_text:
            payload["system"] = system_text
        return payload

    async def complete(self, messages: list[Message], max_tokens: int = 2000) -> LLMResponse:
        """Send a messages request with retry logic."""
        headers = self._build_headers()
        payload = self._build_payload(messages, max_tokens)

        last_exception: Optional[Exception] = None

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            for attempt in range(MAX_RETRIES):
                try:
                    response = await client.post(
                        ANTHROPIC_API_URL,
                        headers=headers,
                        json=payload,
                    )

                    if response.status_code in RETRY_STATUSES:
                        delay = RETRY_BASE_DELAY * (2 ** attempt)
                        logger.warning(
                            "anthropic_retry",
                            status_code=response.status_code,
                            attempt=attempt + 1,
                            delay=delay,
                        )
                        await asyncio.sleep(delay)
                        continue

                    response.raise_for_status()
                    data = response.json()

                    # Extract text content from response
                    content_blocks = data.get("content", [])
                    content = ""
                    for block in content_blocks:
                        if block.get("type") == "text":
                            content += block.get("text", "")

                    usage = data.get("usage", {})
                    prompt_tokens = usage.get("input_tokens", 0)
                    completion_tokens = usage.get("output_tokens", 0)

                    # Detect cache usage
                    cache_read_tokens = usage.get("cache_read_input_tokens", 0)
                    is_cached = cache_read_tokens > 0

                    cost = self._calculate_cost(prompt_tokens, completion_tokens)

                    return LLMResponse(
                        content=content,
                        model=data.get("model", self._model),
                        provider="anthropic",
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        cached=is_cached,
                        cost_usd=cost,
                        raw_response=data,
                    )

                except httpx.HTTPStatusError as e:
                    if e.response.status_code not in RETRY_STATUSES:
                        logger.error(
                            "anthropic_http_error",
                            status_code=e.response.status_code,
                            body=e.response.text[:500],
                        )
                        raise
                    last_exception = e
                    delay = RETRY_BASE_DELAY * (2 ** attempt)
                    await asyncio.sleep(delay)

                except httpx.RequestError as e:
                    last_exception = e
                    delay = RETRY_BASE_DELAY * (2 ** attempt)
                    logger.warning(
                        "anthropic_request_error",
                        error=str(e),
                        attempt=attempt + 1,
                        delay=delay,
                    )
                    await asyncio.sleep(delay)

        raise RuntimeError(
            f"Anthropic request failed after {MAX_RETRIES} attempts"
        ) from last_exception
