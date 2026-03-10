"""
AWS CloudWatch connector for BugPilot.
Supports LOGS (CloudWatch Insights), METRICS (GetMetricData), and ALERTS (DescribeAlarms).

AWS SigV4 signing is implemented manually (no boto3 dependency).
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import time
import urllib.parse
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
import structlog

from app.connectors.base import (
    BaseConnector,
    ConnectorCapability,
    RawEvidenceItem,
    ValidationResult,
)
from app.connectors.retry import async_retry

logger = structlog.get_logger(__name__)

_SUPPORTED_CAPABILITIES = [
    ConnectorCapability.LOGS,
    ConnectorCapability.METRICS,
    ConnectorCapability.ALERTS,
]

_REQUEST_TIMEOUT = 30.0
_QUERY_POLL_INTERVAL = 2.0
_QUERY_MAX_WAIT = 60.0


# ---------------------------------------------------------------------------
# SigV4 signing helpers
# ---------------------------------------------------------------------------

def _sign(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _get_signature_key(
    secret_key: str,
    date_stamp: str,
    region: str,
    service: str,
) -> bytes:
    k_date = _sign(("AWS4" + secret_key).encode("utf-8"), date_stamp)
    k_region = _sign(k_date, region)
    k_service = _sign(k_region, service)
    k_signing = _sign(k_service, "aws4_request")
    return k_signing


def _sigv4_headers(
    method: str,
    host: str,
    uri: str,
    query_string: str,
    payload: str,
    region: str,
    service: str,
    access_key: str,
    secret_key: str,
    session_token: Optional[str] = None,
    extra_headers: Optional[dict[str, str]] = None,
) -> dict[str, str]:
    """
    Compute and return the Authorization + required headers for an AWS SigV4 request.
    """
    now = datetime.now(timezone.utc)
    amzdate = now.strftime("%Y%m%dT%H%M%SZ")
    datestamp = now.strftime("%Y%m%d")

    canonical_headers_dict: dict[str, str] = {
        "host": host,
        "x-amz-date": amzdate,
        "content-type": "application/x-amz-json-1.1",
    }
    if session_token:
        canonical_headers_dict["x-amz-security-token"] = session_token
    if extra_headers:
        for k, v in extra_headers.items():
            canonical_headers_dict[k.lower()] = v

    # Signed headers must be sorted
    signed_headers_list = sorted(canonical_headers_dict.keys())
    canonical_headers = "".join(f"{k}:{canonical_headers_dict[k]}\n" for k in signed_headers_list)
    signed_headers = ";".join(signed_headers_list)

    payload_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    canonical_request = "\n".join([
        method,
        uri,
        query_string,
        canonical_headers,
        signed_headers,
        payload_hash,
    ])

    credential_scope = f"{datestamp}/{region}/{service}/aws4_request"
    string_to_sign = "\n".join([
        "AWS4-HMAC-SHA256",
        amzdate,
        credential_scope,
        hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
    ])

    signing_key = _get_signature_key(secret_key, datestamp, region, service)
    signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    authorization_header = (
        f"AWS4-HMAC-SHA256 Credential={access_key}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, "
        f"Signature={signature}"
    )

    headers = {
        "x-amz-date": amzdate,
        "Authorization": authorization_header,
        "Content-Type": "application/x-amz-json-1.1",
    }
    if session_token:
        headers["x-amz-security-token"] = session_token
    if extra_headers:
        headers.update(extra_headers)
    return headers


def _to_epoch_ms(dt: datetime) -> int:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def _to_epoch(dt: datetime) -> int:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


def _to_iso8601(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Connector
# ---------------------------------------------------------------------------

class CloudWatchConnector(BaseConnector):
    """
    Connector for AWS CloudWatch.

    Supports:
    - LOGS    via CloudWatch Logs Insights (StartQuery + GetQueryResults)
    - METRICS via GetMetricData
    - ALERTS  via DescribeAlarms

    Authentication uses AWS SigV4 signed requests (no boto3).
    """

    def __init__(
        self,
        aws_access_key_id: str,
        aws_secret_access_key: str,
        region: str,
        aws_session_token: Optional[str] = None,
    ) -> None:
        self._access_key = aws_access_key_id
        self._secret_key = aws_secret_access_key
        self._session_token = aws_session_token
        self._region = region

        self._logs_host = f"logs.{region}.amazonaws.com"
        self._monitoring_host = f"monitoring.{region}.amazonaws.com"
        self._logs_endpoint = f"https://{self._logs_host}"
        self._monitoring_endpoint = f"https://{self._monitoring_host}"

    # ------------------------------------------------------------------
    # BaseConnector interface
    # ------------------------------------------------------------------

    def capabilities(self) -> list[ConnectorCapability]:
        return list(_SUPPORTED_CAPABILITIES)

    @async_retry(max_attempts=3, base_delay=1.0, jitter=True)
    async def validate(self) -> ValidationResult:
        """Validate credentials via DescribeLogGroups (CloudWatch Logs API)."""
        start = time.monotonic()
        try:
            payload = json.dumps({"limit": 1})
            headers = _sigv4_headers(
                method="POST",
                host=self._logs_host,
                uri="/",
                query_string="",
                payload=payload,
                region=self._region,
                service="logs",
                access_key=self._access_key,
                secret_key=self._secret_key,
                session_token=self._session_token,
                extra_headers={"x-amz-target": "Logs_20140328.DescribeLogGroups"},
            )
            async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
                resp = await client.post(
                    self._logs_endpoint + "/",
                    headers=headers,
                    content=payload.encode(),
                )
            latency_ms = (time.monotonic() - start) * 1000
            if resp.status_code == 200:
                return ValidationResult(is_valid=True, latency_ms=latency_ms)
            return ValidationResult(
                is_valid=False,
                error=f"Validation failed: HTTP {resp.status_code} - {resp.text[:200]}",
                latency_ms=latency_ms,
            )
        except Exception as exc:
            latency_ms = (time.monotonic() - start) * 1000
            logger.error("cloudwatch_validate_error", error=str(exc))
            return ValidationResult(is_valid=False, error=str(exc), latency_ms=latency_ms)

    async def fetch_evidence(
        self,
        capability: ConnectorCapability,
        service: str,
        since: datetime,
        until: datetime,
        limit: int = 500,
    ) -> list[RawEvidenceItem]:
        if capability == ConnectorCapability.LOGS:
            return await self._fetch_logs(service, since, until, limit)
        elif capability == ConnectorCapability.METRICS:
            return await self._fetch_metrics(service, since, until, limit)
        elif capability == ConnectorCapability.ALERTS:
            return await self._fetch_alerts(service, since, until, limit)
        else:
            logger.warning("cloudwatch_unsupported_capability", capability=capability.value)
            return []

    # ------------------------------------------------------------------
    # Private fetch methods
    # ------------------------------------------------------------------

    async def _logs_post(self, target: str, payload_dict: dict[str, Any]) -> dict[str, Any]:
        """Perform a signed POST to CloudWatch Logs."""
        payload = json.dumps(payload_dict)
        headers = _sigv4_headers(
            method="POST",
            host=self._logs_host,
            uri="/",
            query_string="",
            payload=payload,
            region=self._region,
            service="logs",
            access_key=self._access_key,
            secret_key=self._secret_key,
            session_token=self._session_token,
            extra_headers={"x-amz-target": f"Logs_20140328.{target}"},
        )
        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
            resp = await client.post(
                self._logs_endpoint + "/",
                headers=headers,
                content=payload.encode(),
            )
        resp.raise_for_status()
        return resp.json()

    async def _monitoring_post(self, action: str, form_data: dict[str, str]) -> str:
        """Perform a signed POST to CloudWatch Monitoring (form-encoded)."""
        form_data["Action"] = action
        form_data["Version"] = "2010-08-01"
        payload = urllib.parse.urlencode(form_data)
        headers = _sigv4_headers(
            method="POST",
            host=self._monitoring_host,
            uri="/",
            query_string="",
            payload=payload,
            region=self._region,
            service="monitoring",
            access_key=self._access_key,
            secret_key=self._secret_key,
            session_token=self._session_token,
        )
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
            resp = await client.post(
                self._monitoring_endpoint + "/",
                headers=headers,
                content=payload.encode(),
            )
        resp.raise_for_status()
        return resp.text

    @async_retry(max_attempts=3, base_delay=1.0, jitter=True)
    async def _fetch_logs(
        self, service: str, since: datetime, until: datetime, limit: int
    ) -> list[RawEvidenceItem]:
        """
        Fetch logs via CloudWatch Logs Insights:
        1. StartQuery - begin the query
        2. Poll GetQueryResults until complete
        """
        try:
            # Discover log groups matching the service name
            log_groups_resp = await self._logs_post(
                "DescribeLogGroups",
                {"logGroupNamePattern": service, "limit": 10},
            )
            log_groups = [
                lg["logGroupName"]
                for lg in log_groups_resp.get("logGroups", [])
            ]
            if not log_groups:
                # Fall back to a generic group name
                log_groups = [f"/aws/{service}"]

            query_request: dict[str, Any] = {
                "logGroupNames": log_groups[:20],
                "queryString": (
                    f"fields @timestamp, @message, @logStream, @log | "
                    f"filter @message like /{service}/ | "
                    f"sort @timestamp desc | limit {min(limit, 10000)}"
                ),
                "startTime": _to_epoch(since),
                "endTime": _to_epoch(until),
            }
            start_resp = await self._logs_post("StartQuery", query_request)
            query_id = start_resp.get("queryId")
            if not query_id:
                logger.warning("cloudwatch_no_query_id", service=service)
                return []

            # Poll until complete or timeout
            elapsed = 0.0
            results_data: list[dict] = []
            while elapsed < _QUERY_MAX_WAIT:
                await asyncio.sleep(_QUERY_POLL_INTERVAL)
                elapsed += _QUERY_POLL_INTERVAL
                results_resp = await self._logs_post("GetQueryResults", {"queryId": query_id})
                status = results_resp.get("status", "")
                if status == "Complete":
                    results_data = results_resp.get("results", [])
                    break
                elif status in ("Failed", "Cancelled", "Timeout"):
                    logger.warning("cloudwatch_query_failed", service=service, status=status)
                    return []

            items: list[RawEvidenceItem] = []
            for row in results_data:
                fields = {f["field"]: f["value"] for f in row}
                ts_str = fields.get("@timestamp", "")
                try:
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    ts = since
                items.append(
                    RawEvidenceItem(
                        capability=ConnectorCapability.LOGS,
                        source_system="cloudwatch",
                        service=service,
                        timestamp=ts,
                        payload=fields,
                        message=fields.get("@message"),
                        raw_ref=fields.get("@log"),
                    )
                )
            logger.info("cloudwatch_logs_fetched", service=service, count=len(items))
            return items
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "cloudwatch_logs_http_error",
                service=service,
                status=exc.response.status_code,
            )
            raise
        except Exception as exc:
            logger.error("cloudwatch_logs_error", service=service, error=str(exc))
            return []

    @async_retry(max_attempts=3, base_delay=1.0, jitter=True)
    async def _fetch_metrics(
        self, service: str, since: datetime, until: datetime, limit: int
    ) -> list[RawEvidenceItem]:
        """Fetch metrics via GetMetricData (form-encoded POST to CloudWatch Monitoring)."""
        try:
            form_data: dict[str, str] = {
                "StartTime": _to_iso8601(since),
                "EndTime": _to_iso8601(until),
                "MetricDataQueries.member.1.Id": "m1",
                "MetricDataQueries.member.1.Label": f"{service}_cpu",
                "MetricDataQueries.member.1.MetricStat.Metric.Namespace": "AWS/EC2",
                "MetricDataQueries.member.1.MetricStat.Metric.MetricName": "CPUUtilization",
                "MetricDataQueries.member.1.MetricStat.Metric.Dimensions.member.1.Name": "ServiceName",
                "MetricDataQueries.member.1.MetricStat.Metric.Dimensions.member.1.Value": service,
                "MetricDataQueries.member.1.MetricStat.Period": "60",
                "MetricDataQueries.member.1.MetricStat.Stat": "Average",
            }
            xml_text = await self._monitoring_post("GetMetricData", form_data)
            # Parse minimal info from XML (avoid lxml dependency)
            items: list[RawEvidenceItem] = []
            # Extract Timestamps and Values using simple string parsing
            import re as _re
            timestamps = _re.findall(r"<Timestamp>(.*?)</Timestamp>", xml_text)
            values = _re.findall(r"<Value>(.*?)</Value>", xml_text)
            for ts_str, val_str in zip(timestamps, values):
                try:
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    ts = since
                try:
                    value = float(val_str)
                except (ValueError, TypeError):
                    value = 0.0
                items.append(
                    RawEvidenceItem(
                        capability=ConnectorCapability.METRICS,
                        source_system="cloudwatch",
                        service=service,
                        timestamp=ts,
                        payload={"metric": "CPUUtilization", "value": value},
                        message=f"CPUUtilization={value}",
                    )
                )
            logger.info("cloudwatch_metrics_fetched", service=service, count=len(items))
            return items[:limit]
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "cloudwatch_metrics_http_error",
                service=service,
                status=exc.response.status_code,
            )
            raise
        except Exception as exc:
            logger.error("cloudwatch_metrics_error", service=service, error=str(exc))
            return []

    @async_retry(max_attempts=3, base_delay=1.0, jitter=True)
    async def _fetch_alerts(
        self, service: str, since: datetime, until: datetime, limit: int
    ) -> list[RawEvidenceItem]:
        """Fetch CloudWatch alarms via DescribeAlarms."""
        try:
            form_data: dict[str, str] = {
                "AlarmNamePrefix": service,
                "MaxRecords": str(min(limit, 100)),
            }
            xml_text = await self._monitoring_post("DescribeAlarms", form_data)
            import re as _re
            items: list[RawEvidenceItem] = []
            # Extract MetricAlarm blocks
            alarm_blocks = _re.findall(
                r"<member>(.*?)</member>", xml_text, _re.DOTALL
            )
            for block in alarm_blocks[:limit]:
                def _extract(tag: str, text: str = block) -> str:
                    m = _re.search(rf"<{tag}>(.*?)</{tag}>", text, _re.DOTALL)
                    return m.group(1).strip() if m else ""

                alarm_name = _extract("AlarmName")
                state = _extract("StateValue")
                reason = _extract("StateReason")
                state_updated = _extract("StateUpdatedTimestamp")

                try:
                    ts = datetime.fromisoformat(state_updated.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    ts = since

                severity = _cw_alarm_severity(state)
                items.append(
                    RawEvidenceItem(
                        capability=ConnectorCapability.ALERTS,
                        source_system="cloudwatch",
                        service=service,
                        timestamp=ts,
                        payload={
                            "AlarmName": alarm_name,
                            "StateValue": state,
                            "StateReason": reason,
                            "StateUpdatedTimestamp": state_updated,
                        },
                        severity=severity,
                        message=f"{alarm_name}: {reason}",
                        raw_ref=alarm_name,
                    )
                )
            logger.info("cloudwatch_alerts_fetched", service=service, count=len(items))
            return items
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "cloudwatch_alerts_http_error",
                service=service,
                status=exc.response.status_code,
            )
            raise
        except Exception as exc:
            logger.error("cloudwatch_alerts_error", service=service, error=str(exc))
            return []


def _cw_alarm_severity(state: str) -> str:
    mapping = {
        "ALARM": "critical",
        "INSUFFICIENT_DATA": "unknown",
        "OK": "ok",
    }
    return mapping.get(state.upper(), "unknown")


__all__ = ["CloudWatchConnector"]
