"""
Notifier — sends investigation results via Slack Block Kit and AWS SNS.

Slack message format: Block Kit with hypothesis card + confidence bar.
SNS: publishes JSON payload for CLI polling and other subscribers.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Optional

import boto3
import httpx

log = logging.getLogger(__name__)


# ── Slack ──────────────────────────────────────────────────────────────────────

def _confidence_bar(confidence: float) -> str:
    """ASCII confidence bar: ████░░░░ 73%"""
    filled = round(confidence * 8)
    bar = "█" * filled + "░" * (8 - filled)
    return f"{bar} {confidence:.0%}"


def _build_slack_blocks(investigation: dict, hypotheses: list[dict]) -> list[dict]:
    inv_id = investigation.get("id", "")
    service = investigation.get("service_name") or "unknown service"
    trigger = investigation.get("trigger_ref", "")
    narrative = investigation.get("llm_narrative", "")
    duration_s = (investigation.get("duration_ms") or 0) / 1000

    top = hypotheses[0] if hypotheses else {}
    confidence = top.get("confidence", 0) or 0

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f":bug: BugPilot: {trigger or inv_id} — Root cause found",
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Service:*\n{service}"},
                {"type": "mrkdwn", "text": f"*Duration:*\n{duration_s:.1f}s"},
                {"type": "mrkdwn", "text": f"*Investigation:*\n{inv_id}"},
                {"type": "mrkdwn", "text": f"*Confidence:*\n{_confidence_bar(confidence)}"},
            ],
        },
    ]

    if top:
        pr_url = top.get("pr_url", "")
        pr_title = top.get("pr_title", "Unknown PR")
        pr_author = top.get("pr_author", "")
        file_path = top.get("file_path", "")
        merged_at = (top.get("pr_merged_at") or "")[:10]

        pr_link = f"<{pr_url}|{pr_title}>" if pr_url else pr_title
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*Top hypothesis:* {pr_link}\n"
                    f"Author: `{pr_author}` | Merged: {merged_at}\n"
                    + (f"File: `{file_path}`" if file_path else "")
                ),
            },
        })

    if narrative:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Analysis:*\n{narrative[:500]}"},
        })

    blast = investigation.get("blast_count")
    if blast:
        blast_val = investigation.get("blast_value_usd")
        blast_text = f"*Blast radius:* {blast} affected records"
        if blast_val:
            blast_text += f" (~${float(blast_val):,.0f} at risk)"
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": blast_text},
        })

    blocks.append({"type": "divider"})
    from backend.config import settings
    base_url = settings.BUGPILOT_BASE_URL
    blocks.append({
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "View Investigation"},
                "url": f"{base_url}/investigations/{inv_id}",
                "style": "primary",
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": ":white_check_mark: Confirm"},
                "value": f"confirm:{inv_id}",
                "action_id": "confirm_hypothesis",
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": ":x: Refute"},
                "value": f"refute:{inv_id}",
                "action_id": "refute_hypothesis",
            },
        ],
    })

    return blocks


def send_slack(
    webhook_url: str,
    investigation: dict,
    hypotheses: list[dict],
) -> bool:
    """Send Slack Block Kit notification. Returns True on success."""
    blocks = _build_slack_blocks(investigation, hypotheses)
    try:
        resp = httpx.post(
            webhook_url,
            json={"blocks": blocks},
            timeout=10,
        )
        if resp.status_code != 200:
            log.warning(f"Slack webhook returned {resp.status_code}: {resp.text}")
            return False
        return True
    except Exception as e:
        log.error(f"Slack notification error: {e}")
        return False


# ── SNS ───────────────────────────────────────────────────────────────────────

def publish_sns(
    investigation_id: str,
    org_id: str,
    status: str,
    hypotheses: list[dict],
    error_message: Optional[str] = None,
) -> None:
    """Publish investigation completion event to SNS."""
    sns_arn = os.environ.get("AWS_SNS_TOPIC_ARN") or os.environ.get("SNS_TOPIC_ARN")
    if not sns_arn:
        log.debug("AWS_SNS_TOPIC_ARN not set, skipping SNS publish")
        return

    payload = {
        "event": "investigation_complete",
        "investigation_id": investigation_id,
        "org_id": org_id,
        "status": status,
        "hypothesis_count": len(hypotheses),
        "top_confidence": hypotheses[0].get("confidence") if hypotheses else None,
        "error_message": error_message,
    }

    try:
        sns = boto3.client("sns", region_name=os.environ.get("AWS_REGION", "us-east-1"))
        sns.publish(
            TopicArn=sns_arn,
            Message=json.dumps(payload),
            Subject=f"BugPilot: {investigation_id} {status}",
            MessageAttributes={
                "org_id": {"DataType": "String", "StringValue": org_id},
                "investigation_id": {"DataType": "String", "StringValue": investigation_id},
            },
        )
        log.info(f"SNS published for {investigation_id}")
    except Exception as e:
        log.error(f"SNS publish error: {e}")
