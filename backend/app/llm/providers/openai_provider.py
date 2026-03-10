"""
OpenAI LLM provider using raw httpx (no openai SDK).
Pricing: gpt-4o input $5/M tokens, output $15/M tokens.
Retries on 429/500/503 with exponential backoff.
"""
import asyncio
import json
from typing import Optional

import httpx

from app.llm.base import LLMProvider
from app.llm.types import Message, LLMResponse
from app.core.logging import get_logger

logger = get_logger(__name__)

OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"

# Pricing per million tokens (USD)
GPT4O_INPUT_COST_PER_M = 5.0
GPT4O_OUTPUT_COST_PER_M = 15.0

# Models with different pricing
MODEL_PRICING: dict[str, tuple[float, float]] = {
    "gpt-4o": (5.0, 15.0),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4-turbo": (10.0, 30.0),
    "gpt-4": (30.0, 60.0),
    "gpt-3.5-turbo": (0.50, 1.50),
}

MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0  # seconds
RETRY_STATUSES = {429, 500, 503}


class OpenAIProvider(LLMProvider):
    """
    OpenAI chat completion provider using raw HTTP via httpx.
    Supports gpt-4o (default) and other OpenAI models.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o",
        timeout: float = 60.0,
        organization: Optional[str] = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout = timeout
        self._organization = organization

    def model_name(self) -> str:
        return self._model

    def provider_name(self) -> str:
        return "openai"

    def _calculate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """Calculate cost in USD based on token counts."""
        input_price, output_price = MODEL_PRICING.get(
            self._model, (GPT4O_INPUT_COST_PER_M, GPT4O_OUTPUT_COST_PER_M)
        )
        input_cost = (prompt_tokens / 1_000_000) * input_price
        output_cost = (completion_tokens / 1_000_000) * output_price
        return round(input_cost + output_cost, 8)

    def _build_headers(self) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        if self._organization:
            headers["OpenAI-Organization"] = self._organization
        return headers

    def _build_payload(self, messages: list[Message], max_tokens: int) -> dict:
        return {
            "model": self._model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "max_tokens": max_tokens,
        }

    async def complete(self, messages: list[Message], max_tokens: int = 2000) -> LLMResponse:
        """Send a chat completion request with retry logic."""
        headers = self._build_headers()
        payload = self._build_payload(messages, max_tokens)

        last_exception: Optional[Exception] = None

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            for attempt in range(MAX_RETRIES):
                try:
                    response = await client.post(
                        OPENAI_API_URL,
                        headers=headers,
                        json=payload,
                    )

                    if response.status_code in RETRY_STATUSES:
                        delay = RETRY_BASE_DELAY * (2 ** attempt)
                        logger.warning(
                            "openai_retry",
                            status_code=response.status_code,
                            attempt=attempt + 1,
                            delay=delay,
                        )
                        await asyncio.sleep(delay)
                        continue

                    response.raise_for_status()
                    data = response.json()

                    content = data["choices"][0]["message"]["content"]
                    usage = data.get("usage", {})
                    prompt_tokens = usage.get("prompt_tokens", 0)
                    completion_tokens = usage.get("completion_tokens", 0)

                    # Check for cached prompt tokens
                    cached_tokens = usage.get("prompt_tokens_details", {}).get("cached_tokens", 0)
                    is_cached = cached_tokens > 0

                    cost = self._calculate_cost(prompt_tokens, completion_tokens)

                    return LLMResponse(
                        content=content,
                        model=data.get("model", self._model),
                        provider="openai",
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        cached=is_cached,
                        cost_usd=cost,
                        raw_response=data,
                    )

                except httpx.HTTPStatusError as e:
                    if e.response.status_code not in RETRY_STATUSES:
                        logger.error(
                            "openai_http_error",
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
                        "openai_request_error",
                        error=str(e),
                        attempt=attempt + 1,
                        delay=delay,
                    )
                    await asyncio.sleep(delay)

        raise RuntimeError(
            f"OpenAI request failed after {MAX_RETRIES} attempts"
        ) from last_exception
