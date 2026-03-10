"""
OpenAI-compatible LLM provider.

Works with any server that implements the OpenAI /v1/chat/completions API:
  - vLLM          (self-hosted, any HuggingFace model)
  - LM Studio     (desktop local models)
  - LocalAI       (local, supports llama.cpp / whisper / etc)
  - Together.ai   (cloud, many OSS models)
  - Groq          (cloud, ultra-fast inference)
  - Fireworks.ai  (cloud, fine-tuned OSS models)
  - Perplexity    (cloud, search-augmented)
  - Any endpoint that speaks POST /v1/chat/completions

Usage:
    provider = OpenAICompatibleProvider(
        base_url="https://my-vllm.company.com",
        api_key="sk-...",           # set to "none" for unauthenticated endpoints
        model="mistral-7b-instruct",
    )
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
RETRY_STATUSES = {429, 500, 502, 503}


class OpenAICompatibleProvider(LLMProvider):
    """
    Generic OpenAI-compatible chat completion provider.

    Targets POST {base_url}/v1/chat/completions.
    Cost tracking is optional — pass input/output prices if known, leave at 0
    for free/self-hosted models.
    """

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str = "none",
        timeout: float = 120.0,
        input_cost_per_million_tokens: float = 0.0,
        output_cost_per_million_tokens: float = 0.0,
        extra_headers: Optional[dict[str, str]] = None,
    ) -> None:
        """
        Args:
            base_url: Root URL of the endpoint, e.g. "https://my-vllm.example.com"
                      The path "/v1/chat/completions" is appended automatically.
            model: Model name or identifier to pass in the request body.
            api_key: Bearer token. Pass "none" for unauthenticated local endpoints.
            timeout: Request timeout in seconds. Local/slow models may need >60s.
            input_cost_per_million_tokens: Optional cost for usage tracking.
            output_cost_per_million_tokens: Optional cost for usage tracking.
            extra_headers: Any extra HTTP headers required by the endpoint
                           (e.g. "X-Custom-Token" for private deployments).
        """
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._api_key = api_key
        self._timeout = timeout
        self._input_cost_per_m = input_cost_per_million_tokens
        self._output_cost_per_m = output_cost_per_million_tokens
        self._extra_headers = extra_headers or {}

    # ------------------------------------------------------------------
    # LLMProvider interface
    # ------------------------------------------------------------------

    def model_name(self) -> str:
        return self._model

    def provider_name(self) -> str:
        return "openai_compatible"

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _api_url(self) -> str:
        return f"{self._base_url}/v1/chat/completions"

    def _build_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._api_key and self._api_key.lower() != "none":
            headers["Authorization"] = f"Bearer {self._api_key}"
        headers.update(self._extra_headers)
        return headers

    def _build_payload(self, messages: list[Message], max_tokens: int) -> dict:
        return {
            "model": self._model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "max_tokens": max_tokens,
        }

    def _calculate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        if self._input_cost_per_m == 0.0 and self._output_cost_per_m == 0.0:
            return 0.0
        input_cost = (prompt_tokens / 1_000_000) * self._input_cost_per_m
        output_cost = (completion_tokens / 1_000_000) * self._output_cost_per_m
        return round(input_cost + output_cost, 8)

    async def complete(self, messages: list[Message], max_tokens: int = 2000) -> LLMResponse:
        url = self._api_url()
        headers = self._build_headers()
        payload = self._build_payload(messages, max_tokens)

        last_exception: Optional[Exception] = None

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            for attempt in range(MAX_RETRIES):
                try:
                    response = await client.post(url, headers=headers, json=payload)

                    if response.status_code in RETRY_STATUSES:
                        delay = RETRY_BASE_DELAY * (2 ** attempt)
                        logger.warning(
                            "openai_compatible_retry",
                            base_url=self._base_url,
                            model=self._model,
                            status_code=response.status_code,
                            attempt=attempt + 1,
                            delay=delay,
                        )
                        await asyncio.sleep(delay)
                        continue

                    response.raise_for_status()
                    data = response.json()

                    # OpenAI-compatible response format
                    content = data["choices"][0]["message"]["content"]
                    usage = data.get("usage", {})
                    prompt_tokens = usage.get("prompt_tokens", 0)
                    completion_tokens = usage.get("completion_tokens", 0)

                    # Some providers surface cached token counts the same way OpenAI does
                    cached_tokens = usage.get("prompt_tokens_details", {}).get("cached_tokens", 0)
                    is_cached = cached_tokens > 0

                    cost = self._calculate_cost(prompt_tokens, completion_tokens)

                    return LLMResponse(
                        content=content,
                        model=data.get("model", self._model),
                        provider="openai_compatible",
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        cached=is_cached,
                        cost_usd=cost,
                        raw_response=data,
                    )

                except httpx.ConnectError as e:
                    logger.error(
                        "openai_compatible_connection_failed",
                        base_url=self._base_url,
                        error=str(e),
                    )
                    raise RuntimeError(
                        f"Cannot connect to LLM endpoint at {self._base_url}. "
                        "Check that the server is running and the base_url is correct."
                    ) from e

                except httpx.HTTPStatusError as e:
                    if e.response.status_code not in RETRY_STATUSES:
                        logger.error(
                            "openai_compatible_http_error",
                            base_url=self._base_url,
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
                        "openai_compatible_request_error",
                        base_url=self._base_url,
                        error=str(e),
                        attempt=attempt + 1,
                    )
                    await asyncio.sleep(delay)

        raise RuntimeError(
            f"LLM request failed after {MAX_RETRIES} attempts "
            f"(base_url={self._base_url}, model={self._model})"
        ) from last_exception
