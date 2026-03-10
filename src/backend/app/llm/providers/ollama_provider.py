"""
Ollama LLM provider using raw httpx.
Targets locally running Ollama instances via the /api/chat endpoint.
No cost tracking (local model).
"""
import asyncio
import json
from typing import Optional

import httpx

from app.llm.base import LLMProvider
from app.llm.types import Message, LLMResponse
from app.core.logging import get_logger

logger = get_logger(__name__)

DEFAULT_BASE_URL = "http://localhost:11434"
MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0  # seconds
RETRY_STATUSES = {500, 503}


class OllamaProvider(LLMProvider):
    """
    Ollama local model provider.
    Uses the /api/chat endpoint which follows the OpenAI chat format.

    Ollama does not charge per token — cost_usd is always 0.0.
    """

    def __init__(
        self,
        model: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 120.0,  # Local models can be slow
        keep_alive: str = "5m",
    ) -> None:
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._keep_alive = keep_alive

    def model_name(self) -> str:
        return self._model

    def provider_name(self) -> str:
        return "ollama"

    def _api_url(self) -> str:
        return f"{self._base_url}/api/chat"

    def _build_payload(self, messages: list[Message], max_tokens: int) -> dict:
        return {
            "model": self._model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
            "keep_alive": self._keep_alive,
            "options": {
                "num_predict": max_tokens,
            },
        }

    async def complete(self, messages: list[Message], max_tokens: int = 2000) -> LLMResponse:
        """Send a chat request to the local Ollama instance."""
        url = self._api_url()
        payload = self._build_payload(messages, max_tokens)

        last_exception: Optional[Exception] = None

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            for attempt in range(MAX_RETRIES):
                try:
                    response = await client.post(
                        url,
                        json=payload,
                    )

                    if response.status_code in RETRY_STATUSES:
                        delay = RETRY_BASE_DELAY * (2 ** attempt)
                        logger.warning(
                            "ollama_retry",
                            status_code=response.status_code,
                            attempt=attempt + 1,
                            delay=delay,
                            model=self._model,
                        )
                        await asyncio.sleep(delay)
                        continue

                    response.raise_for_status()
                    data = response.json()

                    # Ollama /api/chat response structure
                    message = data.get("message", {})
                    content = message.get("content", "")

                    # Token counts from eval_count fields
                    prompt_tokens = data.get("prompt_eval_count", 0)
                    completion_tokens = data.get("eval_count", 0)

                    # Ollama signals done via "done" field
                    if not data.get("done", True):
                        logger.warning("ollama_incomplete_response", model=self._model)

                    return LLMResponse(
                        content=content,
                        model=self._model,
                        provider="ollama",
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        cached=False,
                        cost_usd=0.0,  # Local model — no cost
                        raw_response=data,
                    )

                except httpx.ConnectError as e:
                    # Ollama may not be running
                    logger.error(
                        "ollama_connection_failed",
                        base_url=self._base_url,
                        error=str(e),
                    )
                    raise RuntimeError(
                        f"Cannot connect to Ollama at {self._base_url}. "
                        "Ensure Ollama is running: `ollama serve`"
                    ) from e

                except httpx.HTTPStatusError as e:
                    if e.response.status_code not in RETRY_STATUSES:
                        logger.error(
                            "ollama_http_error",
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
                        "ollama_request_error",
                        error=str(e),
                        attempt=attempt + 1,
                        delay=delay,
                    )
                    await asyncio.sleep(delay)

        raise RuntimeError(
            f"Ollama request failed after {MAX_RETRIES} attempts (model: {self._model})"
        ) from last_exception
