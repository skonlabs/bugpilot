"""
Azure OpenAI LLM provider using raw httpx.
Uses the Azure OpenAI REST API with deployment-based routing.
Retries on 429/500/503 with exponential backoff.
"""
import asyncio
from typing import Optional

import httpx

from app.llm.base import LLMProvider
from app.llm.types import Message, LLMResponse
from app.core.logging import get_logger

logger = get_logger(__name__)

MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0  # seconds
RETRY_STATUSES = {429, 500, 503}

# Azure OpenAI typically mirrors OpenAI pricing but we cannot know the deployment model
# Default to gpt-4o pricing; callers can override via subclassing or pass pricing params.
DEFAULT_INPUT_COST_PER_M = 5.0
DEFAULT_OUTPUT_COST_PER_M = 15.0


class AzureOpenAIProvider(LLMProvider):
    """
    Azure OpenAI chat completion provider.

    The Azure REST endpoint pattern is:
      POST {endpoint}/openai/deployments/{deployment_name}/chat/completions
           ?api-version={api_version}
    """

    def __init__(
        self,
        endpoint: str,
        api_key: str,
        deployment_name: str,
        api_version: str = "2024-02-01",
        timeout: float = 60.0,
        input_cost_per_million_tokens: float = DEFAULT_INPUT_COST_PER_M,
        output_cost_per_million_tokens: float = DEFAULT_OUTPUT_COST_PER_M,
    ) -> None:
        # Normalize endpoint — strip trailing slash
        self._endpoint = endpoint.rstrip("/")
        self._api_key = api_key
        self._deployment_name = deployment_name
        self._api_version = api_version
        self._timeout = timeout
        self._input_cost_per_m = input_cost_per_million_tokens
        self._output_cost_per_m = output_cost_per_million_tokens

    def model_name(self) -> str:
        return self._deployment_name

    def provider_name(self) -> str:
        return "azure_openai"

    def _api_url(self) -> str:
        return (
            f"{self._endpoint}/openai/deployments/{self._deployment_name}"
            f"/chat/completions?api-version={self._api_version}"
        )

    def _build_headers(self) -> dict[str, str]:
        return {
            "api-key": self._api_key,
            "Content-Type": "application/json",
        }

    def _build_payload(self, messages: list[Message], max_tokens: int) -> dict:
        return {
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "max_tokens": max_tokens,
        }

    def _calculate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """Calculate cost in USD based on configured per-million token prices."""
        input_cost = (prompt_tokens / 1_000_000) * self._input_cost_per_m
        output_cost = (completion_tokens / 1_000_000) * self._output_cost_per_m
        return round(input_cost + output_cost, 8)

    async def complete(self, messages: list[Message], max_tokens: int = 2000) -> LLMResponse:
        """Send a chat completion request with retry logic."""
        url = self._api_url()
        headers = self._build_headers()
        payload = self._build_payload(messages, max_tokens)

        last_exception: Optional[Exception] = None

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            for attempt in range(MAX_RETRIES):
                try:
                    response = await client.post(
                        url,
                        headers=headers,
                        json=payload,
                    )

                    if response.status_code in RETRY_STATUSES:
                        delay = RETRY_BASE_DELAY * (2 ** attempt)
                        logger.warning(
                            "azure_openai_retry",
                            status_code=response.status_code,
                            attempt=attempt + 1,
                            delay=delay,
                            deployment=self._deployment_name,
                        )
                        await asyncio.sleep(delay)
                        continue

                    response.raise_for_status()
                    data = response.json()

                    content = data["choices"][0]["message"]["content"]
                    usage = data.get("usage", {})
                    prompt_tokens = usage.get("prompt_tokens", 0)
                    completion_tokens = usage.get("completion_tokens", 0)

                    # Azure OpenAI may surface cached prompt token counts
                    cached_tokens = (
                        usage.get("prompt_tokens_details", {}).get("cached_tokens", 0)
                    )
                    is_cached = cached_tokens > 0

                    cost = self._calculate_cost(prompt_tokens, completion_tokens)

                    return LLMResponse(
                        content=content,
                        model=self._deployment_name,
                        provider="azure_openai",
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        cached=is_cached,
                        cost_usd=cost,
                        raw_response=data,
                    )

                except httpx.HTTPStatusError as e:
                    if e.response.status_code not in RETRY_STATUSES:
                        logger.error(
                            "azure_openai_http_error",
                            status_code=e.response.status_code,
                            body=e.response.text[:500],
                            deployment=self._deployment_name,
                        )
                        raise
                    last_exception = e
                    delay = RETRY_BASE_DELAY * (2 ** attempt)
                    await asyncio.sleep(delay)

                except httpx.RequestError as e:
                    last_exception = e
                    delay = RETRY_BASE_DELAY * (2 ** attempt)
                    logger.warning(
                        "azure_openai_request_error",
                        error=str(e),
                        attempt=attempt + 1,
                        delay=delay,
                    )
                    await asyncio.sleep(delay)

        raise RuntimeError(
            f"Azure OpenAI request failed after {MAX_RETRIES} attempts "
            f"(deployment: {self._deployment_name})"
        ) from last_exception
