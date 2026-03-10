from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass
class Message:
    role: str  # "system", "user", "assistant"
    content: str


@dataclass
class LLMResponse:
    content: str
    model: str
    provider: str
    prompt_tokens: int
    completion_tokens: int
    cached: bool = False
    cost_usd: float = 0.0
    raw_response: Optional[dict[str, Any]] = None


@dataclass
class LLMUsageRecord:
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    cached: bool
    cost_usd: float
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
