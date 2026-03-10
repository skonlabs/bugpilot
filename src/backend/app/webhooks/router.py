"""
FastAPI router for inbound webhook endpoints.

Endpoints:
  POST /v1/webhooks/datadog
  POST /v1/webhooks/grafana
  POST /v1/webhooks/cloudwatch
  POST /v1/webhooks/pagerduty
"""
from __future__ import annotations

from typing import Optional

import structlog
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse

from app.webhooks.handlers import (
    WebhookAuthError,
    WebhookIntakeRecord,
    WebhookRateLimitError,
    handle_cloudwatch_webhook,
    handle_datadog_webhook,
    handle_grafana_webhook,
    handle_pagerduty_webhook,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/v1/webhooks", tags=["webhooks"])

# ---------------------------------------------------------------------------
# Helper: extract source IP
# ---------------------------------------------------------------------------


def _get_source_ip(request: Request) -> str:
    """Extract the real client IP, respecting X-Forwarded-For if set."""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Take the first IP in the chain (leftmost = original client)
        return forwarded_for.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


# ---------------------------------------------------------------------------
# Helper: read org_id from request
# ---------------------------------------------------------------------------


def _get_org_id(request: Request) -> str:
    """
    Extract org_id from query parameters or headers.
    Falls back to 'default' if not present.
    """
    org_id = request.query_params.get("org_id")
    if not org_id:
        org_id = request.headers.get("X-BugPilot-Org-Id", "default")
    return org_id


# ---------------------------------------------------------------------------
# Helper: get secrets from app state / config
# ---------------------------------------------------------------------------


def _get_datadog_secrets(request: Request) -> tuple[str, Optional[str]]:
    """Return (current_secret, previous_secret) for Datadog."""
    state = getattr(request.app, "state", None)
    current = getattr(state, "DATADOG_WEBHOOK_SECRET", "") if state else ""
    previous = getattr(state, "DATADOG_WEBHOOK_SECRET_PREV", None) if state else None
    return current, previous


def _get_grafana_secrets(request: Request) -> tuple[str, Optional[str]]:
    state = getattr(request.app, "state", None)
    current = getattr(state, "GRAFANA_WEBHOOK_SECRET", "") if state else ""
    previous = getattr(state, "GRAFANA_WEBHOOK_SECRET_PREV", None) if state else None
    return current, previous


def _get_pagerduty_secrets(request: Request) -> tuple[str, Optional[str]]:
    state = getattr(request.app, "state", None)
    current = getattr(state, "PAGERDUTY_WEBHOOK_SECRET", "") if state else ""
    previous = getattr(state, "PAGERDUTY_WEBHOOK_SECRET_PREV", None) if state else None
    return current, previous


# ---------------------------------------------------------------------------
# Response helper
# ---------------------------------------------------------------------------


def _intake_record_to_response(record: WebhookIntakeRecord) -> dict:
    return {
        "accepted": True,
        "source": record.source,
        "event_type": record.event_type,
        "timestamp": record.timestamp.isoformat(),
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post(
    "/datadog",
    summary="Receive Datadog webhook",
    status_code=status.HTTP_200_OK,
)
async def datadog_webhook(request: Request) -> JSONResponse:
    """
    Accepts inbound Datadog alert/event webhooks.
    Verifies HMAC-SHA256 signature from X-Datadog-Signature header.
    Supports dual-secret grace window for key rotation.
    Rate-limits by source IP + org.
    """
    body = await request.body()
    source_ip = _get_source_ip(request)
    org_id = _get_org_id(request)
    headers = dict(request.headers)
    current_secret, previous_secret = _get_datadog_secrets(request)

    try:
        record = handle_datadog_webhook(
            body=body,
            headers=headers,
            source_ip=source_ip,
            org_id=org_id,
            current_secret=current_secret,
            previous_secret=previous_secret,
        )
    except WebhookRateLimitError:
        logger.warning(
            "datadog_webhook_rate_limited",
            source_ip=source_ip,
            org_id=org_id,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
        )
    except WebhookAuthError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Signature verification failed",
        )
    except Exception as exc:
        logger.error("datadog_webhook_error", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )

    logger.info(
        "datadog_webhook_accepted",
        event_type=record.event_type,
        org_id=org_id,
    )
    return JSONResponse(content=_intake_record_to_response(record))


@router.post(
    "/grafana",
    summary="Receive Grafana webhook",
    status_code=status.HTTP_200_OK,
)
async def grafana_webhook(request: Request) -> JSONResponse:
    """
    Accepts inbound Grafana alert webhooks.
    Verifies HMAC-SHA256 signature from X-Grafana-Signature header (sha256= prefix).
    Supports dual-secret grace window for key rotation.
    Rate-limits by source IP + org.
    """
    body = await request.body()
    source_ip = _get_source_ip(request)
    org_id = _get_org_id(request)
    headers = dict(request.headers)
    current_secret, previous_secret = _get_grafana_secrets(request)

    try:
        record = handle_grafana_webhook(
            body=body,
            headers=headers,
            source_ip=source_ip,
            org_id=org_id,
            current_secret=current_secret,
            previous_secret=previous_secret,
        )
    except WebhookRateLimitError:
        logger.warning(
            "grafana_webhook_rate_limited",
            source_ip=source_ip,
            org_id=org_id,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
        )
    except WebhookAuthError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Signature verification failed",
        )
    except Exception as exc:
        logger.error("grafana_webhook_error", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )

    logger.info(
        "grafana_webhook_accepted",
        event_type=record.event_type,
        org_id=org_id,
    )
    return JSONResponse(content=_intake_record_to_response(record))


@router.post(
    "/cloudwatch",
    summary="Receive CloudWatch (SNS) webhook",
    status_code=status.HTTP_200_OK,
)
async def cloudwatch_webhook(request: Request) -> JSONResponse:
    """
    Accepts inbound AWS CloudWatch alarm notifications delivered via SNS HTTP/HTTPS.
    Verifies the SNS message signature using the AWS public certificate.
    Handles SubscriptionConfirmation and Notification message types.
    Rate-limits by source IP + org.
    """
    body = await request.body()
    source_ip = _get_source_ip(request)
    org_id = _get_org_id(request)
    headers = dict(request.headers)

    try:
        record = handle_cloudwatch_webhook(
            body=body,
            headers=headers,
            source_ip=source_ip,
            org_id=org_id,
        )
    except WebhookRateLimitError:
        logger.warning(
            "cloudwatch_webhook_rate_limited",
            source_ip=source_ip,
            org_id=org_id,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
        )
    except WebhookAuthError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="SNS signature verification failed",
        )
    except Exception as exc:
        logger.error("cloudwatch_webhook_error", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )

    logger.info(
        "cloudwatch_webhook_accepted",
        event_type=record.event_type,
        org_id=org_id,
    )
    return JSONResponse(content=_intake_record_to_response(record))


@router.post(
    "/pagerduty",
    summary="Receive PagerDuty webhook",
    status_code=status.HTTP_200_OK,
)
async def pagerduty_webhook(request: Request) -> JSONResponse:
    """
    Accepts inbound PagerDuty v3 alert/incident webhooks.
    Verifies HMAC-SHA256 signature from X-PagerDuty-Signature header.
    Supports multiple signatures in the header for key rotation.
    Rate-limits by source IP + org.
    """
    body = await request.body()
    source_ip = _get_source_ip(request)
    org_id = _get_org_id(request)
    headers = dict(request.headers)
    current_secret, previous_secret = _get_pagerduty_secrets(request)

    try:
        record = handle_pagerduty_webhook(
            body=body,
            headers=headers,
            source_ip=source_ip,
            org_id=org_id,
            current_secret=current_secret,
            previous_secret=previous_secret,
        )
    except WebhookRateLimitError:
        logger.warning(
            "pagerduty_webhook_rate_limited",
            source_ip=source_ip,
            org_id=org_id,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
        )
    except WebhookAuthError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Signature verification failed",
        )
    except Exception as exc:
        logger.error("pagerduty_webhook_error", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )

    logger.info(
        "pagerduty_webhook_accepted",
        event_type=record.event_type,
        org_id=org_id,
    )
    return JSONResponse(content=_intake_record_to_response(record))


__all__ = ["router"]
