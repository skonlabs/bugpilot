"""
Webhooks module - inbound webhook handling for external monitoring systems.

Provides:
- handlers: Signature verification and payload normalization for Datadog,
            Grafana, CloudWatch (SNS), and PagerDuty.
- router:   FastAPI router mounting the 4 webhook endpoints.
"""
from __future__ import annotations

from .handlers import (
    WebhookAuthError,
    WebhookIntakeRecord,
    WebhookRateLimitError,
    handle_cloudwatch_webhook,
    handle_datadog_webhook,
    handle_grafana_webhook,
    handle_pagerduty_webhook,
    verify_sns_signature,
)
from .router import router

__all__ = [
    "router",
    "WebhookIntakeRecord",
    "WebhookAuthError",
    "WebhookRateLimitError",
    "handle_datadog_webhook",
    "handle_grafana_webhook",
    "handle_cloudwatch_webhook",
    "handle_pagerduty_webhook",
    "verify_sns_signature",
]
