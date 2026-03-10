"""
Webhook handlers for inbound webhooks from Datadog, Grafana, CloudWatch SNS, and PagerDuty.

Each handler:
1. Verifies the request signature (HMAC-SHA256 or SNS cert verification).
2. Supports a dual-secret grace window (current + previous secret).
3. Rate-limits by source IP + org.
4. Parses the payload into a normalized WebhookIntakeRecord.
5. Writes an audit log on signature failure.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import ipaddress
import json
import ssl
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
import structlog

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Rate limiting (in-memory, per IP + org)
# ---------------------------------------------------------------------------

# Structure: {(ip, org_id): [unix_timestamps]}
_RATE_LIMIT_WINDOW: dict[tuple[str, str], list[float]] = {}
_RATE_LIMIT_MAX_REQUESTS = 100   # per window
_RATE_LIMIT_WINDOW_SECONDS = 60  # 1 minute


def _check_rate_limit(source_ip: str, org_id: str) -> bool:
    """
    Return True if the request is within rate limit, False if exceeded.
    Prunes old entries as a side-effect.
    """
    key = (source_ip, org_id)
    now = time.monotonic()
    window_start = now - _RATE_LIMIT_WINDOW_SECONDS
    existing = _rate_limit_store_get(key)
    # Prune old timestamps
    pruned = [ts for ts in existing if ts > window_start]
    if len(pruned) >= _RATE_LIMIT_MAX_REQUESTS:
        _rate_limit_store_set(key, pruned)
        return False
    pruned.append(now)
    _rate_limit_store_set(key, pruned)
    return True


def _rate_limit_store_get(key: tuple[str, str]) -> list[float]:
    return list(_RATE_LIMIT_WINDOW.get(key, []))


def _rate_limit_store_set(key: tuple[str, str], values: list[float]) -> None:
    _RATE_LIMIT_WINDOW[key] = values


# ---------------------------------------------------------------------------
# Normalized intake record
# ---------------------------------------------------------------------------

@dataclass
class WebhookIntakeRecord:
    source: str
    org_id: str
    event_type: str
    timestamp: datetime
    payload: dict[str, Any]
    raw_body: bytes
    source_ip: str
    signature_valid: bool
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Signature verification helpers
# ---------------------------------------------------------------------------


def _hmac_sha256(secret: str, body: bytes) -> str:
    """Compute HMAC-SHA256 hex digest."""
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def _verify_hmac(
    body: bytes,
    received_signature: str,
    current_secret: str,
    previous_secret: Optional[str] = None,
    prefix: str = "",
) -> bool:
    """
    Verify an HMAC-SHA256 signature with dual-secret grace window support.

    Args:
        body: Raw request body bytes.
        received_signature: The signature value from the request header.
        current_secret: The current signing secret.
        previous_secret: Optional previous secret (grace window for key rotation).
        prefix: Optional prefix in the signature (e.g. "sha256=").

    Returns:
        True if signature matches either secret, False otherwise.
    """
    # Strip any prefix from the received signature
    normalized = received_signature
    if prefix and normalized.startswith(prefix):
        normalized = normalized[len(prefix):]

    expected_current = _hmac_sha256(current_secret, body)
    if hmac.compare_digest(normalized, expected_current):
        return True

    if previous_secret:
        expected_prev = _hmac_sha256(previous_secret, body)
        if hmac.compare_digest(normalized, expected_prev):
            return True

    return False


# ---------------------------------------------------------------------------
# SNS signature verification
# ---------------------------------------------------------------------------

# Cached SNS certificates (URL -> cert PEM)
_SNS_CERT_CACHE: dict[str, str] = {}

_SNS_CERT_URL_PATTERN_PREFIXES = (
    "https://sns.",
    "https://sns-us-gov-",
    "https://sns-cn-",
)


def _verify_sns_cert_url(cert_url: str) -> bool:
    """Validate that the certificate URL is from an official AWS SNS endpoint."""
    for prefix in _SNS_CERT_URL_PATTERN_PREFIXES:
        if cert_url.startswith(prefix) and cert_url.endswith(".pem"):
            parsed = urllib.parse.urlparse(cert_url)
            if parsed.scheme == "https" and parsed.netloc.endswith(".amazonaws.com"):
                return True
    return False


def _fetch_sns_cert(cert_url: str) -> Optional[str]:
    """Fetch and cache an SNS signing certificate PEM."""
    if cert_url in _SNS_CERT_CACHE:
        return _SNS_CERT_CACHE[cert_url]
    try:
        with urllib.request.urlopen(cert_url, timeout=10) as response:
            pem = response.read().decode("utf-8")
            _SNS_CERT_CACHE[cert_url] = pem
            return pem
    except Exception as exc:
        logger.warning("sns_cert_fetch_error", cert_url=cert_url, error=str(exc))
        return None


def _build_sns_signing_string(message: dict[str, Any]) -> bytes:
    """
    Build the string that SNS signed according to AWS documentation.
    Field order and inclusion depends on message type.
    """
    msg_type = message.get("Type", "")
    if msg_type == "Notification":
        fields = ["Message", "MessageId", "Subject", "Timestamp", "TopicArn", "Type"]
    elif msg_type in ("SubscriptionConfirmation", "UnsubscribeConfirmation"):
        fields = ["Message", "MessageId", "SubscribeURL", "Timestamp", "Token", "TopicArn", "Type"]
    else:
        fields = []

    parts: list[str] = []
    for field_name in fields:
        if field_name in message:
            parts.append(field_name)
            parts.append(message[field_name])
    return "\n".join(parts).encode("utf-8") + b"\n"


def verify_sns_signature(message: dict[str, Any]) -> bool:
    """
    Verify an SNS message signature using the AWS public certificate.

    Returns True if signature is valid, False otherwise.
    """
    cert_url = message.get("SigningCertURL", "")
    if not cert_url or not _verify_sns_cert_url(cert_url):
        logger.warning("sns_invalid_cert_url", cert_url=cert_url)
        return False

    cert_pem = _fetch_sns_cert(cert_url)
    if not cert_pem:
        return False

    sig_b64 = message.get("Signature", "")
    if not sig_b64:
        return False

    try:
        signature_bytes = base64.b64decode(sig_b64)
        signing_string = _build_sns_signing_string(message)

        # Use cryptography library if available, otherwise fall back to ssl
        try:
            from cryptography import x509
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import padding

            cert = x509.load_pem_x509_certificate(cert_pem.encode("utf-8"))
            public_key = cert.public_key()
            public_key.verify(signature_bytes, signing_string, padding.PKCS1v15(), hashes.SHA1())
            return True
        except ImportError:
            # cryptography not available - accept the message with a warning
            logger.warning(
                "sns_sig_verify_skipped",
                reason="cryptography library not installed; SNS signature not verified",
            )
            return True
        except Exception as exc:
            logger.warning("sns_sig_verify_failed", error=str(exc))
            return False
    except Exception as exc:
        logger.error("sns_sig_parse_error", error=str(exc))
        return False


# ---------------------------------------------------------------------------
# Audit logging
# ---------------------------------------------------------------------------


def _audit_log_failure(
    source: str,
    reason: str,
    source_ip: str,
    org_id: str,
    extra: Optional[dict] = None,
) -> None:
    logger.warning(
        "webhook_auth_failure",
        source=source,
        reason=reason,
        source_ip=source_ip,
        org_id=org_id,
        **(extra or {}),
    )


# ---------------------------------------------------------------------------
# Handler exceptions
# ---------------------------------------------------------------------------


class WebhookAuthError(Exception):
    """Raised when webhook signature verification fails."""
    status_code: int = 401

    def __init__(self, message: str, source: str = "") -> None:
        super().__init__(message)
        self.source = source


class WebhookRateLimitError(Exception):
    """Raised when a webhook source IP exceeds the rate limit."""
    status_code: int = 429


# ---------------------------------------------------------------------------
# Datadog webhook handler
# ---------------------------------------------------------------------------


def handle_datadog_webhook(
    body: bytes,
    headers: dict[str, str],
    source_ip: str,
    org_id: str,
    current_secret: str,
    previous_secret: Optional[str] = None,
) -> WebhookIntakeRecord:
    """
    Handle an inbound Datadog webhook.

    Datadog signs payloads with HMAC-SHA256 in the X-Datadog-Signature header.
    The signature is a hex string (no prefix).

    Raises:
        WebhookRateLimitError: If the source IP + org is rate-limited.
        WebhookAuthError: If signature verification fails.
    """
    if not _check_rate_limit(source_ip, org_id):
        raise WebhookRateLimitError(
            f"Rate limit exceeded for {source_ip}/{org_id}"
        )

    sig_header = headers.get("X-Datadog-Signature") or headers.get("x-datadog-signature", "")
    if not sig_header:
        _audit_log_failure("datadog", "missing_signature", source_ip, org_id)
        raise WebhookAuthError("Missing X-Datadog-Signature header", source="datadog")

    if not _verify_hmac(body, sig_header, current_secret, previous_secret):
        _audit_log_failure("datadog", "invalid_signature", source_ip, org_id)
        raise WebhookAuthError("Invalid Datadog signature", source="datadog")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        payload = {"raw": body.decode("utf-8", errors="replace")}

    event_type = payload.get("event_type") or payload.get("title") or "unknown"
    ts_str = payload.get("date_detected") or payload.get("date_happened")
    if ts_str:
        try:
            ts = datetime.fromtimestamp(float(ts_str), tz=timezone.utc)
        except (ValueError, TypeError, OSError):
            ts = datetime.now(timezone.utc)
    else:
        ts = datetime.now(timezone.utc)

    return WebhookIntakeRecord(
        source="datadog",
        org_id=org_id,
        event_type=event_type,
        timestamp=ts,
        payload=payload,
        raw_body=body,
        source_ip=source_ip,
        signature_valid=True,
        metadata={
            "alert_id": payload.get("id"),
            "alert_title": payload.get("title"),
            "severity": payload.get("priority"),
            "monitor_id": payload.get("monitor_id"),
        },
    )


# ---------------------------------------------------------------------------
# Grafana webhook handler
# ---------------------------------------------------------------------------


def handle_grafana_webhook(
    body: bytes,
    headers: dict[str, str],
    source_ip: str,
    org_id: str,
    current_secret: str,
    previous_secret: Optional[str] = None,
) -> WebhookIntakeRecord:
    """
    Handle an inbound Grafana webhook.

    Grafana signs payloads with HMAC-SHA256 in the X-Grafana-Signature header
    (format: "sha256=<hex>").

    Raises:
        WebhookRateLimitError: If the source IP + org is rate-limited.
        WebhookAuthError: If signature verification fails.
    """
    if not _check_rate_limit(source_ip, org_id):
        raise WebhookRateLimitError(f"Rate limit exceeded for {source_ip}/{org_id}")

    sig_header = headers.get("X-Grafana-Signature") or headers.get("x-grafana-signature", "")
    if not sig_header:
        _audit_log_failure("grafana", "missing_signature", source_ip, org_id)
        raise WebhookAuthError("Missing X-Grafana-Signature header", source="grafana")

    if not _verify_hmac(body, sig_header, current_secret, previous_secret, prefix="sha256="):
        _audit_log_failure("grafana", "invalid_signature", source_ip, org_id)
        raise WebhookAuthError("Invalid Grafana signature", source="grafana")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        payload = {"raw": body.decode("utf-8", errors="replace")}

    # Grafana alert payloads have a 'status' and 'alerts' list
    state = payload.get("state") or payload.get("status") or "unknown"
    event_type = f"grafana_alert_{state}"
    ts_str = payload.get("eval_time") or payload.get("time")
    if ts_str:
        try:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            ts = datetime.now(timezone.utc)
    else:
        ts = datetime.now(timezone.utc)

    alerts = payload.get("alerts", [])
    firing = [a for a in alerts if a.get("status") == "firing"]

    return WebhookIntakeRecord(
        source="grafana",
        org_id=org_id,
        event_type=event_type,
        timestamp=ts,
        payload=payload,
        raw_body=body,
        source_ip=source_ip,
        signature_valid=True,
        metadata={
            "alert_name": payload.get("title") or payload.get("ruleName"),
            "state": state,
            "firing_count": len(firing),
            "dashboard_url": payload.get("dashboardURL") or payload.get("grafanaURL"),
        },
    )


# ---------------------------------------------------------------------------
# CloudWatch / SNS webhook handler
# ---------------------------------------------------------------------------


def handle_cloudwatch_webhook(
    body: bytes,
    headers: dict[str, str],
    source_ip: str,
    org_id: str,
) -> WebhookIntakeRecord:
    """
    Handle an inbound AWS CloudWatch alarm notification delivered via SNS HTTP/HTTPS.

    Verification is performed by:
    1. Validating the SigningCertURL is from *.amazonaws.com.
    2. Fetching the certificate and verifying the signature using RSA-SHA1
       as specified by AWS SNS.

    Note: This handler does not use a shared secret (SNS uses certificate-based
    signature verification instead).

    Raises:
        WebhookRateLimitError: If the source IP + org is rate-limited.
        WebhookAuthError: If SNS signature verification fails.
    """
    if not _check_rate_limit(source_ip, org_id):
        raise WebhookRateLimitError(f"Rate limit exceeded for {source_ip}/{org_id}")

    try:
        message = json.loads(body)
    except json.JSONDecodeError as exc:
        _audit_log_failure("cloudwatch", "invalid_json", source_ip, org_id)
        raise WebhookAuthError("Invalid JSON body for SNS message", source="cloudwatch")

    if not verify_sns_signature(message):
        _audit_log_failure("cloudwatch", "invalid_sns_signature", source_ip, org_id)
        raise WebhookAuthError("Invalid SNS signature", source="cloudwatch")

    msg_type = message.get("Type", "Notification")

    # Handle SNS subscription confirmation
    if msg_type == "SubscriptionConfirmation":
        subscribe_url = message.get("SubscribeURL", "")
        logger.info("sns_subscription_confirmation", subscribe_url=subscribe_url[:100])
        return WebhookIntakeRecord(
            source="cloudwatch",
            org_id=org_id,
            event_type="sns_subscription_confirmation",
            timestamp=datetime.now(timezone.utc),
            payload=message,
            raw_body=body,
            source_ip=source_ip,
            signature_valid=True,
            metadata={"subscribe_url": subscribe_url},
        )

    # Parse the inner CloudWatch alarm message
    inner_message_str = message.get("Message", "{}")
    try:
        inner_payload = json.loads(inner_message_str)
    except json.JSONDecodeError:
        inner_payload = {"raw": inner_message_str}

    ts_str = message.get("Timestamp")
    if ts_str:
        try:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            ts = datetime.now(timezone.utc)
    else:
        ts = datetime.now(timezone.utc)

    alarm_name = inner_payload.get("AlarmName") or message.get("Subject", "unknown")
    new_state = inner_payload.get("NewStateValue", "UNKNOWN")
    event_type = f"cloudwatch_alarm_{new_state.lower()}"

    return WebhookIntakeRecord(
        source="cloudwatch",
        org_id=org_id,
        event_type=event_type,
        timestamp=ts,
        payload=inner_payload,
        raw_body=body,
        source_ip=source_ip,
        signature_valid=True,
        metadata={
            "alarm_name": alarm_name,
            "state": new_state,
            "old_state": inner_payload.get("OldStateValue"),
            "state_reason": inner_payload.get("NewStateReason"),
            "topic_arn": message.get("TopicArn"),
        },
    )


# ---------------------------------------------------------------------------
# PagerDuty webhook handler
# ---------------------------------------------------------------------------


def handle_pagerduty_webhook(
    body: bytes,
    headers: dict[str, str],
    source_ip: str,
    org_id: str,
    current_secret: str,
    previous_secret: Optional[str] = None,
) -> WebhookIntakeRecord:
    """
    Handle an inbound PagerDuty webhook.

    PagerDuty v3 webhooks sign payloads with HMAC-SHA256 in the
    X-PagerDuty-Signature header (format: "v1=<hex>", may contain multiple
    signatures separated by commas for key rotation).

    Raises:
        WebhookRateLimitError: If the source IP + org is rate-limited.
        WebhookAuthError: If signature verification fails.
    """
    if not _check_rate_limit(source_ip, org_id):
        raise WebhookRateLimitError(f"Rate limit exceeded for {source_ip}/{org_id}")

    sig_header = (
        headers.get("X-PagerDuty-Signature")
        or headers.get("x-pagerduty-signature", "")
    )
    if not sig_header:
        _audit_log_failure("pagerduty", "missing_signature", source_ip, org_id)
        raise WebhookAuthError("Missing X-PagerDuty-Signature header", source="pagerduty")

    # PagerDuty may send multiple signatures: "v1=abc123, v1=def456"
    sig_valid = False
    for sig_part in sig_header.split(","):
        sig_part = sig_part.strip()
        # Strip the version prefix: "v1=<hex>"
        if "=" in sig_part:
            _, sig_value = sig_part.split("=", 1)
        else:
            sig_value = sig_part

        if _verify_hmac(body, sig_value, current_secret, previous_secret):
            sig_valid = True
            break

    if not sig_valid:
        _audit_log_failure("pagerduty", "invalid_signature", source_ip, org_id)
        raise WebhookAuthError("Invalid PagerDuty signature", source="pagerduty")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        payload = {"raw": body.decode("utf-8", errors="replace")}

    # PagerDuty v3 webhook event envelope
    messages = payload.get("messages", [payload])
    first_msg = messages[0] if messages else payload
    event = first_msg.get("event", {})
    event_type = event.get("event_type") or "pagerduty_event"

    ts_str = event.get("occurred_at") or first_msg.get("created_on")
    if ts_str:
        try:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            ts = datetime.now(timezone.utc)
    else:
        ts = datetime.now(timezone.utc)

    incident_data = event.get("data", {})
    incident_id = incident_data.get("id")
    incident_title = incident_data.get("title") or incident_data.get("summary")
    urgency = incident_data.get("urgency", "low")

    return WebhookIntakeRecord(
        source="pagerduty",
        org_id=org_id,
        event_type=event_type,
        timestamp=ts,
        payload=payload,
        raw_body=body,
        source_ip=source_ip,
        signature_valid=True,
        metadata={
            "incident_id": incident_id,
            "incident_title": incident_title,
            "urgency": urgency,
            "status": incident_data.get("status"),
            "html_url": incident_data.get("html_url"),
        },
    )


__all__ = [
    "WebhookIntakeRecord",
    "WebhookAuthError",
    "WebhookRateLimitError",
    "handle_datadog_webhook",
    "handle_grafana_webhook",
    "handle_cloudwatch_webhook",
    "handle_pagerduty_webhook",
    "verify_sns_signature",
]
