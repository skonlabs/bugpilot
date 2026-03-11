"""
LLMProviderFactory — resolves the correct LLMProvider for a given org.

Resolution precedence (highest → lowest):
  1. Per-org config  — Organization.settings["llm"]  (stored in DB)
  2. Environment     — LLM_PROVIDER / LLM_API_KEY / … env vars  (config.py Settings)
  3. Built-in default — Anthropic claude-sonnet-4-6 (BugPilot hosted)

Per-org config shape (Organization.settings["llm"]):
  {
    "provider": "openai_compatible",   # required
    "base_url": "https://vllm.acme.com",
    "api_key":  "sk-...",              # optional for unauthenticated endpoints
    "model":    "mistral-7b-instruct", # optional — provider default used if absent
    "timeout":  120,
    "input_cost_per_m":  0.0,          # optional, for usage tracking
    "output_cost_per_m": 0.0,
    # azure_openai extras:
    "azure_deployment":  "gpt-4o-prod",
    "azure_api_version": "2024-02-01",
    # extra HTTP headers for private endpoints:
    "extra_headers": {"X-My-Token": "..."}
  }

Supported provider values (both in env and per-org config):
  "anthropic"          Anthropic Claude  (BugPilot default)
  "openai"             OpenAI GPT
  "azure_openai"       Azure-hosted OpenAI deployment
  "gemini"             Google Gemini  (AI Studio API key)
  "ollama"             Local Ollama instance
  "openai_compatible"  Any OpenAI-compatible endpoint
                       (vLLM, LM Studio, LocalAI, Groq, Together.ai, Fireworks.ai, …)
"""
from __future__ import annotations

from typing import Any, Optional

import structlog

from app.llm.base import LLMProvider
from app.core.logging import get_logger

logger = get_logger(__name__)


# Default models per provider (used when LLM_MODEL / per-org "model" is empty)
_DEFAULT_MODELS: dict[str, str] = {
    "anthropic": "claude-sonnet-4-6",
    "openai": "gpt-4o",
    "azure_openai": "",        # must be set via deployment name
    "gemini": "gemini-2.0-flash",
    "ollama": "llama3",
    "openai_compatible": "",   # must be set explicitly
}


class LLMProviderFactory:
    """Builds the right LLMProvider from org config or env settings."""

    @staticmethod
    def from_org_settings(org_settings: Optional[dict[str, Any]]) -> Optional[LLMProvider]:
        """
        Build a provider from Organization.settings["llm"].
        Returns None if no per-org LLM config is present.
        """
        if not org_settings:
            return None
        llm_cfg = org_settings.get("llm")
        if not llm_cfg or not isinstance(llm_cfg, dict):
            return None

        provider_name = llm_cfg.get("provider", "").strip().lower()
        if not provider_name:
            return None

        logger.info("llm_provider_from_org_config", provider=provider_name)
        return _build_provider(
            provider=provider_name,
            api_key=llm_cfg.get("api_key", ""),
            model=llm_cfg.get("model", ""),
            base_url=llm_cfg.get("base_url", ""),
            timeout=float(llm_cfg.get("timeout", 60.0)),
            azure_deployment=llm_cfg.get("azure_deployment", ""),
            azure_api_version=llm_cfg.get("azure_api_version", "2024-02-01"),
            input_cost_per_m=float(llm_cfg.get("input_cost_per_m", 0.0)),
            output_cost_per_m=float(llm_cfg.get("output_cost_per_m", 0.0)),
            extra_headers=llm_cfg.get("extra_headers", {}),
        )

    @staticmethod
    def from_settings() -> LLMProvider:
        """
        Build a provider from environment-level Settings.
        Falls back to BugPilot default (Anthropic) if LLM_PROVIDER is not set.
        """
        from app.core.config import get_settings
        s = get_settings()

        logger.info("llm_provider_from_env", provider=s.LLM_PROVIDER)
        return _build_provider(
            provider=s.LLM_PROVIDER,
            api_key=s.LLM_API_KEY,
            model=s.LLM_MODEL,
            base_url=s.LLM_BASE_URL,
            timeout=s.LLM_TIMEOUT_SECONDS,
            azure_deployment=s.LLM_AZURE_DEPLOYMENT,
            azure_api_version=s.LLM_AZURE_API_VERSION,
            input_cost_per_m=s.LLM_INPUT_COST_PER_M,
            output_cost_per_m=s.LLM_OUTPUT_COST_PER_M,
        )

    @staticmethod
    def resolve(org_settings: Optional[dict[str, Any]] = None) -> LLMProvider:
        """
        Resolve the provider using the full precedence chain:
          org config  →  env settings  →  built-in default
        """
        # 1. Per-org config
        provider = LLMProviderFactory.from_org_settings(org_settings)
        if provider:
            return provider

        # 2. Env settings (also handles built-in default via LLM_PROVIDER="anthropic")
        return LLMProviderFactory.from_settings()


# ---------------------------------------------------------------------------
# Internal builder
# ---------------------------------------------------------------------------

def _build_provider(
    provider: str,
    api_key: str = "",
    model: str = "",
    base_url: str = "",
    timeout: float = 60.0,
    azure_deployment: str = "",
    azure_api_version: str = "2024-02-01",
    input_cost_per_m: float = 0.0,
    output_cost_per_m: float = 0.0,
    extra_headers: Optional[dict[str, str]] = None,
) -> LLMProvider:
    """Instantiate the concrete LLMProvider for the given provider name."""
    resolved_model = model or _DEFAULT_MODELS.get(provider, "")

    if provider == "anthropic":
        from app.llm.providers.anthropic_provider import AnthropicProvider
        return AnthropicProvider(
            api_key=api_key,
            model=resolved_model or "claude-sonnet-4-6",
            timeout=timeout,
        )

    if provider == "openai":
        from app.llm.providers.openai_provider import OpenAIProvider
        return OpenAIProvider(
            api_key=api_key,
            model=resolved_model or "gpt-4o",
            timeout=timeout,
        )

    if provider == "azure_openai":
        from app.llm.providers.azure_openai_provider import AzureOpenAIProvider
        if not base_url:
            raise ValueError("LLM_BASE_URL (Azure endpoint) is required for azure_openai provider")
        deployment = azure_deployment or resolved_model
        if not deployment:
            raise ValueError(
                "LLM_AZURE_DEPLOYMENT (or LLM_MODEL) is required for azure_openai provider"
            )
        return AzureOpenAIProvider(
            endpoint=base_url,
            api_key=api_key,
            deployment_name=deployment,
            api_version=azure_api_version,
            timeout=timeout,
            input_cost_per_million_tokens=input_cost_per_m,
            output_cost_per_million_tokens=output_cost_per_m,
        )

    if provider == "gemini":
        from app.llm.providers.gemini_provider import GeminiProvider
        if not api_key:
            raise ValueError("LLM_API_KEY is required for gemini provider (get one at aistudio.google.com)")
        return GeminiProvider(
            api_key=api_key,
            model=resolved_model or "gemini-2.0-flash",
            timeout=timeout,
        )

    if provider == "ollama":
        from app.llm.providers.ollama_provider import OllamaProvider
        return OllamaProvider(
            model=resolved_model or "llama3",
            base_url=base_url or "http://localhost:11434",
            timeout=timeout,
        )

    if provider == "openai_compatible":
        from app.llm.providers.openai_compatible_provider import OpenAICompatibleProvider
        if not base_url:
            raise ValueError(
                "LLM_BASE_URL is required for openai_compatible provider "
                "(e.g. https://my-vllm.example.com)"
            )
        if not resolved_model:
            raise ValueError(
                "LLM_MODEL is required for openai_compatible provider "
                "(e.g. mistral-7b-instruct)"
            )
        return OpenAICompatibleProvider(
            base_url=base_url,
            model=resolved_model,
            api_key=api_key or "none",
            timeout=timeout,
            input_cost_per_million_tokens=input_cost_per_m,
            output_cost_per_million_tokens=output_cost_per_m,
            extra_headers=extra_headers or {},
        )

    raise ValueError(
        f"Unknown LLM provider: {provider!r}. "
        "Supported: anthropic, openai, azure_openai, gemini, ollama, openai_compatible"
    )
