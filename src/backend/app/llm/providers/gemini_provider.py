"""
Google Gemini LLM provider (Google AI Studio — API key based).

Uses the Gemini generateContent REST API directly.
No Google SDK dependency — raw httpx only.

Supported models:
  gemini-2.0-flash        fastest, cheapest   ($0.10/M input, $0.40/M output)
  gemini-2.0-flash-lite   ultra-cheap         ($0.075/M input, $0.30/M output)
  gemini-1.5-pro          highest quality     ($1.25/M input <128k, $5.00/M output)
  gemini-1.5-flash        balanced            ($0.075/M input <128k, $0.30/M output)
  gemini-1.5-flash-8b     smallest/cheapest   ($0.0375/M input, $0.15/M output)

API key: get one at https://aistudio.google.com/app/apikey
"""
import asyncio
from typing import Optional

import httpx

from app.llm.base import LLMProvider
from app.llm.types import Message, LLMResponse
from app.core.logging import get_logger

logger = get_logger(__name__)

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

# Pricing per million tokens (USD) — as of 2025
# Prompts ≤128k tokens use the lower tier; we track at lower tier for simplicity.
MODEL_PRICING: dict[str, tuple[float, float]] = {
    "gemini-2.0-flash":       (0.10,  0.40),
    "gemini-2.0-flash-lite":  (0.075, 0.30),
    "gemini-1.5-pro":         (1.25,  5.00),
    "gemini-1.5-flash":       (0.075, 0.30),
    "gemini-1.5-flash-8b":    (0.0375, 0.15),
}

MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0
RETRY_STATUSES = {429, 500, 503}


class GeminiProvider(LLMProvider):
    """
    Google Gemini provider using the AI Studio generateContent REST API.

    Authentication: API key passed as a query parameter (?key=...).
    This is the simplest auth model — ideal for BYOK where the customer
    creates a key at aistudio.google.com and supplies it via config.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.0-flash",
        timeout: float = 60.0,
    ) -> None:
        """
        Args:
            api_key: Google AI Studio API key.
            model: Gemini model ID (see module docstring for options).
            timeout: Request timeout in seconds.
        """
        self._api_key = api_key
        self._model = model
        self._timeout = timeout

    # ------------------------------------------------------------------
    # LLMProvider interface
    # ------------------------------------------------------------------

    def model_name(self) -> str:
        return self._model

    def provider_name(self) -> str:
        return "gemini"

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _api_url(self) -> str:
        return f"{GEMINI_API_BASE}/{self._model}:generateContent?key={self._api_key}"

    def _messages_to_gemini(self, messages: list[Message]) -> tuple[Optional[str], list[dict]]:
        """
        Convert OpenAI-style messages to Gemini's contents format.

        Gemini separates the system instruction from the conversation turns.
        Returns (system_instruction, contents_list).
        """
        system_text: Optional[str] = None
        contents = []

        for msg in messages:
            if msg.role == "system":
                # Gemini has a dedicated systemInstruction field
                system_text = msg.content
            elif msg.role == "user":
                contents.append({"role": "user", "parts": [{"text": msg.content}]})
            elif msg.role == "assistant":
                contents.append({"role": "model", "parts": [{"text": msg.content}]})

        return system_text, contents

    def _build_payload(self, messages: list[Message], max_tokens: int) -> dict:
        system_text, contents = self._messages_to_gemini(messages)
        payload: dict = {
            "contents": contents,
            "generationConfig": {
                "maxOutputTokens": max_tokens,
            },
        }
        if system_text:
            payload["systemInstruction"] = {
                "parts": [{"text": system_text}]
            }
        return payload

    def _calculate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        input_price, output_price = MODEL_PRICING.get(self._model, (0.0, 0.0))
        input_cost = (prompt_tokens / 1_000_000) * input_price
        output_cost = (completion_tokens / 1_000_000) * output_price
        return round(input_cost + output_cost, 8)

    async def complete(self, messages: list[Message], max_tokens: int = 2000) -> LLMResponse:
        url = self._api_url()
        payload = self._build_payload(messages, max_tokens)
        headers = {"Content-Type": "application/json"}

        last_exception: Optional[Exception] = None

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            for attempt in range(MAX_RETRIES):
                try:
                    response = await client.post(url, headers=headers, json=payload)

                    if response.status_code in RETRY_STATUSES:
                        delay = RETRY_BASE_DELAY * (2 ** attempt)
                        logger.warning(
                            "gemini_retry",
                            model=self._model,
                            status_code=response.status_code,
                            attempt=attempt + 1,
                            delay=delay,
                        )
                        await asyncio.sleep(delay)
                        continue

                    response.raise_for_status()
                    data = response.json()

                    # Gemini response: candidates[0].content.parts[0].text
                    candidates = data.get("candidates", [])
                    if not candidates:
                        raise RuntimeError(f"Gemini returned no candidates: {data}")

                    parts = candidates[0].get("content", {}).get("parts", [])
                    content = "".join(p.get("text", "") for p in parts)

                    # Token counts from usageMetadata
                    usage = data.get("usageMetadata", {})
                    prompt_tokens = usage.get("promptTokenCount", 0)
                    completion_tokens = usage.get("candidatesTokenCount", 0)

                    cost = self._calculate_cost(prompt_tokens, completion_tokens)

                    return LLMResponse(
                        content=content,
                        model=self._model,
                        provider="gemini",
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        cached=False,
                        cost_usd=cost,
                        raw_response=data,
                    )

                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 400:
                        # 400 from Gemini usually means invalid request — don't retry
                        try:
                            err_detail = e.response.json().get("error", {}).get("message", e.response.text)
                        except Exception:
                            err_detail = e.response.text
                        logger.error("gemini_bad_request", model=self._model, detail=err_detail)
                        raise RuntimeError(f"Gemini bad request: {err_detail}") from e

                    if e.response.status_code not in RETRY_STATUSES:
                        logger.error(
                            "gemini_http_error",
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
                        "gemini_request_error",
                        error=str(e),
                        attempt=attempt + 1,
                    )
                    await asyncio.sleep(delay)

        raise RuntimeError(
            f"Gemini request failed after {MAX_RETRIES} attempts (model: {self._model})"
        ) from last_exception
