"""Tests for webhook intake endpoints - signature verification and payload parsing."""
import hashlib
import hmac
import json
from unittest.mock import patch

import pytest
from httpx import AsyncClient

from app.webhooks.handlers import (
    WebhookAuthError,
    WebhookIntakeRecord,
    handle_datadog_webhook,
    handle_grafana_webhook,
    handle_pagerduty_webhook,
    handle_cloudwatch_webhook,
    verify_sns_signature,
    _verify_hmac,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sign_datadog(body: bytes, secret: str) -> str:
    """Compute Datadog HMAC-SHA256 signature (hex, no prefix)."""
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _sign_grafana(body: bytes, secret: str) -> str:
    """Compute Grafana HMAC-SHA256 signature (sha256= prefix)."""
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def _sign_pagerduty(body: bytes, secret: str) -> str:
    """Compute PagerDuty HMAC-SHA256 signature (v1= prefix)."""
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"v1={digest}"


DATADOG_SECRET = "test-datadog-secret-abc"
GRAFANA_SECRET = "test-grafana-secret-xyz"
PAGERDUTY_SECRET = "test-pagerduty-secret-pdp"

DATADOG_PAYLOAD = {
    "event_type": "metric_alert_monitor",
    "title": "High CPU on payment-service",
    "priority": "P1",
    "service": "payment-service",
    "date_detected": "1700000000",
}

GRAFANA_PAYLOAD = {
    "state": "alerting",
    "status": "firing",
    "title": "High error rate",
    "ruleName": "Error rate > 5%",
    "alerts": [
        {
            "status": "firing",
            "labels": {"service": "checkout", "severity": "critical"},
            "annotations": {"summary": "Error rate exceeded threshold"},
        }
    ],
    "dashboardURL": "https://grafana.example.com/d/abc123",
}

PAGERDUTY_PAYLOAD = {
    "messages": [
        {
            "event": {
                "event_type": "incident.triggered",
                "occurred_at": "2024-01-15T14:32:00Z",
                "data": {
                    "id": "PT1ABCD",
                    "title": "Payment service degraded",
                    "urgency": "high",
                    "status": "triggered",
                    "html_url": "https://myorg.pagerduty.com/incidents/PT1ABCD",
                },
            }
        }
    ]
}


# ---------------------------------------------------------------------------
# Handler unit tests (direct)
# ---------------------------------------------------------------------------


class TestDatadogHandler:
    def test_valid_signature_accepted(self):
        body = json.dumps(DATADOG_PAYLOAD).encode()
        sig = _sign_datadog(body, DATADOG_SECRET)
        record = handle_datadog_webhook(
            body=body,
            headers={"X-Datadog-Signature": sig},
            source_ip="1.2.3.4",
            org_id="org-001",
            current_secret=DATADOG_SECRET,
        )
        assert isinstance(record, WebhookIntakeRecord)
        assert record.source == "datadog"
        assert record.signature_valid is True
        assert record.event_type == "metric_alert_monitor"

    def test_invalid_signature_raises_auth_error(self):
        body = json.dumps(DATADOG_PAYLOAD).encode()
        with pytest.raises(WebhookAuthError) as exc_info:
            handle_datadog_webhook(
                body=body,
                headers={"X-Datadog-Signature": "wrong-signature"},
                source_ip="1.2.3.4",
                org_id="org-001",
                current_secret=DATADOG_SECRET,
            )
        assert exc_info.value.source == "datadog"

    def test_missing_signature_raises_auth_error(self):
        body = json.dumps(DATADOG_PAYLOAD).encode()
        with pytest.raises(WebhookAuthError):
            handle_datadog_webhook(
                body=body,
                headers={},
                source_ip="1.2.3.4",
                org_id="org-001",
                current_secret=DATADOG_SECRET,
            )

    def test_previous_secret_grace_window(self):
        """Previous secret still accepted during grace window."""
        old_secret = "old-secret-before-rotation"
        new_secret = "new-secret-after-rotation"
        body = json.dumps(DATADOG_PAYLOAD).encode()
        sig = _sign_datadog(body, old_secret)
        record = handle_datadog_webhook(
            body=body,
            headers={"X-Datadog-Signature": sig},
            source_ip="1.2.3.4",
            org_id="org-001",
            current_secret=new_secret,
            previous_secret=old_secret,
        )
        assert record.signature_valid is True

    def test_event_type_extracted(self):
        payload = {"event_type": "monitor_status_changed", "title": "Monitor Changed"}
        body = json.dumps(payload).encode()
        sig = _sign_datadog(body, DATADOG_SECRET)
        record = handle_datadog_webhook(
            body=body,
            headers={"X-Datadog-Signature": sig},
            source_ip="10.0.0.1",
            org_id="org-002",
            current_secret=DATADOG_SECRET,
        )
        assert record.event_type == "monitor_status_changed"


class TestGrafanaHandler:
    def test_valid_signature_accepted(self):
        body = json.dumps(GRAFANA_PAYLOAD).encode()
        sig = _sign_grafana(body, GRAFANA_SECRET)
        record = handle_grafana_webhook(
            body=body,
            headers={"X-Grafana-Signature": sig},
            source_ip="10.0.0.1",
            org_id="org-003",
            current_secret=GRAFANA_SECRET,
        )
        assert record.source == "grafana"
        assert record.signature_valid is True
        assert "alerting" in record.event_type or "firing" in record.event_type

    def test_invalid_signature_rejected(self):
        body = json.dumps(GRAFANA_PAYLOAD).encode()
        with pytest.raises(WebhookAuthError):
            handle_grafana_webhook(
                body=body,
                headers={"X-Grafana-Signature": "sha256=badhash"},
                source_ip="10.0.0.1",
                org_id="org-003",
                current_secret=GRAFANA_SECRET,
            )

    def test_missing_signature_rejected(self):
        body = json.dumps(GRAFANA_PAYLOAD).encode()
        with pytest.raises(WebhookAuthError):
            handle_grafana_webhook(
                body=body,
                headers={},
                source_ip="10.0.0.1",
                org_id="org-003",
                current_secret=GRAFANA_SECRET,
            )

    def test_firing_count_in_metadata(self):
        body = json.dumps(GRAFANA_PAYLOAD).encode()
        sig = _sign_grafana(body, GRAFANA_SECRET)
        record = handle_grafana_webhook(
            body=body,
            headers={"X-Grafana-Signature": sig},
            source_ip="10.0.0.1",
            org_id="org-003",
            current_secret=GRAFANA_SECRET,
        )
        assert record.metadata.get("firing_count") == 1


class TestPagerDutyHandler:
    def test_valid_signature_accepted(self):
        body = json.dumps(PAGERDUTY_PAYLOAD).encode()
        sig = _sign_pagerduty(body, PAGERDUTY_SECRET)
        record = handle_pagerduty_webhook(
            body=body,
            headers={"X-PagerDuty-Signature": sig},
            source_ip="203.0.113.5",
            org_id="org-004",
            current_secret=PAGERDUTY_SECRET,
        )
        assert record.source == "pagerduty"
        assert record.event_type == "incident.triggered"
        assert record.metadata["incident_id"] == "PT1ABCD"
        assert record.metadata["urgency"] == "high"

    def test_invalid_signature_rejected(self):
        body = json.dumps(PAGERDUTY_PAYLOAD).encode()
        with pytest.raises(WebhookAuthError):
            handle_pagerduty_webhook(
                body=body,
                headers={"X-PagerDuty-Signature": "v1=badhash"},
                source_ip="203.0.113.5",
                org_id="org-004",
                current_secret=PAGERDUTY_SECRET,
            )

    def test_missing_signature_rejected(self):
        body = json.dumps(PAGERDUTY_PAYLOAD).encode()
        with pytest.raises(WebhookAuthError):
            handle_pagerduty_webhook(
                body=body,
                headers={},
                source_ip="203.0.113.5",
                org_id="org-004",
                current_secret=PAGERDUTY_SECRET,
            )

    def test_multiple_signatures_header(self):
        """PagerDuty may send multiple v1= signatures for key rotation."""
        body = json.dumps(PAGERDUTY_PAYLOAD).encode()
        valid_sig = _sign_pagerduty(body, PAGERDUTY_SECRET)
        # Combine an old (invalid) sig with the valid one
        combined = f"v1=old-invalid-hash,{valid_sig}"
        record = handle_pagerduty_webhook(
            body=body,
            headers={"X-PagerDuty-Signature": combined},
            source_ip="203.0.113.5",
            org_id="org-004",
            current_secret=PAGERDUTY_SECRET,
        )
        assert record.signature_valid is True


class TestCloudWatchHandler:
    def test_sns_subscription_confirmation(self):
        """CloudWatch SNS subscription confirmation returns a record."""
        msg = {
            "Type": "SubscriptionConfirmation",
            "MessageId": "msg-id-001",
            "Token": "abc123token",
            "TopicArn": "arn:aws:sns:us-east-1:123456789012:my-topic",
            "SubscribeURL": "https://sns.us-east-1.amazonaws.com/confirm?token=abc",
            "Timestamp": "2024-01-15T14:32:00.000Z",
            "Message": "Please confirm the subscription.",
            "Signature": "ZXhhbXBsZXNpZ25hdHVyZQ==",
            "SigningCertURL": "https://sns.us-east-1.amazonaws.com/cert.pem",
        }
        body = json.dumps(msg).encode()
        # Patch verify_sns_signature to return True for testing
        with patch("app.webhooks.handlers.verify_sns_signature", return_value=True):
            record = handle_cloudwatch_webhook(
                body=body,
                headers={"x-amz-sns-message-type": "SubscriptionConfirmation"},
                source_ip="54.240.197.1",
                org_id="org-005",
            )
        assert record.event_type == "sns_subscription_confirmation"
        assert record.metadata.get("subscribe_url") is not None

    def test_alarm_notification_parsed(self):
        """CloudWatch alarm notification is parsed correctly."""
        inner = {
            "AlarmName": "HighCPU-payment-service",
            "NewStateValue": "ALARM",
            "OldStateValue": "OK",
            "NewStateReason": "Threshold Crossed: CPU > 80%",
        }
        msg = {
            "Type": "Notification",
            "MessageId": "msg-id-002",
            "Subject": "ALARM: HighCPU-payment-service",
            "Message": json.dumps(inner),
            "Timestamp": "2024-01-15T14:32:00.000Z",
            "TopicArn": "arn:aws:sns:us-east-1:123456789012:my-topic",
            "Signature": "ZXhhbXBsZXNpZ25hdHVyZQ==",
            "SigningCertURL": "https://sns.us-east-1.amazonaws.com/cert.pem",
        }
        body = json.dumps(msg).encode()
        with patch("app.webhooks.handlers.verify_sns_signature", return_value=True):
            record = handle_cloudwatch_webhook(
                body=body,
                headers={},
                source_ip="54.240.197.1",
                org_id="org-005",
            )
        assert record.source == "cloudwatch"
        assert record.event_type == "cloudwatch_alarm_alarm"
        assert record.metadata["alarm_name"] == "HighCPU-payment-service"
        assert record.metadata["state"] == "ALARM"

    def test_invalid_sns_signature_raises_auth_error(self):
        """Invalid SNS signature is rejected."""
        msg = {
            "Type": "Notification",
            "MessageId": "msg-id-003",
            "Message": "{}",
            "Timestamp": "2024-01-15T14:32:00.000Z",
            "Signature": "invalidsig",
            "SigningCertURL": "https://sns.us-east-1.amazonaws.com/cert.pem",
        }
        body = json.dumps(msg).encode()
        with patch("app.webhooks.handlers.verify_sns_signature", return_value=False):
            with pytest.raises(WebhookAuthError):
                handle_cloudwatch_webhook(
                    body=body,
                    headers={},
                    source_ip="54.240.197.1",
                    org_id="org-005",
                )


# ---------------------------------------------------------------------------
# Signature helper unit tests
# ---------------------------------------------------------------------------


def test_verify_hmac_exact_match():
    secret = "my-secret"
    body = b'{"hello": "world"}'
    correct_sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert _verify_hmac(body, correct_sig, secret) is True


def test_verify_hmac_wrong_secret():
    body = b'{"hello": "world"}'
    sig = hmac.new(b"correct-secret", body, hashlib.sha256).hexdigest()
    assert _verify_hmac(body, sig, "wrong-secret") is False


def test_verify_hmac_with_prefix_stripped():
    secret = "my-secret"
    body = b"test payload"
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    sig_with_prefix = f"sha256={digest}"
    assert _verify_hmac(body, sig_with_prefix, secret, prefix="sha256=") is True


def test_verify_hmac_previous_secret_fallback():
    old_secret = "old-secret"
    new_secret = "new-secret"
    body = b"payload"
    sig = hmac.new(old_secret.encode(), body, hashlib.sha256).hexdigest()
    # Should fail with new_secret alone
    assert _verify_hmac(body, sig, new_secret) is False
    # Should succeed with previous_secret fallback
    assert _verify_hmac(body, sig, new_secret, previous_secret=old_secret) is True
